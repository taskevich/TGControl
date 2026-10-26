from app.application.dto import AccountView, ChatInfo, Dialog, JoinResult, TgMessage
from app.application.use_cases.proxies import ProxyView
from app.domain.entities import ChatMessage
from app.domain.values import tme_link
from app.presentation.http.schemas import AccountOut, MessageOut, ProxyOut


def account(view: AccountView) -> AccountOut:
    out = AccountOut.model_validate(view.account)
    out.twofa = view.twofa
    out.connected = view.connected
    return out


def proxy(view: ProxyView) -> ProxyOut:
    out = ProxyOut.model_validate(view.proxy)
    out.has_password = bool(view.proxy.password_enc)
    out.accounts_count = view.accounts_count
    out.url_masked = view.url_masked
    return out


def chat_message(m: ChatMessage, media_url: str | None = None) -> MessageOut:
    out = MessageOut.model_validate(m)
    out.link = tme_link(m.chat_username, m.chat_id, m.msg_id)
    out.media_url = media_url
    return out


def tg_message(m: TgMessage) -> dict:
    return {
        "id": m.id,
        "date": m.date.isoformat() if m.date else None,
        "text": m.text,
        "is_service": m.is_service,
        "out": m.out,
        "sender_id": m.sender_id,
        "sender_name": m.sender_name,
        "sender_username": m.sender_username,
        "views": m.views,
        "forwards": m.forwards,
        "replies": m.replies,
        "reactions": m.reactions,
        "reactions_total": m.reactions_total,
        "reply_to_msg_id": m.reply_to_msg_id,
        "media": m.media,
    }


def dialog(d: Dialog) -> dict:
    return {
        "id": d.id,
        "title": d.title,
        "username": d.username,
        "type": d.type,
        "unread": d.unread,
        "unread_mentions": d.unread_mentions,
        "pinned": d.pinned,
        "archived": d.archived,
        "participants": d.participants,
        "is_admin": d.is_admin,
        "can_send": d.can_send,
        "cant_send_reason": d.cant_send_reason,
        "last_text": d.last_text,
        "last_date": d.last_date.isoformat() if d.last_date else None,
    }


def chat(c: ChatInfo | None) -> dict | None:
    if c is None:
        return None
    return {"id": c.id, "title": c.title, "username": c.username, "type": c.type}


def join_result(r: JoinResult) -> dict:
    return {"status": r.status, "detail": r.detail, "chat": chat(r.chat)}
