import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime

from app.application.policies import Policies
from app.application.ports.repositories import UnitOfWorkFactory
from app.application.ports.services import KeyValueStore
from app.application.services.archive import MessageArchive
from app.application.services.telegram_access import AccountClients
from app.domain.entities import ChatMessage, TgUser
from app.domain.errors import (
    AccountDead,
    Conflict,
    DomainError,
    FloodWait,
    NotFound,
    TelegramError,
)

log = logging.getLogger(__name__)


@dataclass
class Feed:
    items: list[ChatMessage]
    next_before_date: datetime | None = None
    next_before_id: int | None = None


@dataclass
class TgUserActivity:
    user: TgUser
    messages_count: int
    chats_count: int
    last_message_at: datetime | None


class SavedMessages:
    def __init__(
        self,
        uow: UnitOfWorkFactory,
        clients: AccountClients,
        archive: MessageArchive,
        kv: KeyValueStore,
        policies: Policies,
    ):
        self._uow = uow
        self._clients = clients
        self._archive = archive
        self._kv = kv
        self._policies = policies

    async def feed(self, *, limit: int = 50, **filters) -> Feed:
        limit = max(1, min(limit, 200))
        async with self._uow() as uow:
            rows = await uow.messages.feed(limit=limit, **filters)
        last = rows[-1] if len(rows) == limit else None
        return Feed(rows, last.date if last else None, last.id if last else None)

    async def chats(self, account_id: int | None = None) -> list[dict]:
        async with self._uow() as uow:
            return await uow.messages.saved_chats(account_id)

    async def summary(self, account_id: int | None = None) -> dict:
        async with self._uow() as uow:
            return await uow.messages.summary(account_id)

    async def get(self, message_id: int) -> ChatMessage:
        async with self._uow() as uow:
            m = await uow.messages.get(message_id)
        if not m:
            raise NotFound("Сообщение не найдено")
        return m

    async def users(self, q: str | None = None, limit: int = 50) -> list[TgUser]:
        async with self._uow() as uow:
            return await uow.tg_users.search(
                q.lstrip("@") if q else None, min(limit, 200)
            )

    async def user(self, user_id: int) -> TgUserActivity:
        async with self._uow() as uow:
            user = await uow.tg_users.get(user_id)
            if not user:
                raise NotFound("Пользователь не найден")
            count, chats, last = await uow.tg_users.activity(user_id)
        return TgUserActivity(user, count, chats, last)

    async def _sync_account(
        self, uow, account, dialog_limit: int, per_chat: int
    ) -> dict:
        tg = await self._clients.session(uow, account)
        last = await uow.messages.last_ids(account.id)
        res = {"account_id": account.id, "chats": 0, "new": 0, "errors": 0}
        async with self._clients.guard(uow, account):
            dialogs = await tg.dialogs(dialog_limit)
        for d in dialogs:
            have = last.get(d.id, 0)
            if not d.top_message_id or d.top_message_id <= have:
                continue
            try:
                async with self._clients.guard(uow, account):
                    _, inserted = await self._archive.fetch_new(
                        uow,
                        tg,
                        account.id,
                        d.id,
                        have,
                        per_chat if have else min(per_chat, 50),
                    )
            except FloodWait as e:
                if e.seconds > self._policies.flood_wait_max:
                    res["errors"] += 1
                    break
                await asyncio.sleep(e.seconds + 1)
                continue
            except AccountDead:
                raise
            except TelegramError:
                res["errors"] += 1
                continue
            res["chats"] += 1
            res["new"] += inserted
        return res

    async def sync_accounts(
        self,
        account_ids: list[int] | None = None,
        dialog_limit: int = 50,
        per_chat: int = 100,
    ) -> dict:
        async with self._uow() as uow:
            ids = await uow.accounts.usable_ids(account_ids)
        sem = asyncio.Semaphore(max(1, self._policies.bulk_concurrency))

        async def one(aid: int) -> dict:
            async with sem, self._uow() as uow:
                account = await uow.accounts.get(aid)
                try:
                    return await self._sync_account(
                        uow, account, dialog_limit, per_chat
                    )
                except DomainError as e:
                    return {
                        "account_id": aid,
                        "chats": 0,
                        "new": 0,
                        "errors": 1,
                        "error": str(e),
                    }

        results = await asyncio.gather(*(one(i) for i in ids))
        return {
            "accounts": len(ids),
            "chats": sum(r["chats"] for r in results),
            "new": sum(r["new"] for r in results),
            "errors": sum(r["errors"] for r in results),
            "details": results,
        }

    async def sync(
        self, account_id: int | None, dialog_limit: int, per_chat: int
    ) -> dict:
        if account_id:
            async with self._uow() as uow:
                await self._clients.account(uow, account_id)
        lock = f"messages:sync:{account_id or 'all'}"
        if not await self._kv.set(lock, "1", nx=True, ex=900):
            raise Conflict("Синхронизация уже выполняется")
        try:
            return await self.sync_accounts(
                [account_id] if account_id else None, dialog_limit, per_chat
            )
        finally:
            await self._kv.delete(lock)

    async def sync_periodically(self) -> None:
        minutes = self._policies.messages_sync_minutes
        if minutes <= 0:
            return
        while True:
            await asyncio.sleep(minutes * 60)
            if not await self._kv.set("messages:sync:lock", "1", nx=True, ex=1800):
                continue
            try:
                res = await self.sync_accounts(
                    dialog_limit=self._policies.messages_sync_dialogs
                )
                log.info("Messages sync: %s new in %s chats", res["new"], res["chats"])
            except Exception:  # noqa: BLE001
                log.exception("Messages sync failed")
            finally:
                await self._kv.delete("messages:sync:lock")
