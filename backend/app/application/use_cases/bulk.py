import asyncio
import logging
import random

from app.application.dto import Page
from app.application.policies import Policies
from app.application.ports.repositories import UnitOfWork, UnitOfWorkFactory
from app.application.ports.services import KeyValueStore
from app.application.ports.telegram import TelegramSession
from app.application.services.telegram_access import AccountClients
from app.application.services.tracking import MessageTracker
from app.domain.entities import Account, BulkTask, BulkTaskItem, ItemStatus, TaskKind
from app.domain.errors import (
    AccountDead,
    AccountUnavailable,
    DomainError,
    FloodWait,
    NotFound,
    OperationSkipped,
)
from app.domain.values import parse_target

log = logging.getLogger(__name__)


class BulkTasks:
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
        self._running: dict[int, asyncio.Task] = {}

    @staticmethod
    async def _accounts(uow: UnitOfWork, params: dict) -> list[int]:
        return await uow.accounts.usable_ids(
            None if params.get("all_accounts") else params.get("account_ids", [])
        )

    async def create(self, kind: str, params: dict, created_by: str) -> BulkTask:
        async with self._uow() as uow:
            account_ids = await self._accounts(uow, params)
            if not account_ids:
                raise DomainError("Нет подходящих аккаунтов (включённых и активных)")
            task = BulkTask(
                kind=kind,
                params=params,
                total=len(account_ids) * len(params["targets"]),
                created_by=created_by,
            )
            await uow.tasks.add(task)
            await uow.commit()
        self._start(task.id)
        return task

    async def all(
        self, page: int = 1, page_size: int = 30, kind: str | None = None
    ) -> Page:
        async with self._uow() as uow:
            return await uow.tasks.page(kind, page, page_size)

    async def get(self, task_id: int) -> BulkTask:
        async with self._uow() as uow:
            task = await uow.tasks.get_with_items(task_id)
        if not task:
            raise NotFound("Задача не найдена")
        return task

    async def cancel(self, task_id: int) -> None:
        async with self._uow() as uow:
            task = await uow.tasks.get(task_id)
        if not task:
            raise NotFound("Задача не найдена")
        if not task.is_active:
            raise DomainError("Задача уже завершена")
        await self._kv.set(f"task:cancel:{task_id}", "1", ex=86400)

    async def delete(self, task_id: int) -> None:
        async with self._uow() as uow:
            task = await uow.tasks.get(task_id)
            if not task:
                raise NotFound("Задача не найдена")
            if task.is_active:
                raise DomainError("Сначала остановите задачу")
            await uow.tasks.delete(task)
            await uow.commit()

    async def mark_interrupted(self) -> None:
        async with self._uow() as uow:
            await uow.tasks.fail_active("Прервано перезапуском сервера")
            await uow.commit()

    def _start(self, task_id: int) -> None:
        t = asyncio.create_task(self._run(task_id))
        self._running[task_id] = t
        t.add_done_callback(lambda _: self._running.pop(task_id, None))

    async def _cancelled(self, task_id: int) -> bool:
        return await self._kv.exists(f"task:cancel:{task_id}")

    @staticmethod
    async def _record(
        uow: UnitOfWork,
        task_id: int,
        account_id: int,
        target: str,
        status: str,
        detail: str,
    ) -> None:
        await uow.tasks.add_item(
            BulkTaskItem(
                task_id=task_id,
                account_id=account_id,
                target=target,
                status=status,
                detail=detail[:2000],
            )
        )
        await uow.commit()

    async def _do_one(
        self,
        uow: UnitOfWork,
        task: BulkTask,
        account: Account,
        tg: TelegramSession,
        target: str,
    ) -> tuple[str, str]:
        p = task.params
        t = parse_target(target)
        if task.kind in (TaskKind.JOIN, TaskKind.LEAVE):
            res = await (tg.join(t) if task.kind == TaskKind.JOIN else tg.leave(t))
            return res.status, res.detail
        if task.kind == TaskKind.SEND:
            sent = await tg.send(
                t,
                p["text"],
                join_if_needed=p.get("join_if_needed", False),
                link_preview=p.get("link_preview", True),
            )
            tm = None
            if p.get("track", True):
                tm = await self._tracker.track(
                    uow,
                    account.id,
                    sent.message,
                    sent.chat,
                    source="bulk",
                    task_id=task.id,
                )
            return (
                ItemStatus.OK,
                f"Отправлено{': ' + tm.link if tm and tm.link else ''}",
            )
        if task.kind == TaskKind.COMMENT:
            sent = await tg.comment(
                t,
                p["text"],
                join_if_needed=p.get("join_if_needed", False),
                link_preview=p.get("link_preview", True),
            )
            tm = None
            if p.get("track", True):
                tm = await self._tracker.track(
                    uow,
                    account.id,
                    sent.message,
                    sent.chat,
                    source="bulk",
                    task_id=task.id,
                    is_comment=True,
                    parent_link=target,
                    thread_top_id=sent.thread_top_id,
                )
            return (
                ItemStatus.OK,
                f"Комментарий оставлен{': ' + tm.link if tm and tm.link else ''}",
            )
        raise DomainError(f"Неизвестный тип задачи: {task.kind}")

    async def _worker(
        self,
        task_id: int,
        account_id: int,
        targets: list[str],
        sem: asyncio.Semaphore,
        dmin: float,
        dmax: float,
    ) -> None:
        async with sem, self._uow() as uow:
            task = await uow.tasks.get(task_id)
            account = await uow.accounts.get(account_id)
            label = account.label if account else f"#{account_id}"
            try:
                if not account:
                    raise AccountUnavailable("Аккаунт удалён")
                tg = await self._clients.session(uow, account)
            except AccountUnavailable as e:
                for t in targets:
                    await self._record(
                        uow, task_id, account_id, t, ItemStatus.ERROR, f"{label}: {e}"
                    )
                return

            for i, target in enumerate(targets):
                if await self._cancelled(task_id):
                    return
                status, detail = ItemStatus.ERROR, ""
                for attempt in range(2):
                    try:
                        async with self._clients.guard(uow, account):
                            status, detail = await self._do_one(
                                uow, task, account, tg, target
                            )
                    except OperationSkipped as e:
                        status, detail = ItemStatus.SKIPPED, str(e)
                    except FloodWait as e:
                        if attempt == 0 and e.seconds <= self._policies.flood_wait_max:
                            await asyncio.sleep(e.seconds + 1)
                            continue
                        status, detail = ItemStatus.ERROR, str(e)
                    except AccountDead as e:
                        await self._record(
                            uow, task_id, account_id, target, ItemStatus.ERROR, str(e)
                        )
                        for rest in targets[i + 1 :]:
                            await self._record(
                                uow,
                                task_id,
                                account_id,
                                rest,
                                ItemStatus.ERROR,
                                "Аккаунт стал недоступен",
                            )
                        return
                    except DomainError as e:
                        status, detail = ItemStatus.ERROR, str(e)
                    break
                await self._record(uow, task_id, account_id, target, status, detail)
                if i < len(targets) - 1 and status != ItemStatus.SKIPPED:
                    await asyncio.sleep(random.uniform(dmin, max(dmin, dmax)))

    async def _run(self, task_id: int) -> None:
        try:
            async with self._uow() as uow:
                task = await uow.tasks.get(task_id)
                p = task.params
                account_ids = await self._accounts(uow, p)
                targets = task.targets
                task.start(len(account_ids) * len(targets))
                await uow.commit()
            dmin = (
                p["delay_min"]
                if p.get("delay_min") is not None
                else self._policies.bulk_delay_min
            )
            dmax = (
                p["delay_max"]
                if p.get("delay_max") is not None
                else self._policies.bulk_delay_max
            )

            sem = asyncio.Semaphore(max(1, self._policies.bulk_concurrency))
            results = await asyncio.gather(
                *(
                    self._worker(task_id, aid, targets, sem, dmin, dmax)
                    for aid in account_ids
                ),
                return_exceptions=True,
            )
            for r in results:
                if isinstance(r, Exception):
                    log.error("Bulk task %s worker error: %r", task_id, r)
            async with self._uow() as uow:
                task = await uow.tasks.get(task_id)
                task.finish(cancelled=await self._cancelled(task_id))
                await uow.commit()
        except Exception as e:  # noqa: BLE001
            log.exception("Bulk task %s failed", task_id)
            async with self._uow() as uow:
                task = await uow.tasks.get(task_id)
                if task:
                    task.fail(
                        str(e)
                        if isinstance(e, DomainError)
                        else f"{type(e).__name__}: {e}"
                    )
                    await uow.commit()
