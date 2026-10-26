from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.values import NEW_PASSWORD_MIN_LENGTH, normalize_phone


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class LoginIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class ChangePasswordIn(BaseModel):
    old_password: str
    new_password: str = Field(min_length=6)


class PanelUserOut(ORM):
    id: int
    username: str
    is_active: bool
    created_at: datetime


class PanelUserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6)


class ProxyBrief(ORM):
    id: int
    name: str | None
    scheme: str
    host: str
    port: int
    is_active: bool
    status: str
    latency_ms: int | None


class ProxyOut(ProxyBrief):
    username: str | None
    has_password: bool = False
    status_detail: str | None
    checked_at: datetime | None
    created_at: datetime
    accounts_count: int = 0
    url_masked: str = ""


class ProxyCreate(BaseModel):
    url: str = Field(min_length=3)
    name: str | None = None


class ProxyBulkIn(BaseModel):
    text: str = Field(min_length=3)


class ProxyUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    is_active: bool | None = None


class ProxyAssignIn(BaseModel):
    account_ids: list[int] = Field(default_factory=list)
    max_per_proxy: int = Field(default=1, ge=1, le=100)
    only_working: bool = True


class AccountOut(ORM):
    id: int
    phone: str | None
    tg_id: int | None
    username: str | None
    first_name: str | None
    last_name: str | None
    api_id: int | None
    proxy_id: int | None
    proxy: "ProxyBrief | None" = None
    status: str
    status_detail: str | None
    is_enabled: bool
    notes: str | None
    source: str | None
    has_2fa: bool = False
    twofa: str | None = None
    connected: bool = False
    created_at: datetime
    last_checked_at: datetime | None


class AccountUpdate(BaseModel):
    proxy_id: int | None = None
    proxy: str | None = None
    notes: str | None = None
    is_enabled: bool | None = None
    api_id: int | None = None
    api_hash: str | None = None
    twofa: str | None = None


class SetPasswordIn(BaseModel):
    password: str = Field(min_length=NEW_PASSWORD_MIN_LENGTH)
    hint: str = Field(default="", max_length=64)

    @field_validator("password")
    @classmethod
    def no_spaces_around(cls, v: str) -> str:
        if v != v.strip():
            raise ValueError("Пароль не должен начинаться или заканчиваться пробелом")
        return v


class SetPasswordAllIn(SetPasswordIn):
    account_ids: list[int] = Field(default_factory=list)


class SetPasswordResult(BaseModel):
    account_id: int
    label: str
    status: str
    detail: str | None = None


class LoginStartIn(BaseModel):
    phone: str
    api_id: int | None = None
    api_hash: str | None = None
    proxy: str | None = None
    proxy_id: int | None = None
    password: str | None = None

    @field_validator("phone")
    @classmethod
    def norm_phone(cls, v: str) -> str:
        return normalize_phone(v)


class LoginCodeIn(BaseModel):
    flow_id: str
    code: str


class LoginPasswordIn(BaseModel):
    flow_id: str
    password: str


class LoginStepOut(BaseModel):
    flow_id: str
    step: str
    account: AccountOut | None = None
    detail: str | None = None


class ImportResultItem(BaseModel):
    name: str
    status: str
    detail: str | None = None
    account_id: int | None = None


class SendMessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=4096)
    reply_to: int | None = None
    track: bool = True
    link_preview: bool = True


class SendToIn(SendMessageIn):
    target: str = Field(min_length=1)


class TargetIn(BaseModel):
    target: str = Field(min_length=1)


class CommentPostIn(BaseModel):
    post_link: str
    text: str = Field(min_length=1, max_length=4096)
    join_if_needed: bool = False


class BulkBase(BaseModel):
    account_ids: list[int] = Field(default_factory=list)
    all_accounts: bool = False
    targets: list[str] = Field(min_length=1)
    delay_min: float | None = Field(default=None, ge=0)
    delay_max: float | None = Field(default=None, ge=0)

    @field_validator("targets")
    @classmethod
    def clean_targets(cls, v: list[str]) -> list[str]:
        cleaned = [t.strip() for t in v if t and t.strip()]
        if not cleaned:
            raise ValueError("Укажите хотя бы одну цель")
        return list(dict.fromkeys(cleaned))


class BulkSendIn(BulkBase):
    text: str = Field(min_length=1, max_length=4096)
    mode: str = Field(default="message", pattern="^(message|comment)$")
    join_if_needed: bool = False
    track: bool = True
    link_preview: bool = True


class BulkJoinIn(BulkBase):
    pass


class TaskItemOut(ORM):
    id: int
    account_id: int | None
    target: str | None
    status: str
    detail: str | None
    created_at: datetime


class TaskOut(ORM):
    id: int
    kind: str
    params: dict
    status: str
    total: int
    done: int
    success: int
    skipped: int
    failed: int
    error: str | None
    created_by: str | None
    created_at: datetime
    finished_at: datetime | None


class TaskDetailOut(TaskOut):
    items: list[TaskItemOut]


class TrackedOut(ORM):
    id: int
    account_id: int
    task_id: int | None
    chat_id: int
    chat_title: str | None
    chat_username: str | None
    msg_id: int
    is_comment: bool
    parent_link: str | None
    link: str | None
    text: str | None
    source: str
    views: int | None
    forwards: int | None
    reactions_total: int
    reactions: list
    replies_count: int
    is_deleted: bool
    sent_at: datetime | None
    last_refreshed_at: datetime | None
    refresh_error: str | None


class SnapshotOut(ORM):
    views: int | None
    forwards: int | None
    reactions_total: int
    replies_count: int
    taken_at: datetime


class CommentOut(ORM):
    id: int
    account_id: int
    tracked_id: int | None
    kind: str
    chat_id: int
    chat_title: str | None
    msg_id: int
    reply_to_msg_id: int | None
    sender_id: int | None
    sender_name: str | None
    sender_username: str | None
    text: str | None
    link: str | None
    date: datetime | None


class TrackedDetailOut(TrackedOut):
    snapshots: list[SnapshotOut]
    comments: list[CommentOut]


class TrackLinkIn(BaseModel):
    account_id: int
    link: str


class RefreshIn(BaseModel):
    ids: list[int] = Field(default_factory=list)
    account_id: int | None = None


class Page(BaseModel):
    items: list
    total: int


class TgUserOut(ORM):
    id: int
    username: str | None
    first_name: str | None
    last_name: str | None
    phone: str | None
    is_bot: bool
    is_premium: bool
    is_deleted: bool
    first_seen_at: datetime
    updated_at: datetime


class TgUserDetailOut(TgUserOut):
    messages_count: int = 0
    chats_count: int = 0
    last_message_at: datetime | None = None


class MessageOut(ORM):
    id: int
    account_id: int
    chat_id: int
    chat_title: str | None
    chat_username: str | None
    chat_type: str | None
    msg_id: int
    sender_id: int | None
    sender_name: str | None
    tg_user: TgUserOut | None = None
    out: bool
    is_service: bool
    text: str | None
    media: str | None
    media_size: int | None = None
    media_mime: str | None = None
    media_name: str | None = None
    media_status: str | None = None
    media_error: str | None = None
    media_url: str | None = None
    reply_to_msg_id: int | None
    thread_top_id: int | None
    views: int | None
    forwards: int | None
    replies: int | None
    reactions: list
    reactions_total: int
    date: datetime | None
    edit_date: datetime | None
    link: str | None = None


class MessageFeedOut(BaseModel):
    items: list[MessageOut]
    next_before_date: datetime | None = None
    next_before_id: int | None = None


class SavedChatOut(BaseModel):
    account_id: int
    chat_id: int
    chat_title: str | None
    chat_username: str | None
    chat_type: str | None
    count: int
    last_date: datetime | None


class ReadAllIn(BaseModel):
    account_id: int | None = None


class MessagesSyncIn(BaseModel):
    account_id: int | None = None
    dialog_limit: int = Field(default=50, ge=1, le=500)
    per_chat: int = Field(default=100, ge=1, le=1000)
