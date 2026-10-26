"""proxies table, binding of a proxy to an account

Moves existing per-account proxy strings (accounts.proxy) into the proxies table.

Revision ID: 0003_proxies
Revises: 0002_messages
Create Date: 2026-10-20

"""
from typing import Sequence, Union
from urllib.parse import quote, unquote, urlparse

import sqlalchemy as sa
from alembic import op

revision: str = "0003_proxies"
down_revision: Union[str, None] = "0002_messages"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TS = sa.DateTime(timezone=True)


def _parse(proxy: str):
    proxy = proxy.strip()
    if "://" in proxy:
        u = urlparse(proxy)
        return (
            u.scheme.lower(), u.hostname, u.port,
            unquote(u.username) if u.username else None, unquote(u.password) if u.password else None,
        )
    parts = proxy.split(":")
    return (
        "socks5", parts[0], int(parts[1]),
        parts[2] if len(parts) > 2 else None, parts[3] if len(parts) > 3 else None,
    )


def _cipher():
    from app.infrastructure.config import settings
    from app.infrastructure.security import FernetCipher

    return FernetCipher(settings.SESSION_ENCRYPTION_KEY, settings.SECRET_KEY)


def upgrade() -> None:
    op.create_table(
        "proxies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(128)),
        sa.Column("scheme", sa.String(10), nullable=False, server_default="socks5"),
        sa.Column("host", sa.String(255), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(255)),
        sa.Column("password_enc", sa.Text()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("status", sa.String(16), nullable=False, server_default="unknown"),
        sa.Column("status_detail", sa.Text()),
        sa.Column("latency_ms", sa.Integer()),
        sa.Column("checked_at", TS),
        sa.Column("created_at", TS, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("scheme", "host", "port", "username", name="uq_proxy"),
    )
    op.add_column("accounts", sa.Column("proxy_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_accounts_proxy_id", "accounts", "proxies", ["proxy_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_accounts_proxy_id", "accounts", ["proxy_id"])

    encrypt = _cipher().encrypt

    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, proxy FROM accounts WHERE proxy IS NOT NULL AND proxy <> ''")).all()
    known: dict[tuple, int] = {}
    for account_id, raw in rows:
        try:
            scheme, host, port, user, pwd = _parse(raw)
        except (ValueError, IndexError):
            continue
        if not host or not port:
            continue
        key = (scheme, host, port, user)
        if key not in known:
            known[key] = conn.execute(
                sa.text(
                    "INSERT INTO proxies (scheme, host, port, username, password_enc, is_active, status) "
                    "VALUES (:s, :h, :p, :u, :pw, true, 'unknown') RETURNING id"
                ),
                {"s": scheme, "h": host, "p": port, "u": user, "pw": encrypt(pwd) if pwd else None},
            ).scalar_one()
        conn.execute(
            sa.text("UPDATE accounts SET proxy_id = :pid WHERE id = :aid"), {"pid": known[key], "aid": account_id}
        )

    op.drop_column("accounts", "proxy")


def downgrade() -> None:
    decrypt = _cipher().decrypt

    op.add_column("accounts", sa.Column("proxy", sa.String(255)))
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT a.id, p.scheme, p.host, p.port, p.username, p.password_enc "
            "FROM accounts a JOIN proxies p ON p.id = a.proxy_id"
        )
    ).all()
    for aid, scheme, host, port, user, pwd_enc in rows:
        auth = ""
        if user:
            pwd = decrypt(pwd_enc) if pwd_enc else ""
            auth = f"{quote(user, safe='')}:{quote(pwd, safe='')}@"
        conn.execute(
            sa.text("UPDATE accounts SET proxy = :p WHERE id = :aid"),
            {"p": f"{scheme}://{auth}{host}:{port}", "aid": aid},
        )
    op.drop_index("ix_accounts_proxy_id", table_name="accounts")
    op.drop_constraint("fk_accounts_proxy_id", "accounts", type_="foreignkey")
    op.drop_column("accounts", "proxy_id")
    op.drop_table("proxies")
