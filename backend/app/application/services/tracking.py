import asyncio
from collections import defaultdict
from datetime import timedelta

from app.application.dto import ChatInfo, TgMessage
from app.application.policies import Policies
from app.application.ports.repositories import UnitOfWork
from app.application.ports.telegram import TelegramSession
from app.application.services.telegram_access import AccountClients
from app.domain.entities import Account, Comment, CommentKind, TrackedMessage, utcnow
from app.domain.errors import (
    AccountDead,
    AccountUnavailable,
    DomainError,
    FloodWait,
    TelegramError,
)
from app.domain.values import comment_link, tme_link


def _comment(
    account_id: int,
    tracked: TrackedMessage | None,
    m: TgMessage,
    chat_id: int,
    chat_title: str | None,
    kind: str,
    link: str | None,
) -> Comment:
    return Comment(
        account_id=account_id,
        tracked_id=tracked.id if tracked else None,
        kind=kind,
        chat_id=chat_id,
        chat_title=chat_title,
        msg_id=m.id,
        reply_to_msg_id=m.reply_to_msg_id,
        sender_id=m.sender_id,
        sender_name=m.sender_name,
        sender_username=m.sender_username,
        text=m.text or "",
        link=link,
        date=m.date,
    )


def _reply_link(tm: TrackedMessage, r: TgMessage) -> str | None:
    if tm.is_comment:
        return comment_link(tm.parent_link, r.id)
    return tme_link(tm.chat_username, r.chat_id, r.id)


class MessageTracker:
    def __init__(self, clients: AccountClients, policies: Policies):
        self._clients = clients
        self._policies = policies

    async def track(
        self,
        uow: UnitOfWork,
        account_id: int,
        msg: TgMessage,
        chat: ChatInfo,
        *,
        source: str,
        task_id: int | None = None,
        is_comment: bool = False,
        parent_link: str | None = None,
        thread_top_id: int | None = None
    ) -> TrackedMessage:
        existing = await uow.tracked.find(account_id, msg.chat_id, msg.id)
        if existing:
            return existing
        link = comment_link(parent_link, msg.id) if is_comment else None
        tm = TrackedMessage(
            account_id=account_id,
            task_id=task_id,
            chat_id=msg.chat_id,
            chat_access_hash=chat.access_hash,
            chat_title=chat.title,
            chat_username=chat.username,
            msg_id=msg.id,
            thread_top_id=thread_top_id or msg.thread_root_id,
            is_comment=is_comment,
            parent_link=parent_link,
            link=link or tme_link(chat.username, msg.chat_id, msg.id),
            text=msg.text,
            source=source,
            sent_at=msg.date,
        )
        tm.apply_stats(
            views=msg.views,
            forwards=msg.forwards,
            reactions=msg.reactions,
            replies=msg.replies or 0,
        )
        uow.tracked.add(tm)
        await uow.commit()
        return tm

    async def refresh(
        self, uow: UnitOfWork, items: list[TrackedMessage], with_replies: bool = True
    ) -> dict:
        summary = {"refreshed": 0, "errors": 0, "new_comments": 0}
        by_account: dict[int, list[TrackedMessage]] = defaultdict(list)
        for tm in items:
            by_account[tm.account_id].append(tm)

        for account_id, tms in by_account.items():
            account = await uow.accounts.get(account_id)
            if not account:
                continue
            try:
                tg = await self._clients.session(uow, account)
            except AccountUnavailable as e:
                for tm in tms:
                    tm.refresh_error = str(e)
                summary["errors"] += len(tms)
                await uow.commit()
                continue

            by_chat: dict[int, list[TrackedMessage]] = defaultdict(list)
            for tm in tms:
                by_chat[tm.chat_id].append(tm)

            for group in by_chat.values():
                first = group[0]
                try:
                    async with self._clients.guard(uow, account):
                        msgs = await tg.fetch_by_ids(
                            first.chat_id,
                            first.chat_access_hash,
                            [tm.msg_id for tm in group],
                        )
                except DomainError as e:
                    for tm in group:
                        tm.refresh_error = str(e)
                    summary["errors"] += len(group)
                    await uow.commit()
                    continue

                for tm, m in zip(group, msgs):
                    tm.last_refreshed_at = utcnow()
                    if m is None:
                        tm.is_deleted = True
                        continue
                    replies: list[TgMessage] = []
                    error = None
                    if with_replies:
                        try:
                            replies = await tg.replies_to(
                                first.chat_id, first.chat_access_hash, m
                            )
                        except DomainError as e:
                            error = str(e)
                    comments = [
                        _comment(
                            account_id,
                            tm,
                            r,
                            r.chat_id,
                            tm.chat_title,
                            CommentKind.REPLY,
                            _reply_link(tm, r),
                        )
                        for r in replies
                        if not r.out
                    ]
                    summary["new_comments"] += await uow.comments.upsert_many(comments)
                    tm.refresh_error = error
                    tm.apply_stats(
                        views=m.views,
                        forwards=m.forwards,
                        reactions=m.reactions,
                        replies=max(m.replies or 0, len(comments)),
                    )
                    uow.tracked.add_snapshot(tm.snapshot())
                    summary["refreshed"] += 1
                await uow.commit()
        return summary

    async def scan_mentions(
        self,
        uow: UnitOfWork,
        tg: TelegramSession,
        account: Account,
        dialog_limit: int = 50,
        per_chat: int = 50,
    ) -> dict:
        tracked = {
            (tm.chat_id, tm.msg_id): tm
            for tm in await uow.tracked.by_account(account.id)
        }
        comments: list[Comment] = []
        chats = 0
        for d in await tg.dialogs(dialog_limit):
            if not d.is_group:
                continue
            chats += 1
            try:
                found = await tg.mentions(d.id, per_chat)
            except FloodWait as e:
                if e.seconds > self._policies.flood_wait_max:
                    break
                await asyncio.sleep(e.seconds + 1)
                continue
            except AccountDead:
                raise
            except TelegramError:
                continue
            for m in found:
                if m.out:
                    continue
                tm = (
                    tracked.get((d.id, m.reply_to_msg_id))
                    if m.reply_to_msg_id
                    else None
                )
                link = tme_link(d.username, d.id, m.id)
                if tm and tm.is_comment:
                    link = comment_link(tm.parent_link, m.id)
                kind = CommentKind.REPLY if tm else CommentKind.MENTION
                comments.append(_comment(account.id, tm, m, d.id, d.title, kind, link))
        saved = await uow.comments.upsert_many(comments)
        await uow.commit()
        return {"chats_scanned": chats, "found": len(comments), "saved": saved}

    async def refresh_recent(self, uow: UnitOfWork) -> dict | None:
        since = utcnow() - timedelta(days=self._policies.stats_refresh_days)
        items = await uow.tracked.for_refresh(since=since)
        return await self.refresh(uow, items) if items else None
