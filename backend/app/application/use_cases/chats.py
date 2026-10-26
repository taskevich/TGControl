import asyncio
import json
from dataclasses import asdict
from datetime import datetime

from app.application.dto import Dialog, JoinResult, Page, TgMessage
from app.application.policies import Policies
from app.application.ports.repositories import UnitOfWorkFactory
from app.application.ports.services import KeyValueStore
from app.application.services.archive import MessageArchive
from app.application.services.telegram_access import AccountClients
from app.application.services.tracking import MessageTracker
from app.domain.entities import Account
from app.domain.errors import AccountDead, Conflict, DomainError, FloodWait
from app.domain.values import Target, parse_target


def _dump_dialogs(dialogs: list[Dialog]) -> str:
    return json.dumps([asdict(d) for d in dialogs], ensure_ascii=False, default=str)


def _load_dialogs(raw: str) -> list[Dialog]:
    items = json.loads(raw)
    for d in items:
        d["last_date"] = (
            datetime.fromisoformat(d["last_date"]) if d["last_date"] else None
        )
    return [Dialog(**d) for d in items]


class AccountChats:
    def __init__(
        self,
        uow: UnitOfWorkFactory,
        clients: AccountClients,
        archive: MessageArchive,
        tracker: MessageTracker,
        kv: KeyValueStore,
        policies: Policies,
    ):
        self._uow = uow
        self._clients = clients
        self._archive = archive
        self._tracker = tracker
        self._kv = kv
        self._policies = policies

    async def _invalidate_dialogs(self, account_id: int) -> None:
        await self._kv.delete(f"dialogs:{account_id}")

    async def dialogs(
        self, account_id: int, refresh: bool = False, limit: int = 300
    ) -> list[Dialog]:
        key = f"dialogs:{account_id}"
        if not refresh:
            cached = await self._kv.get(key)
            if cached:
                return _load_dialogs(cached)
        async with self._uow() as uow:
            account = await self._clients.account(uow, account_id)
            tg = await self._clients.session(uow, account)
            async with self._clients.guard(uow, account):
                dialogs = await tg.dialogs(min(limit, 2000))
        await self._kv.set(
            key, _dump_dialogs(dialogs), ex=self._policies.dialogs_cache_ttl
        )
        return dialogs

    async def history(
        self, account_id: int, peer_id: int, limit: int = 50, offset_id: int = 0
    ) -> list[TgMessage]:
        async with self._uow() as uow:
            account = await self._clients.account(uow, account_id)
            tg = await self._clients.session(uow, account)
            async with self._clients.guard(uow, account):
                return await self._archive.history(
                    uow, tg, account.id, peer_id, offset_id, min(limit, 200)
                )

    async def new_messages(
        self, account_id: int, peer_id: int, after_id: int, limit: int = 100
    ) -> tuple[list[TgMessage], int]:
        async with self._uow() as uow:
            account = await self._clients.account(uow, account_id)
            tg = await self._clients.session(uow, account)
            async with self._clients.guard(uow, account):
                return await self._archive.fetch_new(
                    uow, tg, account.id, peer_id, after_id, min(limit, 500)
                )

    async def send(
        self,
        account_id: int,
        peer_id: int,
        text: str,
        *,
        reply_to: int | None = None,
        track: bool = True,
        link_preview: bool = True,
    ) -> tuple[TgMessage, int | None]:
        async with self._uow() as uow:
            account = await self._clients.account(uow, account_id)
            tg = await self._clients.session(uow, account)
            async with self._clients.guard(uow, account):
                sent = await tg.send(
                    Target.by_id(peer_id),
                    text,
                    reply_to=reply_to,
                    link_preview=link_preview,
                )
            await self._archive.save(uow, account.id, sent.chat, [sent.message])
            tracked_id = None
            if track:
                tracked_id = (
                    await self._tracker.track(
                        uow, account.id, sent.message, sent.chat, source="panel"
                    )
                ).id
        await self._invalidate_dialogs(account_id)
        return sent.message, tracked_id

    async def send_to(
        self,
        account_id: int,
        target: str,
        text: str,
        *,
        track: bool = True,
        link_preview: bool = True,
    ) -> tuple[TgMessage, int | None]:
        async with self._uow() as uow:
            account = await self._clients.account(uow, account_id)
            tg = await self._clients.session(uow, account)
            async with self._clients.guard(uow, account):
                sent = await tg.send(
                    parse_target(target), text, link_preview=link_preview
                )
            tracked_id = None
            if track:
                tracked_id = (
                    await self._tracker.track(
                        uow, account.id, sent.message, sent.chat, source="panel"
                    )
                ).id
        return sent.message, tracked_id

    async def comment(
        self, account_id: int, post_link: str, text: str, join_if_needed: bool = False
    ) -> tuple[TgMessage, int, str | None]:
        async with self._uow() as uow:
            account = await self._clients.account(uow, account_id)
            tg = await self._clients.session(uow, account)
            async with self._clients.guard(uow, account):
                sent = await tg.comment(
                    parse_target(post_link), text, join_if_needed=join_if_needed
                )
            tm = await self._tracker.track(
                uow,
                account.id,
                sent.message,
                sent.chat,
                source="panel",
                is_comment=True,
                parent_link=post_link,
                thread_top_id=sent.thread_top_id,
            )
        return sent.message, tm.id, tm.link

    async def _membership(self, account_id: int, target: str, join: bool) -> JoinResult:
        async with self._uow() as uow:
            account = await self._clients.account(uow, account_id)
            tg = await self._clients.session(uow, account)
            async with self._clients.guard(uow, account):
                t = parse_target(target)
                res = await (tg.join(t) if join else tg.leave(t))
        await self._invalidate_dialogs(account_id)
        return res

    async def join(self, account_id: int, target: str) -> JoinResult:
        return await self._membership(account_id, target, join=True)

    async def leave(self, account_id: int, target: str) -> JoinResult:
        return await self._membership(account_id, target, join=False)

    async def replies(
        self, account_id: int, peer_id: int, msg_id: int
    ) -> list[TgMessage]:
        async with self._uow() as uow:
            account = await self._clients.account(uow, account_id)
            tg = await self._clients.session(uow, account)
            async with self._clients.guard(uow, account):
                found = await tg.replies(peer_id, msg_id)
        return sorted(found, key=lambda m: m.id)

    async def _read_account(self, uow, account: Account) -> dict:
        tg = await self._clients.session(uow, account)
        res = {
            "account_id": account.id,
            "dialogs": 0,
            "topics": 0,
            "messages": 0,
            "errors": 0,
        }
        async with self._clients.guard(uow, account):
            unread = await tg.unread_dialogs()
        for d in unread:
            try:
                res["topics"] += await self._read_dialog(uow, tg, account, d)
            except FloodWait as e:
                res["errors"] += 1
                res["error"] = str(e)
                break
            except AccountDead:
                raise
            except DomainError as e:
                res["errors"] += 1
                res["error"] = f"{d.title}: {e}"
                continue
            res["dialogs"] += 1
            res["messages"] += d.unread
        res["unread_dialogs"] = len(unread)
        await self._invalidate_dialogs(account.id)
        return res

    async def _read_dialog(self, uow, tg, account: Account, d: Dialog) -> int:
        try:
            async with self._clients.guard(uow, account):
                return await tg.read_dialog(d)
        except FloodWait as e:
            if e.seconds > self._policies.flood_wait_max:
                raise
            await asyncio.sleep(e.seconds + 1)
        async with self._clients.guard(uow, account):
            return await tg.read_dialog(d)

    async def read_all(self, account_id: int | None = None) -> dict:
        if account_id:
            async with self._uow() as uow:
                await self._clients.account(uow, account_id)
        lock = f"read-all:{account_id or 'all'}"
        if not await self._kv.set(lock, "1", nx=True, ex=1800):
            raise Conflict("Отметка прочитанного уже выполняется")
        try:
            async with self._uow() as uow:
                ids = await uow.accounts.usable_ids(
                    [account_id] if account_id else None
                )
            sem = asyncio.Semaphore(max(1, self._policies.bulk_concurrency))

            async def one(aid: int) -> dict:
                async with sem, self._uow() as uow:
                    account = await uow.accounts.get(aid)
                    try:
                        return await self._read_account(uow, account)
                    except DomainError as e:
                        if account_id:
                            raise
                        return {
                            "account_id": aid,
                            "dialogs": 0,
                            "topics": 0,
                            "messages": 0,
                            "errors": 1,
                            "error": str(e),
                        }

            results = await asyncio.gather(*(one(i) for i in ids))
        finally:
            await self._kv.delete(lock)
        if account_id and not results:
            raise Conflict("Аккаунт отключён")
        return {
            "accounts": len(ids),
            "dialogs": sum(r["dialogs"] for r in results),
            "topics": sum(r["topics"] for r in results),
            "messages": sum(r["messages"] for r in results),
            "errors": sum(r["errors"] for r in results),
            "details": results,
        }

    async def comments(
        self,
        account_id: int,
        kind: str | None = None,
        q: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Page:
        async with self._uow() as uow:
            await self._clients.account(uow, account_id)
            return await uow.comments.page(
                account_id=account_id, kind=kind, q=q, page=page, page_size=page_size
            )

    async def scan_comments(self, account_id: int, dialog_limit: int = 50) -> dict:
        async with self._uow() as uow:
            account = await self._clients.account(uow, account_id)
            tg = await self._clients.session(uow, account)
            tracked = await uow.tracked.by_account(account_id, include_deleted=False)
            refreshed = await self._tracker.refresh(uow, tracked) if tracked else {}
            async with self._clients.guard(uow, account):
                mentions = await self._tracker.scan_mentions(
                    uow, tg, account, dialog_limit=min(dialog_limit, 300)
                )
        return {"tracked": refreshed, "mentions": mentions}
