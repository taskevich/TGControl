from dataclasses import dataclass, field
from datetime import datetime

from app.domain.entities import Account
from app.domain.values import ProxyAddress


@dataclass(frozen=True)
class TgProfile:
    id: int
    phone: str | None
    username: str | None
    first_name: str | None
    last_name: str | None


@dataclass(frozen=True)
class TgUserInfo:
    id: int
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    is_bot: bool = False
    is_premium: bool = False
    is_deleted: bool = False
    is_min: bool = False


@dataclass(frozen=True)
class ChatInfo:
    id: int
    title: str | None
    username: str | None
    type: str  # user / bot / group / supergroup / channel / unknown
    access_hash: int | None = None


@dataclass(frozen=True)
class TgMessage:
    id: int
    chat_id: int
    date: datetime | None
    text: str
    is_service: bool = False
    out: bool = False
    post: bool = False
    sender_id: int | None = None
    sender_name: str | None = None
    sender_username: str | None = None
    sender_user: TgUserInfo | None = None
    views: int | None = None
    forwards: int | None = None
    replies: int | None = None
    reactions: list[dict] = field(default_factory=list)
    reply_to_msg_id: int | None = None
    reply_to_top_id: int | None = None
    media: str | None = None
    media_size: int | None = (
        None  # bytes, for media with a file (photo, video, document, ...)
    )
    media_mime: str | None = None
    media_name: str | None = None
    grouped_id: int | None = None
    edit_date: datetime | None = None

    @property
    def reactions_total(self) -> int:
        return sum(r["count"] for r in self.reactions)

    @property
    def thread_root_id(self) -> int | None:
        return self.reply_to_top_id or self.reply_to_msg_id


@dataclass(frozen=True)
class Dialog:
    id: int
    title: str
    username: str | None
    type: str
    unread: int
    unread_mentions: int
    pinned: bool
    archived: bool
    participants: int | None
    is_admin: bool
    can_send: bool
    cant_send_reason: str | None
    last_text: str
    last_date: datetime | None
    top_message_id: int = 0
    is_group: bool = False
    unread_reactions: int = 0
    unread_mark: bool = False
    forum: bool = False

    @property
    def has_unread(self) -> bool:
        return bool(
            self.unread
            or self.unread_mentions
            or self.unread_reactions
            or self.unread_mark
        )


@dataclass(frozen=True)
class DownloadedMedia:
    path: str
    size: int
    mime: str | None
    file_name: str


@dataclass(frozen=True)
class JoinResult:
    status: str
    detail: str
    chat: ChatInfo | None = None


@dataclass(frozen=True)
class SentMessage:
    message: TgMessage
    chat: ChatInfo
    thread_top_id: int | None = None  # for comments: id of the discussion root


@dataclass(frozen=True)
class LocatedMessage:
    message: TgMessage
    chat: ChatInfo
    is_comment: bool = False
    parent_link: str | None = None
    thread_top_id: int | None = None


@dataclass(frozen=True)
class ClientParams:
    session: str = ""
    api_id: int | None = None
    api_hash: str | None = None
    proxy: ProxyAddress | None = None
    device_model: str | None = None
    system_version: str | None = None
    app_version: str | None = None
    lang_code: str | None = None
    system_lang_code: str | None = None


@dataclass(frozen=True)
class LoginCode:
    session: str
    phone_code_hash: str
    delivery: str  # App / Sms / Call / ...


@dataclass
class ParsedSession:
    session: str
    name: str
    source: str
    phone: str | None = None
    api_id: int | None = None
    api_hash: str | None = None
    twofa: str | None = None
    device_model: str | None = None
    system_version: str | None = None
    app_version: str | None = None
    lang_code: str | None = None
    system_lang_code: str | None = None
    proxy: str | None = None


@dataclass
class ParsedUploads:
    accounts: list[ParsedSession] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)  # [{"name": str, "error": str}]


@dataclass
class AccountView:
    account: Account
    connected: bool
    twofa: str | None  # decrypted 2FA password


@dataclass
class LoginStep:
    flow_id: str
    step: str  # code / password / done
    account: AccountView | None = None
    detail: str | None = None


@dataclass
class ImportResult:
    name: str
    status: str  # created / updated / error
    detail: str | None = None
    account_id: int | None = None


@dataclass
class PasswordResult:
    account_id: int
    label: str
    status: str
    detail: str | None = None


@dataclass
class Page:
    items: list
    total: int
