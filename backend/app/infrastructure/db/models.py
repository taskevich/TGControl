from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    type_annotation_map = {
        datetime: DateTime(timezone=True),
        dict[str, Any]: JSONB,
        list[Any]: JSONB,
    }


class PanelUserModel(Base):
    __tablename__ = "panel_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool]
    created_at: Mapped[datetime]


class ProxyModel(Base):
    __tablename__ = "proxies"
    __table_args__ = (
        UniqueConstraint("scheme", "host", "port", "username", name="uq_proxy"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str | None] = mapped_column(String(128))
    scheme: Mapped[str] = mapped_column(String(10))
    host: Mapped[str] = mapped_column(String(255))
    port: Mapped[int]
    username: Mapped[str | None] = mapped_column(String(255))
    password_enc: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool]
    status: Mapped[str] = mapped_column(String(16))
    status_detail: Mapped[str | None] = mapped_column(Text)
    latency_ms: Mapped[int | None]
    checked_at: Mapped[datetime | None]
    created_at: Mapped[datetime]


class AccountModel(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    phone: Mapped[str | None] = mapped_column(String(32), index=True)
    tg_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    username: Mapped[str | None] = mapped_column(String(64))
    first_name: Mapped[str | None] = mapped_column(String(128))
    last_name: Mapped[str | None] = mapped_column(String(128))
    session_enc: Mapped[str] = mapped_column(Text)
    twofa_enc: Mapped[str | None] = mapped_column(Text)
    api_id: Mapped[int | None]
    api_hash: Mapped[str | None] = mapped_column(String(64))
    device_model: Mapped[str | None] = mapped_column(String(128))
    system_version: Mapped[str | None] = mapped_column(String(128))
    app_version: Mapped[str | None] = mapped_column(String(64))
    lang_code: Mapped[str | None] = mapped_column(String(16))
    system_lang_code: Mapped[str | None] = mapped_column(String(16))
    proxy_id: Mapped[int | None] = mapped_column(
        ForeignKey("proxies.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[str] = mapped_column(String(32), index=True)
    status_detail: Mapped[str | None] = mapped_column(Text)
    is_enabled: Mapped[bool]
    notes: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime]
    last_checked_at: Mapped[datetime | None]

    proxy: Mapped[ProxyModel | None] = relationship(lazy="joined")


class BulkTaskItemModel(Base):
    __tablename__ = "bulk_task_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("bulk_tasks.id", ondelete="CASCADE"), index=True
    )
    account_id: Mapped[int | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL")
    )
    target: Mapped[str | None] = mapped_column(String(512))
    status: Mapped[str] = mapped_column(String(16))
    detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime]


class BulkTaskModel(Base):
    __tablename__ = "bulk_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(32))
    params: Mapped[dict[str, Any]]
    status: Mapped[str] = mapped_column(String(32), index=True)
    total: Mapped[int]
    done: Mapped[int]
    success: Mapped[int]
    skipped: Mapped[int]
    failed: Mapped[int]
    error: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime]
    finished_at: Mapped[datetime | None]

    items: Mapped[list[BulkTaskItemModel]] = relationship(
        cascade="all, delete-orphan",
        order_by=BulkTaskItemModel.id,
        passive_deletes=True,
        lazy="raise",
    )


class MessageStatSnapshotModel(Base):
    __tablename__ = "message_stat_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    tracked_id: Mapped[int] = mapped_column(
        ForeignKey("tracked_messages.id", ondelete="CASCADE"), index=True
    )
    views: Mapped[int | None]
    forwards: Mapped[int | None]
    reactions_total: Mapped[int]
    replies_count: Mapped[int]
    taken_at: Mapped[datetime]


class TrackedMessageModel(Base):
    __tablename__ = "tracked_messages"
    __table_args__ = (
        UniqueConstraint("account_id", "chat_id", "msg_id", name="uq_tracked_msg"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    task_id: Mapped[int | None] = mapped_column(
        ForeignKey("bulk_tasks.id", ondelete="SET NULL")
    )
    chat_id: Mapped[int] = mapped_column(BigInteger)
    chat_access_hash: Mapped[int | None] = mapped_column(BigInteger)
    chat_title: Mapped[str | None] = mapped_column(String(255))
    chat_username: Mapped[str | None] = mapped_column(String(64))
    msg_id: Mapped[int]
    thread_top_id: Mapped[int | None]
    is_comment: Mapped[bool]
    parent_link: Mapped[str | None] = mapped_column(String(512))
    link: Mapped[str | None] = mapped_column(String(512))
    text: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(16))
    views: Mapped[int | None]
    forwards: Mapped[int | None]
    reactions_total: Mapped[int]
    reactions: Mapped[list[Any]]
    replies_count: Mapped[int]
    is_deleted: Mapped[bool]
    sent_at: Mapped[datetime | None]
    created_at: Mapped[datetime]
    last_refreshed_at: Mapped[datetime | None]
    refresh_error: Mapped[str | None] = mapped_column(Text)

    snapshots: Mapped[list[MessageStatSnapshotModel]] = relationship(
        cascade="all, delete-orphan",
        order_by=MessageStatSnapshotModel.taken_at,
        passive_deletes=True,
        lazy="raise",
    )


class CommentModel(Base):
    __tablename__ = "comments"
    __table_args__ = (
        UniqueConstraint("account_id", "chat_id", "msg_id", name="uq_comment_msg"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    tracked_id: Mapped[int | None] = mapped_column(
        ForeignKey("tracked_messages.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(16))
    chat_id: Mapped[int] = mapped_column(BigInteger)
    chat_title: Mapped[str | None] = mapped_column(String(255))
    msg_id: Mapped[int]
    reply_to_msg_id: Mapped[int | None]
    sender_id: Mapped[int | None] = mapped_column(BigInteger)
    sender_name: Mapped[str | None] = mapped_column(String(255))
    sender_username: Mapped[str | None] = mapped_column(String(64))
    text: Mapped[str | None] = mapped_column(Text)
    link: Mapped[str | None] = mapped_column(String(512))
    date: Mapped[datetime | None] = mapped_column(index=True)
    created_at: Mapped[datetime]


class TgUserModel(Base):
    __tablename__ = "tg_user"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=False
    )  # Telegram user id
    username: Mapped[str | None] = mapped_column(String(64), index=True)
    first_name: Mapped[str | None] = mapped_column(String(255))
    last_name: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(32))
    is_bot: Mapped[bool]
    is_premium: Mapped[bool]
    is_deleted: Mapped[bool]
    first_seen_at: Mapped[datetime]
    updated_at: Mapped[datetime]


class MessageModel(Base):
    __tablename__ = "message"
    __table_args__ = (
        UniqueConstraint("account_id", "chat_id", "msg_id", name="uq_message"),
        Index("ix_message_date_id", "date", "id"),
        Index("ix_message_account_chat_date", "account_id", "chat_id", "date"),
        Index(
            "ix_message_media_pending",
            "id",
            postgresql_where=text("media_status = 'pending'"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    chat_title: Mapped[str | None] = mapped_column(String(255))
    chat_username: Mapped[str | None] = mapped_column(String(64))
    chat_type: Mapped[str | None] = mapped_column(String(16))
    msg_id: Mapped[int]
    sender_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    tg_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("tg_user.id", ondelete="SET NULL"), index=True
    )
    sender_name: Mapped[str | None] = mapped_column(String(255))
    out: Mapped[bool]
    is_service: Mapped[bool]
    text: Mapped[str | None] = mapped_column(Text)
    media: Mapped[str | None] = mapped_column(String(32))
    media_size: Mapped[int | None] = mapped_column(BigInteger)
    media_mime: Mapped[str | None] = mapped_column(String(128))
    media_name: Mapped[str | None] = mapped_column(String(255))
    media_status: Mapped[str | None] = mapped_column(String(16))
    media_key: Mapped[str | None] = mapped_column(String(512))
    media_error: Mapped[str | None] = mapped_column(Text)
    reply_to_msg_id: Mapped[int | None]
    thread_top_id: Mapped[int | None]
    grouped_id: Mapped[int | None] = mapped_column(BigInteger)
    views: Mapped[int | None]
    forwards: Mapped[int | None]
    replies: Mapped[int | None]
    reactions: Mapped[list[Any]]
    reactions_total: Mapped[int]
    date: Mapped[datetime | None]
    edit_date: Mapped[datetime | None]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]

    tg_user: Mapped[TgUserModel | None] = relationship(lazy="joined")
