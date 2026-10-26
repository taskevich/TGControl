import asyncio
import logging
from dataclasses import dataclass
from datetime import timedelta

from app.application.dto import Page
from app.application.policies import Policies
from app.application.ports.repositories import UnitOfWorkFactory
from app.application.ports.services import KeyValueStore
from app.application.services.telegram_access import AccountClients
from app.application.services.tracking import MessageTracker
from app.domain.entities import Comment, MessageStatSnapshot, TrackedMessage, utcnow
from app.domain.errors import NotFound

log = logging.getLogger(__name__)

REFRESH_LIMIT = 300


@dataclass
class TrackedDetails:
    message: TrackedMessage
    snapshots: list[MessageStatSnapshot]
    comments: list[Comment]


class Statistics:
    def __init__(
        self,
        uow: UnitOfWorkFactory,
        clients: AccountClients,
        tracker: MessageTracker,
        kv: KeyValueStore,
        policies: Policies,
    ):
        self._uow = uow
        self._clients = clients
        self._tracker = tracker
        self._kv = kv
        self._policies = policies

    async def summary(self, days: int = 14, account_id: int | None = None) -> dict:
        async with self._uow() as uow:
            data = await uow.stats.summary(days, account_id)
        return {**data, "auto_refresh_minutes": self._policies.stats_refresh_minutes}

    async def chat_messages(
        self, account_id: int | None = None, days: int = 14, top: int = 10
    ) -> dict:
        days = max(1, min(days, 365))
        top = max(1, min(top, 50))
        async with self._uow() as uow:
            return {
                "days": days,
                **await uow.stats.chat_messages(days, top, account_id),
            }

    async def tracked(self, **filters) -> Page:
        async with self._uow() as uow:
            return await uow.tracked.page(**filters)

    async def details(self, tracked_id: int) -> TrackedDetails:
        async with self._uow() as uow:
            tm = await uow.tracked.get_with_snapshots(tracked_id)
            if not tm:
                raise NotFound("Сообщение не найдено")
            return TrackedDetails(
                tm, list(tm.snapshots), await uow.comments.for_tracked(tracked_id)
            )

    async def refresh(self, ids: list[int], account_id: int | None = None) -> dict:
        since = (
            None
            if ids
            else utcnow() - timedelta(days=self._policies.stats_refresh_days)
        )
        async with self._uow() as uow:
            items = await uow.tracked.for_refresh(
                ids=ids or None, since=since, account_id=account_id, limit=REFRESH_LIMIT
            )
            if not items:
                return {"refreshed": 0, "errors": 0, "new_comments": 0}
            return await self._tracker.refresh(uow, items)

    async def track_link(self, account_id: int, link: str) -> TrackedMessage:
        async with self._uow() as uow:
            account = await self._clients.account(uow, account_id)
            tg = await self._clients.session(uow, account)
            async with self._clients.guard(uow, account):
                found = await tg.locate(link)
            tm = await self._tracker.track(
                uow,
                account.id,
                found.message,
                found.chat,
                source="manual",
                is_comment=found.is_comment,
                parent_link=found.parent_link,
                thread_top_id=found.thread_top_id,
            )
            await self._tracker.refresh(uow, [tm])
            return tm

    async def untrack(self, tracked_id: int) -> None:
        async with self._uow() as uow:
            tm = await uow.tracked.get(tracked_id)
            if not tm:
                raise NotFound("Сообщение не найдено")
            await uow.tracked.delete(tm)
            await uow.commit()

    async def comments(self, **filters) -> Page:
        async with self._uow() as uow:
            return await uow.comments.page(**filters)

    async def refresh_periodically(self) -> None:
        minutes = self._policies.stats_refresh_minutes
        if minutes <= 0:
            return
        while True:
            await asyncio.sleep(minutes * 60)
            if not await self._kv.set("stats:refresh:lock", "1", nx=True, ex=1800):
                continue
            try:
                async with self._uow() as uow:
                    res = await self._tracker.refresh_recent(uow)
                if res:
                    log.info("Auto stats refresh: %s", res)
            except Exception:  # noqa: BLE001
                log.exception("Auto stats refresh failed")
            finally:
                await self._kv.delete("stats:refresh:lock")
