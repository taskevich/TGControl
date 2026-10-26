from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum

from app.domain.errors import AccountUnavailable, Conflict, InvalidInput


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(eq=False)
class PanelUser:
    username: str
    password_hash: str
    is_active: bool = True
    id: int | None = None
    created_at: datetime = field(default_factory=utcnow)


class ProxyStatus(StrEnum):
    UNKNOWN = "unknown"
    OK = "ok"
    ERROR = "error"


@dataclass(eq=False)
class Proxy:
    host: str
    port: int
    scheme: str = "socks5"  # socks5 / socks4 / http
    name: str | None = None
    username: str | None = None
    password_enc: str | None = None
    is_active: bool = True
    status: str = ProxyStatus.UNKNOWN
    status_detail: str | None = None
    latency_ms: int | None = None
    checked_at: datetime | None = None
    id: int | None = None
    created_at: datetime = field(default_factory=utcnow)

    def record_check(self, ok: bool, latency_ms: int | None, error: str | None) -> None:
        self.status = ProxyStatus.OK if ok else ProxyStatus.ERROR
        self.latency_ms = latency_ms
        self.status_detail = error
        self.checked_at = utcnow()

    def reset_check(self) -> None:
        self.status, self.latency_ms, self.status_detail = (
            ProxyStatus.UNKNOWN,
            None,
            None,
        )

    def ensure_usable(self) -> None:
        if not self.is_active:
            raise AccountUnavailable(
                f"Привязанный прокси #{self.id} отключён - включите его или отвяжите от аккаунта"
            )


class AccountStatus(StrEnum):
    NEW = "new"
    ACTIVE = "active"
    UNAUTHORIZED = "unauthorized"
    BANNED = "banned"
    ERROR = "error"


USABLE_STATUSES = (AccountStatus.ACTIVE, AccountStatus.NEW)


@dataclass(eq=False)
class Account:
    session_enc: str  # encrypted Telethon StringSession
    phone: str | None = None
    tg_id: int | None = None
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    twofa_enc: str | None = None  # encrypted 2FA password

    api_id: int | None = None
    api_hash: str | None = None
    device_model: str | None = None
    system_version: str | None = None
    app_version: str | None = None
    lang_code: str | None = None
    system_lang_code: str | None = None
    proxy_id: int | None = None

    status: str = AccountStatus.NEW
    status_detail: str | None = None
    is_enabled: bool = True
    notes: str | None = None
    source: str | None = None  # phone / session_file / string / json

    id: int | None = None
    created_at: datetime = field(default_factory=utcnow)
    last_checked_at: datetime | None = None

    proxy: Proxy | None = field(init=False, repr=False)

    @property
    def label(self) -> str:
        return self.phone or (f"@{self.username}" if self.username else f"#{self.id}")

    @property
    def has_2fa(self) -> bool:
        return bool(self.twofa_enc)

    def ensure_enabled(self) -> None:
        if not self.is_enabled:
            raise AccountUnavailable("Аккаунт отключён в панели")

    def update_profile(
        self,
        *,
        tg_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
        phone: str | None,
    ) -> None:
        self.tg_id = tg_id
        self.username = username
        self.first_name = first_name
        self.last_name = last_name
        if phone:
            self.phone = "+" + phone.lstrip("+")

    def activate(self) -> None:
        self.status = AccountStatus.ACTIVE
        self.status_detail = None

    def mark_checked(self) -> None:
        self.last_checked_at = utcnow()

    def mark_dead(self, *, banned: bool, detail: str) -> None:
        self.status = AccountStatus.BANNED if banned else AccountStatus.UNAUTHORIZED
        self.status_detail = detail
        self.last_checked_at = utcnow()

    def mark_unauthorized(self, detail: str) -> None:
        self.status = AccountStatus.UNAUTHORIZED
        self.status_detail = detail

    def mark_error(self, detail: str) -> None:
        self.status = AccountStatus.ERROR
        self.status_detail = detail


class TaskKind(StrEnum):
    SEND = "send"
    COMMENT = "comment"
    JOIN = "join"
    LEAVE = "leave"


class TaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ItemStatus(StrEnum):
    OK = "ok"
    SKIPPED = "skipped"
    ERROR = "error"


ACTIVE_TASK_STATUSES = (TaskStatus.PENDING, TaskStatus.RUNNING)


@dataclass(eq=False)
class BulkTaskItem:
    task_id: int
    status: str  # ok / skipped / error
    account_id: int | None = None
    target: str | None = None
    detail: str | None = None
    id: int | None = None
    created_at: datetime = field(default_factory=utcnow)


@dataclass(eq=False)
class BulkTask:
    kind: str
    params: dict = field(default_factory=dict)
    status: str = TaskStatus.PENDING
    total: int = 0
    done: int = 0
    success: int = 0
    skipped: int = 0
    failed: int = 0
    error: str | None = None
    created_by: str | None = None
    id: int | None = None
    created_at: datetime = field(default_factory=utcnow)
    finished_at: datetime | None = None

    items: list[BulkTaskItem] = field(init=False, repr=False)

    @property
    def is_active(self) -> bool:
        return self.status in ACTIVE_TASK_STATUSES

    @property
    def targets(self) -> list[str]:
        return self.params["targets"]

    def start(self, total: int) -> None:
        self.total = total
        self.status = TaskStatus.RUNNING

    def finish(self, cancelled: bool) -> None:
        self.status = TaskStatus.CANCELLED if cancelled else TaskStatus.DONE
        self.finished_at = utcnow()

    def fail(self, error: str) -> None:
        self.status = TaskStatus.FAILED
        self.error = error
        self.finished_at = utcnow()


@dataclass(eq=False)
class MessageStatSnapshot:
    tracked_id: int
    views: int | None = None
    forwards: int | None = None
    reactions_total: int = 0
    replies_count: int = 0
    id: int | None = None
    taken_at: datetime = field(default_factory=utcnow)


@dataclass(eq=False)
class TrackedMessage:
    account_id: int
    chat_id: int  # marked peer id (-100... for channels)
    msg_id: int
    task_id: int | None = None
    chat_access_hash: int | None = None
    chat_title: str | None = None
    chat_username: str | None = None
    thread_top_id: int | None = None
    is_comment: bool = False
    parent_link: str | None = None
    link: str | None = None
    text: str | None = None
    source: str = "panel"  # panel / bulk / manual

    views: int | None = None
    forwards: int | None = None
    reactions_total: int = 0
    reactions: list = field(default_factory=list)
    replies_count: int = 0
    is_deleted: bool = False

    sent_at: datetime | None = None
    id: int | None = None
    created_at: datetime = field(default_factory=utcnow)
    last_refreshed_at: datetime | None = None
    refresh_error: str | None = None

    snapshots: list[MessageStatSnapshot] = field(init=False, repr=False)

    def apply_stats(
        self,
        *,
        views: int | None,
        forwards: int | None,
        reactions: list[dict],
        replies: int,
    ) -> None:
        self.views = views
        self.forwards = forwards
        self.reactions = reactions
        self.reactions_total = sum(r["count"] for r in reactions)
        self.replies_count = replies
        self.is_deleted = False

    def snapshot(self) -> MessageStatSnapshot:
        return MessageStatSnapshot(
            tracked_id=self.id,
            views=self.views,
            forwards=self.forwards,
            reactions_total=self.reactions_total,
            replies_count=self.replies_count,
        )


class CommentKind(StrEnum):
    REPLY = "reply"
    MENTION = "mention"


@dataclass(eq=False)
class Comment:
    account_id: int
    chat_id: int
    msg_id: int
    kind: str = CommentKind.REPLY
    tracked_id: int | None = None
    chat_title: str | None = None
    reply_to_msg_id: int | None = None
    sender_id: int | None = None
    sender_name: str | None = None
    sender_username: str | None = None
    text: str | None = None
    link: str | None = None
    date: datetime | None = None
    id: int | None = None
    created_at: datetime = field(default_factory=utcnow)


@dataclass(eq=False)
class TgUser:
    id: int  # Telegram user id
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    is_bot: bool = False
    is_premium: bool = False
    is_deleted: bool = False
    first_seen_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)


class MediaStatus(StrEnum):
    PENDING = "pending"
    STORED = "stored"
    TOO_LARGE = "too_large"
    FAILED = "failed"


STORABLE_MEDIA = frozenset(
    {"photo", "video", "voice", "video_note", "sticker", "gif", "audio", "file"}
)


def initial_media_status(
    media: str | None, size: int | None, max_size: int
) -> str | None:
    if media not in STORABLE_MEDIA:
        return None
    if size is not None and size > max_size:
        return MediaStatus.TOO_LARGE
    return MediaStatus.PENDING


@dataclass(eq=False)
class ChatMessage:
    account_id: int
    chat_id: int
    msg_id: int
    chat_title: str | None = None
    chat_username: str | None = None
    chat_type: str | None = None
    sender_id: int | None = None
    tg_user_id: int | None = None
    sender_name: str | None = None
    out: bool = False
    is_service: bool = False
    text: str | None = None
    media: str | None = None
    media_size: int | None = None
    media_mime: str | None = None
    media_name: str | None = None
    media_status: str | None = None
    media_key: str | None = None
    media_error: str | None = None
    reply_to_msg_id: int | None = None
    thread_top_id: int | None = None
    grouped_id: int | None = None
    views: int | None = None
    forwards: int | None = None
    replies: int | None = None
    reactions: list = field(default_factory=list)
    reactions_total: int = 0
    date: datetime | None = None
    edit_date: datetime | None = None
    id: int | None = None
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    tg_user: TgUser | None = field(init=False, repr=False)

    def media_stored(self, key: str, size: int, mime: str | None, name: str) -> None:
        self.media_status, self.media_key, self.media_error = (
            MediaStatus.STORED,
            key,
            None,
        )
        self.media_size, self.media_mime, self.media_name = size, mime, name
        self.updated_at = utcnow()

    def media_skipped(self, status: str, error: str | None = None) -> None:
        self.media_status, self.media_error = status, error
        self.updated_at = utcnow()

    def queue_media(self) -> None:
        if self.media not in STORABLE_MEDIA:
            raise InvalidInput("У сообщения нет файла")
        if self.media_status == MediaStatus.STORED:
            raise Conflict("Файл уже сохранён")
        self.media_skipped(MediaStatus.PENDING)
