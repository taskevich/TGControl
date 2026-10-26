"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "panel_users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", TS, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_panel_users_username", "panel_users", ["username"], unique=True)

    op.create_table(
        "accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("phone", sa.String(32)),
        sa.Column("tg_id", sa.BigInteger()),
        sa.Column("username", sa.String(64)),
        sa.Column("first_name", sa.String(128)),
        sa.Column("last_name", sa.String(128)),
        sa.Column("session_enc", sa.Text(), nullable=False),
        sa.Column("twofa_enc", sa.Text()),
        sa.Column("api_id", sa.Integer()),
        sa.Column("api_hash", sa.String(64)),
        sa.Column("device_model", sa.String(128)),
        sa.Column("system_version", sa.String(128)),
        sa.Column("app_version", sa.String(64)),
        sa.Column("lang_code", sa.String(16)),
        sa.Column("system_lang_code", sa.String(16)),
        sa.Column("proxy", sa.String(255)),
        sa.Column("status", sa.String(32), nullable=False, server_default="new"),
        sa.Column("status_detail", sa.Text()),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notes", sa.Text()),
        sa.Column("source", sa.String(32)),
        sa.Column("created_at", TS, nullable=False, server_default=sa.func.now()),
        sa.Column("last_checked_at", TS),
    )
    op.create_index("ix_accounts_phone", "accounts", ["phone"])
    op.create_index("ix_accounts_tg_id", "accounts", ["tg_id"])
    op.create_index("ix_accounts_status", "accounts", ["status"])

    op.create_table(
        "bulk_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("params", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("done", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text()),
        sa.Column("created_by", sa.String(64)),
        sa.Column("created_at", TS, nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", TS),
    )
    op.create_index("ix_bulk_tasks_status", "bulk_tasks", ["status"])

    op.create_table(
        "bulk_task_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("bulk_tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="SET NULL")),
        sa.Column("target", sa.String(512)),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("detail", sa.Text()),
        sa.Column("created_at", TS, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_bulk_task_items_task_id", "bulk_task_items", ["task_id"])

    op.create_table(
        "tracked_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("bulk_tasks.id", ondelete="SET NULL")),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("chat_access_hash", sa.BigInteger()),
        sa.Column("chat_title", sa.String(255)),
        sa.Column("chat_username", sa.String(64)),
        sa.Column("msg_id", sa.Integer(), nullable=False),
        sa.Column("thread_top_id", sa.Integer()),
        sa.Column("is_comment", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("parent_link", sa.String(512)),
        sa.Column("link", sa.String(512)),
        sa.Column("text", sa.Text()),
        sa.Column("source", sa.String(16), nullable=False, server_default="panel"),
        sa.Column("views", sa.Integer()),
        sa.Column("forwards", sa.Integer()),
        sa.Column("reactions_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reactions", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("replies_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sent_at", TS),
        sa.Column("created_at", TS, nullable=False, server_default=sa.func.now()),
        sa.Column("last_refreshed_at", TS),
        sa.Column("refresh_error", sa.Text()),
        sa.UniqueConstraint("account_id", "chat_id", "msg_id", name="uq_tracked_msg"),
    )
    op.create_index("ix_tracked_messages_account_id", "tracked_messages", ["account_id"])

    op.create_table(
        "message_stat_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tracked_id", sa.Integer(), sa.ForeignKey("tracked_messages.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("views", sa.Integer()),
        sa.Column("forwards", sa.Integer()),
        sa.Column("reactions_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("replies_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("taken_at", TS, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_message_stat_snapshots_tracked_id", "message_stat_snapshots", ["tracked_id"])

    op.create_table(
        "comments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tracked_id", sa.Integer(), sa.ForeignKey("tracked_messages.id", ondelete="CASCADE")),
        sa.Column("kind", sa.String(16), nullable=False, server_default="reply"),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("chat_title", sa.String(255)),
        sa.Column("msg_id", sa.Integer(), nullable=False),
        sa.Column("reply_to_msg_id", sa.Integer()),
        sa.Column("sender_id", sa.BigInteger()),
        sa.Column("sender_name", sa.String(255)),
        sa.Column("sender_username", sa.String(64)),
        sa.Column("text", sa.Text()),
        sa.Column("link", sa.String(512)),
        sa.Column("date", TS),
        sa.Column("created_at", TS, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("account_id", "chat_id", "msg_id", name="uq_comment_msg"),
    )
    op.create_index("ix_comments_account_id", "comments", ["account_id"])
    op.create_index("ix_comments_tracked_id", "comments", ["tracked_id"])
    op.create_index("ix_comments_date", "comments", ["date"])


def downgrade() -> None:
    op.drop_table("comments")
    op.drop_table("message_stat_snapshots")
    op.drop_table("tracked_messages")
    op.drop_table("bulk_task_items")
    op.drop_table("bulk_tasks")
    op.drop_table("accounts")
    op.drop_table("panel_users")
