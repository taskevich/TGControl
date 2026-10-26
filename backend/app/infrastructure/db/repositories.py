"""SQLAlchemy implementations of the persistence ports.

Queries work with the ORM models (models.py); results are handed out as domain entities (mapper.py).
"""

from datetime import datetime, timedelta

from sqlalchemy import Date, and_, case, cast, func, literal_column, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.application.dto import ChatInfo, Page, TgMessage, TgUserInfo
from app.domain.entities import (
    ACTIVE_TASK_STATUSES,
    STORABLE_MEDIA,
    USABLE_STATUSES,
    Account,
    BulkTask,
    BulkTaskItem,
    ChatMessage,
    Comment,
    ItemStatus,
    MediaStatus,
    MessageStatSnapshot,
    PanelUser,
    Proxy,
    ProxyStatus,
    TaskStatus,
    TgUser,
    TrackedMessage,
    initial_media_status,
    utcnow,
)
from app.infrastructure.db.mapper import EntityTracker
from app.infrastructure.db.models import (
    AccountModel,
    BulkTaskModel,
    CommentModel,
    MessageModel,
    PanelUserModel,
    ProxyModel,
    TgUserModel,
    TrackedMessageModel,
)

CHUNK = 300  # rows per multi-row INSERT (asyncpg bind parameter limit)
USABLE = [str(s) for s in USABLE_STATUSES]


class _Repo:
    """Queries return ORM models; `_one` / `_all` turn them into domain entities tracked by the unit of work."""

    def __init__(self, db: AsyncSession, tracker: EntityTracker):
        self.db = db
        self._t = tracker

    async def _get(self, model_cls, ident):
        self._t.sync()
        return self._t.entity(await self.db.get(model_cls, ident))

    async def _one(self, stmt):
        self._t.sync()  # entity changes must be visible to the query (autoflush)
        return self._t.entity(await self.db.scalar(stmt))

    async def _all(self, stmt) -> list:
        self._t.sync()
        return self._t.entities((await self.db.scalars(stmt)).unique().all())

    async def _page(self, stmt, order_by, page: int, page_size: int) -> Page:
        self._t.sync()
        total = await self.db.scalar(select(func.count()).select_from(stmt.subquery()))
        items = await self._all(stmt.order_by(*order_by).offset((page - 1) * page_size).limit(page_size))
        return Page(items=items, total=total or 0)

    def _add(self, entity) -> None:
        self._t.add(entity)

    async def _delete(self, entity) -> None:
        await self.db.delete(self._t.model(entity))
        self._t.forget(entity)


# ---------------------------------------------------------------- panel users
class SqlPanelUserRepository(_Repo):
    async def get(self, user_id: int) -> PanelUser | None:
        return await self._get(PanelUserModel, user_id)

    async def by_username(self, username: str) -> PanelUser | None:
        return await self._one(select(PanelUserModel).where(PanelUserModel.username == username))

    async def all(self) -> list[PanelUser]:
        return await self._all(select(PanelUserModel).order_by(PanelUserModel.id))

    async def count(self) -> int:
        return await self.db.scalar(select(func.count(PanelUserModel.id))) or 0

    def add(self, user: PanelUser) -> None:
        self._add(user)

    async def delete(self, user: PanelUser) -> None:
        await self._delete(user)


# ---------------------------------------------------------------- accounts
class SqlAccountRepository(_Repo):
    async def get(self, account_id: int) -> Account | None:
        return await self._get(AccountModel, account_id)

    async def by_tg_id(self, tg_id: int) -> Account | None:
        return await self._one(select(AccountModel).where(AccountModel.tg_id == tg_id))

    async def all(self, status: str | None = None) -> list[Account]:
        q = select(AccountModel).order_by(AccountModel.id)
        if status:
            q = q.where(AccountModel.status == status)
        return await self._all(q)

    async def enabled_ids(self) -> list[int]:
        return list((await self.db.scalars(select(AccountModel.id).where(AccountModel.is_enabled.is_(True)))).all())

    async def usable_ids(self, account_ids: list[int] | None) -> list[int]:
        self._t.sync()
        q = select(AccountModel.id).where(AccountModel.is_enabled.is_(True))
        if account_ids is None:
            q = q.where(AccountModel.status.in_(USABLE))
        else:
            q = q.where(AccountModel.id.in_(account_ids or [-1]))
        return list((await self.db.scalars(q.order_by(AccountModel.id))).all())

    async def without_proxy(self, account_ids: list[int]) -> list[Account]:
        q = select(AccountModel).where(AccountModel.proxy_id.is_(None)).order_by(AccountModel.id)
        if account_ids:
            q = q.where(AccountModel.id.in_(account_ids))
        return await self._all(q)

    async def ids_by_proxy(self, proxy_id: int) -> list[int]:
        self._t.sync()
        return list((await self.db.scalars(select(AccountModel.id).where(AccountModel.proxy_id == proxy_id))).all())

    async def count_by_proxy(self) -> dict[int, int]:
        self._t.sync()
        rows = await self.db.execute(
            select(AccountModel.proxy_id, func.count(AccountModel.id))
            .where(AccountModel.proxy_id.is_not(None))
            .group_by(AccountModel.proxy_id)
        )
        return dict(rows.all())

    def add(self, account: Account) -> None:
        self._add(account)

    async def delete(self, account: Account) -> None:
        await self._delete(account)

    async def load_proxy(self, account: Account) -> None:
        await self._t.refresh_relationship(account, "proxy")


# ---------------------------------------------------------------- proxies
class SqlProxyRepository(_Repo):
    async def get(self, proxy_id: int) -> Proxy | None:
        return await self._get(ProxyModel, proxy_id)

    async def all(self) -> list[Proxy]:
        return await self._all(select(ProxyModel).order_by(ProxyModel.id))

    async def ids(self) -> list[int]:
        return list((await self.db.scalars(select(ProxyModel.id))).all())

    async def find(self, scheme: str, host: str, port: int, username: str | None) -> Proxy | None:
        P = ProxyModel
        q = select(P).where(P.scheme == scheme, P.host == host, P.port == port)
        q = q.where(P.username == username) if username else q.where(P.username.is_(None))
        return await self._one(q)

    async def active(self, only_working: bool) -> list[Proxy]:
        q = select(ProxyModel).where(ProxyModel.is_active.is_(True))
        if only_working:
            q = q.where(ProxyModel.status == ProxyStatus.OK)
        return await self._all(q)

    async def add(self, proxy: Proxy) -> None:
        self._add(proxy)
        await self.db.flush()

    async def delete(self, proxy: Proxy) -> None:
        await self._delete(proxy)


# ---------------------------------------------------------------- bulk tasks
class SqlBulkTaskRepository(_Repo):
    async def get(self, task_id: int) -> BulkTask | None:
        return await self._get(BulkTaskModel, task_id)

    async def get_with_items(self, task_id: int) -> BulkTask | None:
        return await self._one(
            select(BulkTaskModel).where(BulkTaskModel.id == task_id).options(selectinload(BulkTaskModel.items))
        )

    async def page(self, kind: str | None, page: int, page_size: int) -> Page:
        stmt = select(BulkTaskModel)
        if kind:
            stmt = stmt.where(BulkTaskModel.kind == kind)
        return await self._page(stmt, [BulkTaskModel.id.desc()], page, page_size)

    async def add(self, task: BulkTask) -> None:
        self._add(task)
        await self.db.flush()

    async def delete(self, task: BulkTask) -> None:
        await self._delete(task)

    async def add_item(self, item: BulkTaskItem) -> None:
        self._add(item)
        T = BulkTaskModel
        counters = {"done": T.done + 1}
        if item.status == ItemStatus.OK:
            counters["success"] = T.success + 1
        elif item.status == ItemStatus.SKIPPED:
            counters["skipped"] = T.skipped + 1
        else:
            counters["failed"] = T.failed + 1
        await self.db.execute(update(T).where(T.id == item.task_id).values(**counters))

    async def fail_active(self, error: str) -> None:
        await self.db.execute(
            update(BulkTaskModel)
            .where(BulkTaskModel.status.in_([str(s) for s in ACTIVE_TASK_STATUSES]))
            .values(status=TaskStatus.FAILED, error=error, finished_at=utcnow())
        )


# ---------------------------------------------------------------- tracked messages
TRACKED_SORTS = {"sent_at": "sent_at", "views": "views", "reactions": "reactions_total", "replies": "replies_count"}


class SqlTrackedMessageRepository(_Repo):
    async def get(self, tracked_id: int) -> TrackedMessage | None:
        return await self._get(TrackedMessageModel, tracked_id)

    async def get_with_snapshots(self, tracked_id: int) -> TrackedMessage | None:
        T = TrackedMessageModel
        return await self._one(select(T).where(T.id == tracked_id).options(selectinload(T.snapshots)))

    async def find(self, account_id: int, chat_id: int, msg_id: int) -> TrackedMessage | None:
        T = TrackedMessageModel
        return await self._one(select(T).where(T.account_id == account_id, T.chat_id == chat_id, T.msg_id == msg_id))

    async def by_account(self, account_id: int, include_deleted: bool = True) -> list[TrackedMessage]:
        T = TrackedMessageModel
        q = select(T).where(T.account_id == account_id)
        if not include_deleted:
            q = q.where(T.is_deleted.is_(False))
        return await self._all(q)

    async def for_refresh(self, *, ids: list[int] | None = None, since: datetime | None = None,
                          account_id: int | None = None, limit: int | None = None) -> list[TrackedMessage]:
        T = TrackedMessageModel
        q = select(T).where(T.is_deleted.is_(False))
        if ids:
            q = q.where(T.id.in_(ids))
        elif since is not None:
            q = q.where(T.sent_at >= since)
        if account_id:
            q = q.where(T.account_id == account_id)
        q = q.order_by(T.id.desc())
        if limit:
            q = q.limit(limit)
        return await self._all(q)

    async def page(self, *, account_id: int | None, source: str | None, comments_only: bool, q: str | None,
                   sort: str, order: str, page: int, page_size: int) -> Page:
        T = TrackedMessageModel
        stmt = select(T)
        if account_id:
            stmt = stmt.where(T.account_id == account_id)
        if source:
            stmt = stmt.where(T.source == source)
        if comments_only:
            stmt = stmt.where(T.is_comment.is_(True))
        if q:
            like = f"%{q}%"
            stmt = stmt.where(T.text.ilike(like) | T.chat_title.ilike(like))
        col = getattr(T, TRACKED_SORTS.get(sort, "sent_at"))
        col = col.asc().nullsfirst() if order == "asc" else col.desc().nullslast()
        return await self._page(stmt, [col, T.id.desc()], page, page_size)

    def add(self, tm: TrackedMessage) -> None:
        self._add(tm)

    def add_snapshot(self, snapshot: MessageStatSnapshot) -> None:
        self._add(snapshot)

    async def delete(self, tm: TrackedMessage) -> None:
        await self._delete(tm)


# ---------------------------------------------------------------- comments
COMMENT_COLUMNS = ("account_id", "tracked_id", "kind", "chat_id", "chat_title", "msg_id", "reply_to_msg_id",
                   "sender_id", "sender_name", "sender_username", "text", "link", "date", "created_at")


class SqlCommentRepository(_Repo):
    async def upsert_many(self, comments: list[Comment]) -> int:
        C = CommentModel
        rows = [{c: getattr(x, c) for c in COMMENT_COLUMNS} for x in comments]
        total = 0
        for i in range(0, len(rows), CHUNK):
            stmt = pg_insert(C).values(rows[i : i + CHUNK])
            stmt = stmt.on_conflict_do_update(
                constraint="uq_comment_msg",
                set_={
                    "text": stmt.excluded.text,
                    "tracked_id": func.coalesce(stmt.excluded.tracked_id, C.tracked_id),
                    "kind": case((stmt.excluded.tracked_id.is_(None), C.kind), else_=stmt.excluded.kind),
                },
            )
            res = await self.db.execute(stmt)
            total += res.rowcount or 0
        return total

    async def page(self, *, account_id: int | None, kind: str | None, q: str | None,
                   page: int, page_size: int) -> Page:
        C = CommentModel
        stmt = select(C)
        if account_id:
            stmt = stmt.where(C.account_id == account_id)
        if kind:
            stmt = stmt.where(C.kind == kind)
        if q:
            stmt = stmt.where(C.text.ilike(f"%{q}%"))
        return await self._page(stmt, [C.date.desc().nullslast()], page, page_size)

    async def for_tracked(self, tracked_id: int) -> list[Comment]:
        C = CommentModel
        return await self._all(select(C).where(C.tracked_id == tracked_id).order_by(C.date))


# ---------------------------------------------------------------- saved chat messages
def _cut(value: str | None, size: int = 255) -> str | None:
    return (value or "")[:size] or None


def _message_row(account_id: int, chat: ChatInfo, m: TgMessage, max_media_size: int | None) -> dict:
    now = utcnow()
    return {
        "account_id": account_id,
        "chat_id": m.chat_id,
        "chat_title": _cut(chat.title),
        "chat_username": chat.username,
        "chat_type": chat.type,
        "msg_id": m.id,
        "sender_id": m.sender_id,
        "tg_user_id": m.sender_user.id if m.sender_user else None,
        "sender_name": _cut(m.sender_name),
        "out": m.out,
        "is_service": m.is_service,
        "text": m.text or "",
        "media": m.media,
        "media_size": m.media_size,
        "media_mime": _cut(m.media_mime, 128),
        "media_name": _cut(m.media_name),
        "media_status": initial_media_status(m.media, m.media_size, max_media_size) if max_media_size else None,
        "reply_to_msg_id": m.reply_to_msg_id,
        "thread_top_id": m.reply_to_top_id,
        "grouped_id": m.grouped_id,
        "views": m.views,
        "forwards": m.forwards,
        "replies": m.replies,
        "reactions": m.reactions,
        "reactions_total": m.reactions_total,
        "date": m.date,
        "edit_date": m.edit_date,
        "created_at": now,
        "updated_at": now,
    }


class SqlChatMessageRepository(_Repo):
    async def upsert(self, account_id: int, chat: ChatInfo, messages: list[TgMessage],
                     max_media_size: int | None = None) -> int:
        M = MessageModel
        rows = [_message_row(account_id, chat, m, max_media_size) for m in messages]
        inserted = 0
        for i in range(0, len(rows), CHUNK):
            stmt = pg_insert(M).values(rows[i : i + CHUNK])
            ex = stmt.excluded
            stmt = stmt.on_conflict_do_update(
                constraint="uq_message",
                set_={
                    "chat_title": ex.chat_title,
                    "chat_username": ex.chat_username,
                    "text": ex.text,
                    "media": ex.media,
                    "media_size": func.coalesce(ex.media_size, M.media_size),
                    "media_mime": func.coalesce(ex.media_mime, M.media_mime),
                    "media_name": func.coalesce(ex.media_name, M.media_name),
                    # rows saved before the storage was configured get queued once it is
                    "media_status": func.coalesce(M.media_status, ex.media_status),
                    "sender_name": func.coalesce(ex.sender_name, M.sender_name),
                    "tg_user_id": func.coalesce(ex.tg_user_id, M.tg_user_id),
                    "views": ex.views,
                    "forwards": ex.forwards,
                    "replies": ex.replies,
                    "reactions": ex.reactions,
                    "reactions_total": ex.reactions_total,
                    "edit_date": ex.edit_date,
                    "updated_at": ex.updated_at,
                },
            ).returning(literal_column("(xmax = 0)"))
            result = await self.db.execute(stmt)
            inserted += sum(1 for (is_new,) in result.all() if is_new)
        return inserted

    async def last_ids(self, account_id: int) -> dict[int, int]:
        M = MessageModel
        rows = await self.db.execute(
            select(M.chat_id, func.max(M.msg_id)).where(M.account_id == account_id).group_by(M.chat_id)
        )
        return dict(rows.all())

    async def get(self, message_id: int) -> ChatMessage | None:
        return await self._get(MessageModel, message_id)

    async def feed(self, *, account_id: int | None = None, chat_id: int | None = None, sender_id: int | None = None,
                   q: str | None = None, out: bool | None = None, chat_type: str | None = None,
                   with_media: bool | None = None, media_status: str | None = None, media_kind: str | None = None,
                   before_date: datetime | None = None, before_id: int | None = None, after_id: int | None = None,
                   limit: int = 50) -> list[ChatMessage]:
        M = MessageModel
        stmt = select(M)
        if account_id:
            stmt = stmt.where(M.account_id == account_id)
        if chat_id:
            stmt = stmt.where(M.chat_id == chat_id)
        if sender_id:
            stmt = stmt.where(M.sender_id == sender_id)
        if out is not None:
            stmt = stmt.where(M.out.is_(out))
        if chat_type:
            stmt = stmt.where(M.chat_type == chat_type)
        if with_media:
            stmt = stmt.where(M.media.is_not(None))
        if media_status == "any":  # every message with a file
            stmt = stmt.where(M.media_status.is_not(None))
        elif media_status == "not_stored":
            stmt = stmt.where(M.media_status.in_([MediaStatus.FAILED, MediaStatus.TOO_LARGE]))
        elif media_status:
            stmt = stmt.where(M.media_status == media_status)
        if media_kind:
            stmt = stmt.where(M.media == media_kind)
        if q:
            like = f"%{q}%"
            stmt = stmt.where(or_(M.text.ilike(like), M.sender_name.ilike(like), M.chat_title.ilike(like),
                                  M.media_name.ilike(like)))
        if after_id:
            stmt = stmt.where(M.id > after_id)
        if before_date is not None and before_id is not None:
            stmt = stmt.where(or_(M.date < before_date, and_(M.date == before_date, M.id < before_id)))
        stmt = stmt.order_by(M.date.desc().nullslast(), M.id.desc()).limit(limit)
        return await self._all(stmt)

    async def saved_chats(self, account_id: int | None) -> list[dict]:
        M = MessageModel
        stmt = (
            select(M.account_id, M.chat_id, func.max(M.chat_title), func.max(M.chat_username), func.max(M.chat_type),
                   func.count(M.id), func.max(M.date))
            .group_by(M.account_id, M.chat_id)
            .order_by(func.max(M.date).desc().nullslast())
        )
        if account_id:
            stmt = stmt.where(M.account_id == account_id)
        return [
            {"account_id": a, "chat_id": c, "chat_title": t, "chat_username": u, "chat_type": ty, "count": n,
             "last_date": d}
            for a, c, t, u, ty, n, d in (await self.db.execute(stmt)).all()
        ]

    async def summary(self, account_id: int | None) -> dict:
        M = MessageModel
        where = [M.account_id == account_id] if account_id else []
        total, chats, senders, last = (
            await self.db.execute(
                select(func.count(M.id), func.count(func.distinct(M.chat_id)), func.count(func.distinct(M.tg_user_id)),
                       func.max(M.date)).where(*where)
            )
        ).one()
        stored, pending, size = (
            await self.db.execute(
                select(
                    func.count(M.id).filter(M.media_status == MediaStatus.STORED),
                    func.count(M.id).filter(M.media_status == MediaStatus.PENDING),
                    func.coalesce(func.sum(M.media_size).filter(M.media_status == MediaStatus.STORED), 0),
                ).where(*where)
            )
        ).one()
        return {"messages": total, "chats": chats, "users": senders, "last_date": last,
                "media_stored": stored, "media_pending": pending, "media_bytes": int(size)}

    async def media_stats(self, account_id: int | None, days: int | None = None) -> dict:
        M = MessageModel
        where = [M.media_status.is_not(None)] + ([M.account_id == account_id] if account_id else [])
        if days:
            where.append(M.date >= utcnow() - timedelta(days=days))
        size = func.coalesce(func.sum(M.media_size), 0)
        stored = M.media_status == MediaStatus.STORED

        kinds: dict[str, dict] = {}
        statuses: dict[str, dict] = {}
        rows = await self.db.execute(
            select(M.media, M.media_status, func.count(M.id), size).where(*where).group_by(M.media, M.media_status)
        )
        for kind, status, count, total in rows.all():
            k = kinds.setdefault(kind, {"kind": kind, "total": 0, "stored": 0, "stored_bytes": 0, "pending": 0,
                                        "failed": 0, "too_large": 0})
            k["total"] += count
            k[status] = k.get(status, 0) + count
            if status == MediaStatus.STORED:
                k["stored_bytes"] = int(total)
            st = statuses.setdefault(status, {"count": 0, "bytes": 0})
            st["count"] += count
            st["bytes"] += int(total)

        chat_rows = await self.db.execute(
            select(M.account_id, M.chat_id, func.max(M.chat_title), func.count(M.id), size)
            .where(*where, stored)
            .group_by(M.account_id, M.chat_id)
            .order_by(size.desc())
            .limit(15)
        )
        account_rows = await self.db.execute(
            select(M.account_id, func.count(M.id).filter(stored), func.coalesce(func.sum(M.media_size).filter(stored), 0),
                   func.count(M.id).filter(M.media_status == MediaStatus.PENDING))
            .where(*where)
            .group_by(M.account_id)
            .order_by(M.account_id)
        )
        day = cast(func.timezone("UTC", M.date), Date)
        daily_rows = await self.db.execute(
            select(day, func.count(M.id), func.count(M.id).filter(stored),
                   func.coalesce(func.sum(M.media_size).filter(stored), 0))
            .where(*where, M.date.is_not(None))
            .group_by(day)
            .order_by(day.desc())
            .limit(days or 30)
        )
        daily = [{"date": d.isoformat(), "total": t, "stored": n, "bytes": int(b)}
                 for d, t, n, b in reversed(daily_rows.all())]
        return {
            "daily": daily,
            "statuses": statuses,
            "kinds": sorted(kinds.values(), key=lambda k: -k["total"]),
            "chats": [{"account_id": a, "chat_id": c, "chat_title": t, "count": n, "bytes": int(b)}
                      for a, c, t, n, b in chat_rows.all()],
            "accounts": [{"account_id": a, "stored": n, "bytes": int(b), "pending": p}
                         for a, n, b, p in account_rows.all()],
        }

    async def pending_media(self, limit: int) -> list[ChatMessage]:
        M, A = MessageModel, AccountModel
        usable = select(A.id).where(A.is_enabled.is_(True), A.status.in_(USABLE))
        return await self._all(
            select(M)
            .where(M.media_status == MediaStatus.PENDING, M.account_id.in_(usable))
            .order_by(M.id)
            .limit(limit)
        )

    async def queue_unqueued_media(self) -> int:
        M = MessageModel
        res = await self.db.execute(
            update(M)
            .where(M.media_status.is_(None), M.media.in_(sorted(STORABLE_MEDIA)))
            .values(media_status=MediaStatus.PENDING)
            .execution_options(synchronize_session=False)
        )
        return res.rowcount or 0


# ---------------------------------------------------------------- Telegram users
def _user_row(u: TgUserInfo) -> dict:
    now = utcnow()
    return {
        "id": u.id,
        "username": u.username,
        "first_name": _cut(u.first_name),
        "last_name": _cut(u.last_name),
        "phone": u.phone,
        "is_bot": u.is_bot,
        "is_premium": u.is_premium,
        "is_deleted": u.is_deleted,
        "first_seen_at": now,
        "updated_at": now,
    }


class SqlTgUserRepository(_Repo):
    async def upsert_many(self, users: list[TgUserInfo]) -> None:
        U = TgUserModel
        full = [_user_row(u) for u in users if not u.is_min]
        minimal = [_user_row(u) for u in users if u.is_min]
        for i in range(0, len(full), CHUNK):
            stmt = pg_insert(U).values(full[i : i + CHUNK])
            ex = stmt.excluded
            stmt = stmt.on_conflict_do_update(
                index_elements=[U.id],
                set_={
                    "username": ex.username,
                    "first_name": ex.first_name,
                    "last_name": ex.last_name,
                    "phone": func.coalesce(ex.phone, U.phone),
                    "is_bot": ex.is_bot,
                    "is_premium": ex.is_premium,
                    "is_deleted": ex.is_deleted,
                    "updated_at": ex.updated_at,
                },
            )
            await self.db.execute(stmt)
        for i in range(0, len(minimal), CHUNK):
            # "min" users carry incomplete data – only insert if unknown
            await self.db.execute(pg_insert(U).values(minimal[i : i + CHUNK]).on_conflict_do_nothing())

    async def get(self, user_id: int) -> TgUser | None:
        return await self._get(TgUserModel, user_id)

    async def search(self, q: str | None, limit: int) -> list[TgUser]:
        U = TgUserModel
        stmt = select(U)
        if q:
            like = f"%{q}%"
            stmt = stmt.where(or_(U.username.ilike(like), U.first_name.ilike(like), U.last_name.ilike(like)))
        return await self._all(stmt.order_by(U.updated_at.desc()).limit(limit))

    async def activity(self, user_id: int) -> tuple[int, int, datetime | None]:
        M = MessageModel
        count, chats, last = (
            await self.db.execute(
                select(func.count(M.id), func.count(func.distinct(M.chat_id)), func.max(M.date))
                .where(M.tg_user_id == user_id)
            )
        ).one()
        return count, chats, last
