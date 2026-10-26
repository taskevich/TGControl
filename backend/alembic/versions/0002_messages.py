"""saved chat messages and telegram users

Revision ID: 0002_messages
Revises: 0001_initial
Create Date: 2026-10-20

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_messages"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "tg_user",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=False),
        sa.Column("username", sa.String(64)),
        sa.Column("first_name", sa.String(255)),
        sa.Column("last_name", sa.String(255)),
        sa.Column("phone", sa.String(32)),
        sa.Column("is_bot", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_premium", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("first_seen_at", TS, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TS, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_tg_user_username", "tg_user", ["username"])

    op.create_table(
        "message",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("chat_title", sa.String(255)),
        sa.Column("chat_username", sa.String(64)),
        sa.Column("chat_type", sa.String(16)),
        sa.Column("msg_id", sa.Integer(), nullable=False),
        sa.Column("sender_id", sa.BigInteger()),
        sa.Column("tg_user_id", sa.BigInteger(), sa.ForeignKey("tg_user.id", ondelete="SET NULL")),
        sa.Column("sender_name", sa.String(255)),
        sa.Column("out", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_service", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("text", sa.Text()),
        sa.Column("media", sa.String(32)),
        sa.Column("reply_to_msg_id", sa.Integer()),
        sa.Column("thread_top_id", sa.Integer()),
        sa.Column("grouped_id", sa.BigInteger()),
        sa.Column("views", sa.Integer()),
        sa.Column("forwards", sa.Integer()),
        sa.Column("replies", sa.Integer()),
        sa.Column("reactions", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("reactions_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("date", TS),
        sa.Column("edit_date", TS),
        sa.Column("created_at", TS, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TS, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("account_id", "chat_id", "msg_id", name="uq_message"),
    )
    op.create_index("ix_message_account_id", "message", ["account_id"])
    op.create_index("ix_message_chat_id", "message", ["chat_id"])
    op.create_index("ix_message_sender_id", "message", ["sender_id"])
    op.create_index("ix_message_tg_user_id", "message", ["tg_user_id"])
    op.create_index("ix_message_date_id", "message", ["date", "id"])
    op.create_index("ix_message_account_chat_date", "message", ["account_id", "chat_id", "date"])


def downgrade() -> None:
    op.drop_table("message")
    op.drop_table("tg_user")
