"""Read-only aggregates for the statistics pages."""

from datetime import timedelta

from sqlalchemy import Date, case, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import utcnow
from app.domain.values import tme_link
from app.infrastructure.db.models import (
    AccountModel,
    CommentModel,
    MessageModel,
    TgUserModel,
    TrackedMessageModel,
)


def _account_label(aid, phone, username, first_name) -> str:
    return (f"@{username}" if username else None) or phone or first_name or f"#{aid}"


class SqlStatsQueries:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def summary(self, days: int, account_id: int | None) -> dict:
        db, T, A, C = self.db, TrackedMessageModel, AccountModel, CommentModel
        acc_rows = (await db.execute(select(A.status, func.count()).group_by(A.status))).all()

        tm_filter = [T.account_id == account_id] if account_id else []
        sums = (
            func.coalesce(func.sum(T.views), 0),
            func.coalesce(func.sum(T.reactions_total), 0),
            func.coalesce(func.sum(T.replies_count), 0),
        )
        totals = (await db.execute(select(func.count(T.id), *sums).where(*tm_filter))).one()

        since = utcnow() - timedelta(days=days)
        day = cast(T.sent_at, Date)
        daily = (
            await db.execute(
                select(day, func.count(T.id), *sums).where(T.sent_at >= since, *tm_filter).group_by(day).order_by(day)
            )
        ).all()

        per_account = (
            await db.execute(
                select(A.id, A.phone, A.username, A.first_name, func.count(T.id), *sums)
                .join(T, T.account_id == A.id)
                .group_by(A.id)
                .order_by(func.count(T.id).desc())
            )
        ).all()

        c_filter = [C.account_id == account_id] if account_id else []
        comments_total = await db.scalar(select(func.count(C.id)).where(*c_filter))
        comments_day = await db.scalar(
            select(func.count(C.id)).where(C.date >= utcnow() - timedelta(days=1), *c_filter)
        )

        return {
            "accounts": {status: count for status, count in acc_rows},
            "messages": totals[0],
            "views": int(totals[1]),
            "reactions": int(totals[2]),
            "replies": int(totals[3]),
            "comments_total": comments_total or 0,
            "comments_24h": comments_day or 0,
            "daily": [
                {"date": d.isoformat(), "messages": c, "views": int(v), "reactions": int(r), "replies": int(rp)}
                for d, c, v, r, rp in daily
            ],
            "per_account": [
                {"account_id": aid, "label": _account_label(aid, phone, un, fn), "messages": c, "views": int(v),
                 "reactions": int(r), "replies": int(rp)}
                for aid, phone, un, fn, c, v, r, rp in per_account
            ],
        }

    async def chat_messages(self, days: int, top: int, account_id: int | None) -> dict:
        db, M, A, U = self.db, MessageModel, AccountModel, TgUserModel
        where = [M.date >= utcnow() - timedelta(days=days)]
        if account_id:
            where.append(M.account_id == account_id)

        out_i = case((M.out.is_(True), 1), else_=0)
        in_i = case((M.out.is_(False), 1), else_=0)
        out_views = func.coalesce(func.sum(case((M.out.is_(True), M.views), else_=0)), 0)
        out_reacts = func.coalesce(func.sum(case((M.out.is_(True), M.reactions_total), else_=0)), 0)
        out_replies = func.coalesce(func.sum(case((M.out.is_(True), M.replies), else_=0)), 0)

        t = (
            await db.execute(
                select(
                    func.count(M.id),
                    func.coalesce(func.sum(in_i), 0),
                    func.coalesce(func.sum(out_i), 0),
                    func.count(func.distinct(func.concat(M.account_id, ":", M.chat_id))),
                    func.count(func.distinct(M.tg_user_id)),
                    func.coalesce(func.sum(M.views), 0),
                    func.coalesce(func.sum(M.reactions_total), 0),
                    out_views,
                    out_reacts,
                    out_replies,
                ).where(*where)
            )
        ).one()
        totals = {
            "messages": t[0], "incoming": int(t[1]), "outgoing": int(t[2]), "chats": t[3], "users": t[4],
            "views": int(t[5]), "reactions": int(t[6]),
            "out_views": int(t[7]), "out_reactions": int(t[8]), "out_replies": int(t[9]),
        }

        day = cast(func.timezone("UTC", M.date), Date)
        daily = [
            {"date": d.isoformat(), "incoming": int(i), "outgoing": int(o), "reactions": int(r)}
            for d, i, o, r in (
                await db.execute(
                    select(day, func.sum(in_i), func.sum(out_i), func.coalesce(func.sum(M.reactions_total), 0))
                    .where(*where)
                    .group_by(day)
                    .order_by(day)
                )
            ).all()
        ]

        top_chats = [
            {
                "account_id": a, "chat_id": c, "title": title or str(c), "type": ty, "messages": n,
                "incoming": int(i), "outgoing": int(o), "authors": au, "reactions": int(r), "last_date": ld,
            }
            for a, c, title, ty, n, i, o, au, r, ld in (
                await db.execute(
                    select(
                        M.account_id, M.chat_id, func.max(M.chat_title), func.max(M.chat_type),
                        func.count(M.id), func.sum(in_i), func.sum(out_i), func.count(func.distinct(M.tg_user_id)),
                        func.coalesce(func.sum(M.reactions_total), 0), func.max(M.date),
                    )
                    .where(*where)
                    .group_by(M.account_id, M.chat_id)
                    .order_by(func.count(M.id).desc())
                    .limit(top)
                )
            ).all()
        ]

        top_users = [
            {
                "id": uid, "username": un,
                "name": " ".join(x for x in (fn, ln) if x) or (f"@{un}" if un else f"id{uid}"),
                "is_bot": bot, "messages": n, "chats": ch, "reactions": int(r), "last_date": ld,
            }
            for uid, un, fn, ln, bot, n, ch, r, ld in (
                await db.execute(
                    select(
                        U.id, U.username, U.first_name, U.last_name, U.is_bot,
                        func.count(M.id), func.count(func.distinct(M.chat_id)),
                        func.coalesce(func.sum(M.reactions_total), 0), func.max(M.date),
                    )
                    .join(M, M.tg_user_id == U.id)
                    .where(*where, M.out.is_(False))
                    .group_by(U.id)
                    .order_by(func.count(M.id).desc())
                    .limit(top)
                )
            ).all()
        ]

        per_account = [
            {
                "account_id": aid, "label": _account_label(aid, ph, un, fn), "messages": n, "incoming": int(i),
                "outgoing": int(o), "chats": ch, "out_views": int(v), "out_reactions": int(r),
                "out_replies": int(rp),
            }
            for aid, ph, un, fn, n, i, o, ch, v, r, rp in (
                await db.execute(
                    select(
                        A.id, A.phone, A.username, A.first_name,
                        func.count(M.id), func.sum(in_i), func.sum(out_i),
                        func.count(func.distinct(M.chat_id)), out_views, out_reacts, out_replies,
                    )
                    .join(M, M.account_id == A.id)
                    .where(*where)
                    .group_by(A.id)
                    .order_by(func.count(M.id).desc())
                )
            ).all()
        ]

        top_out_rows = (
            await db.scalars(
                select(M)
                .where(*where, M.out.is_(True), M.is_service.is_(False))
                .order_by(
                    (func.coalesce(M.reactions_total, 0) * 10 + func.coalesce(M.replies, 0) * 5
                     + func.coalesce(M.views, 0)).desc(),
                    M.date.desc(),
                )
                .limit(top)
            )
        ).all()
        top_outgoing = [
            {
                "id": m.id, "account_id": m.account_id, "chat_title": m.chat_title, "text": (m.text or "")[:300],
                "media": m.media, "date": m.date, "views": m.views, "reactions": m.reactions,
                "reactions_total": m.reactions_total, "replies": m.replies,
                "link": tme_link(m.chat_username, m.chat_id, m.msg_id),
            }
            for m in top_out_rows
        ]

        return {
            "totals": totals,
            "daily": daily,
            "top_chats": top_chats,
            "top_users": top_users,
            "per_account": per_account,
            "top_outgoing": top_outgoing,
        }
