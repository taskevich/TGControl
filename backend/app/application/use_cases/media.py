import asyncio
import logging
import re
import shutil
import tempfile
import time
import uuid
from dataclasses import dataclass

from app.application.policies import Policies
from app.application.ports.repositories import UnitOfWorkFactory
from app.application.ports.services import (
    FileStorage,
    KeyValueStore,
    Signer,
    StoredObject,
)
from app.application.services.telegram_access import AccountClients
from app.domain.entities import ChatMessage, MediaStatus
from app.domain.errors import (
    AccountDead,
    AccountUnavailable,
    AuthenticationFailed,
    Conflict,
    DomainError,
    FloodWait,
    MediaTooLarge,
    NotFound,
)

log = logging.getLogger(__name__)

BATCH = 20
IDLE_SECONDS = 30
LOCK = "media:worker"
FILE_TIMEOUT = 1800
LOCK_TTL = 120


@dataclass
class OpenedFile:
    message: ChatMessage
    content: StoredObject

    @property
    def file_name(self) -> str:
        m = self.message
        return m.media_name or (m.media_key or "file").rsplit("/", 1)[-1]


def _safe_name(name: str) -> str:
    name = re.sub(r"[^\w.\-]+", "_", name, flags=re.UNICODE).strip("._")
    return name[:120] or "file"


def object_key(m: ChatMessage, file_name: str) -> str:
    return f"{m.account_id}/{m.chat_id}/{m.msg_id}/{_safe_name(file_name)}"


class MediaFiles:
    def __init__(
        self,
        uow: UnitOfWorkFactory,
        clients: AccountClients,
        storage: FileStorage | None,
        signer: Signer,
        kv: KeyValueStore,
        policies: Policies,
        tmp_dir: str | None = None,
    ):
        self._uow = uow
        self._signer = signer
        self._clients = clients
        self._storage = storage
        self._kv = kv
        self._policies = policies
        self._tmp_dir = tmp_dir or None

    @property
    def enabled(self) -> bool:
        return self._storage is not None

    @property
    def max_size(self) -> int | None:
        return self._policies.media_max_size if self.enabled else None

    def _require(self) -> FileStorage:
        if self._storage is None:
            raise Conflict("Хранилище файлов не настроено (S3_BUCKET в .env)")
        return self._storage

    def url_for(self, m: ChatMessage) -> str | None:
        if (
            self._storage is None
            or m.media_status != MediaStatus.STORED
            or m.id is None
        ):
            return None
        ttl = self._policies.media_link_ttl
        exp = (int(time.time()) // ttl + 2) * ttl
        return f"/api/files/{m.id}?exp={exp}&sig={self._signer.sign(f'{m.id}:{exp}')}"

    async def open(
        self, message_id: int, exp: int, sig: str, byte_range: str | None = None
    ) -> OpenedFile:
        storage = self._require()
        if exp < time.time() or not self._signer.verify(f"{message_id}:{exp}", sig):
            raise AuthenticationFailed("Ссылка на файл недействительна или устарела")
        async with self._uow() as uow:
            m = await uow.messages.get(message_id)
        if not m or m.media_status != MediaStatus.STORED or not m.media_key:
            raise NotFound("Файл сообщения не сохранён")
        return OpenedFile(m, await storage.open(m.media_key, byte_range))

    async def stats(
        self, account_id: int | None = None, days: int | None = None
    ) -> dict:
        async with self._uow() as uow:
            res = await uow.messages.media_stats(account_id, days)
        return {
            **res,
            "enabled": self.enabled,
            "max_size": self._policies.media_max_size,
        }

    async def retry(self, message_id: int) -> ChatMessage:
        self._require()
        async with self._uow() as uow:
            m = await uow.messages.get(message_id)
            if not m:
                raise NotFound("Сообщение не найдено")
            m.queue_media()
            await uow.commit()
            return m

    async def prepare(self) -> None:
        if self._storage is None:
            return
        await self._storage.prepare()
        async with self._uow() as uow:
            queued = await uow.messages.queue_unqueued_media()
            await uow.commit()
        if queued:
            log.info("Media: queued %s files of earlier saved messages", queued)

    async def run_periodically(self) -> None:
        if self._storage is None:
            return
        prepared = False
        while True:
            done = 0
            try:
                if not prepared:
                    try:
                        await self.prepare()
                    except Exception as e:  # noqa: BLE001
                        log.warning("Media storage is not available yet: %s", e)
                        await asyncio.sleep(IDLE_SECONDS)
                        continue
                    prepared = True
                done = await self._run_batch()
                if done:
                    log.info("Media: %s files processed", done)
            except asyncio.CancelledError:
                if asyncio.current_task().cancelling():
                    raise
                log.warning("Media worker: a request was cancelled, continuing")
            except Exception:  # noqa: BLE001
                log.exception("Media worker failed")
            if not done:
                await asyncio.sleep(IDLE_SECONDS)

    async def _keep_lock(self, owner: str) -> None:
        while True:
            await asyncio.sleep(LOCK_TTL / 3)
            if await self._kv.get(LOCK) != owner:
                return
            await self._kv.set(LOCK, owner, ex=LOCK_TTL)

    async def _run_batch(self) -> int:
        owner = uuid.uuid4().hex
        if not await self._kv.set(LOCK, owner, nx=True, ex=LOCK_TTL):
            return 0
        keeper = asyncio.create_task(self._keep_lock(owner))
        try:
            async with self._uow() as uow:
                batch = await uow.messages.pending_media(BATCH)
            by_account: dict[int, list[int]] = {}
            for m in batch:
                by_account.setdefault(m.account_id, []).append(m.id)
            sem = asyncio.Semaphore(max(1, self._policies.media_concurrency))

            async def account_queue(ids: list[int]) -> int:
                done = 0
                for mid in ids:
                    async with sem, self._uow() as uow:
                        m = await uow.messages.get(mid)
                        if m and m.media_status == MediaStatus.PENDING:
                            if not await self._store_in_time(uow, m):
                                break
                    done += 1
                return done

            return sum(
                await asyncio.gather(
                    *(account_queue(ids) for ids in by_account.values())
                )
            )
        finally:
            keeper.cancel()
            if await self._kv.get(LOCK) == owner:
                await self._kv.delete(LOCK)

    async def _store_in_time(self, uow, m: ChatMessage) -> bool:
        try:
            return await asyncio.wait_for(self._store(uow, m), FILE_TIMEOUT)
        except TimeoutError:
            log.warning(
                "Media of message %s: no progress in %s s, postponed",
                m.id,
                FILE_TIMEOUT,
            )
            await self._clients.drop(m.account_id)  # the connection is probably stuck
            return False

    async def _store(self, uow, m: ChatMessage) -> bool:
        storage = self._require()
        tmp = tempfile.mkdtemp(prefix="tgmedia-", dir=self._tmp_dir)
        try:
            account = await self._clients.account(uow, m.account_id)
            tg = await self._clients.session(uow, account)
            async with self._clients.guard(uow, account):
                f = await tg.download_media(
                    m.chat_id, m.msg_id, tmp, self._policies.media_max_size
                )
            if f.size > self._policies.media_max_size:
                raise MediaTooLarge(f.size, self._policies.media_max_size)
            key = object_key(m, f.file_name)
            await storage.put_file(key, f.path, f.mime)
            m.media_stored(key, f.size, f.mime, f.file_name)
            await uow.commit()
            return True
        except MediaTooLarge as e:
            m.media_size = e.size
            m.media_skipped(MediaStatus.TOO_LARGE, str(e))
        except (FloodWait, AccountUnavailable, AccountDead) as e:
            log.info("Media of account %s postponed: %s", m.account_id, e)
            return False
        except DomainError as e:
            m.media_skipped(MediaStatus.FAILED, str(e))
        except Exception as e:  # noqa: BLE001
            log.warning("Media of message %s postponed, storage error: %s", m.id, e)
            return False
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        await uow.commit()
        return True
