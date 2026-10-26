"""media files of saved messages in the file storage (S3)

Revision ID: 0004_message_media
Revises: 0003_proxies
Create Date: 2026-10-26

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_message_media"
down_revision: Union[str, None] = "0003_proxies"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("message", sa.Column("media_size", sa.BigInteger()))
    op.add_column("message", sa.Column("media_mime", sa.String(128)))
    op.add_column("message", sa.Column("media_name", sa.String(255)))
    op.add_column("message", sa.Column("media_status", sa.String(16)))
    op.add_column("message", sa.Column("media_key", sa.String(512)))
    op.add_column("message", sa.Column("media_error", sa.Text()))
    op.create_index(
        "ix_message_media_pending", "message", ["id"], postgresql_where=sa.text("media_status = 'pending'")
    )


def downgrade() -> None:
    op.drop_index("ix_message_media_pending", table_name="message")
    for column in ("media_error", "media_key", "media_status", "media_name", "media_mime", "media_size"):
        op.drop_column("message", column)
