from telethon import types
from telethon import utils as tg_utils

from app.application.dto import ChatInfo, Dialog, TgMessage, TgProfile, TgUserInfo


def chat_username(e) -> str | None:
    username = getattr(e, "username", None)
    if not username and getattr(e, "usernames", None):
        active = [u.username for u in e.usernames if getattr(u, "active", False)]
        username = active[0] if active else None
    return username


def entity_type(e) -> str:
    if isinstance(e, types.User):
        return "bot" if e.bot else "user"
    if isinstance(e, (types.Chat, types.ChatForbidden)):
        return "group"
    if isinstance(e, (types.Channel, types.ChannelForbidden)):
        return "channel" if getattr(e, "broadcast", False) else "supergroup"
    return "unknown"


def is_member(e) -> bool:
    if isinstance(e, types.Channel):
        return not e.left
    if isinstance(e, types.Chat):
        return not (e.left or e.deactivated)
    return True


def can_send(e, require_member: bool = True) -> tuple[bool, str]:
    if isinstance(e, types.User):
        if e.deleted:
            return False, "Пользователь удалён"
        return True, ""
    if isinstance(e, (types.ChatForbidden, types.ChannelForbidden)):
        return False, "Доступ к чату запрещён"
    if isinstance(e, types.Chat):
        if e.deactivated or e.migrated_to:
            return False, "Группа деактивирована/мигрировала"
        if require_member and e.left:
            return False, "Аккаунт не состоит в чате"
        if e.creator or e.admin_rights:
            return True, ""
        if e.default_banned_rights and e.default_banned_rights.send_messages:
            return False, "В чате запрещено писать участникам"
        return True, ""
    if isinstance(e, types.Channel):
        is_admin = bool(e.creator or e.admin_rights)
        if e.broadcast:
            if e.creator or (e.admin_rights and e.admin_rights.post_messages):
                return True, ""
            return False, "Канал: нет прав на публикацию"
        if require_member and e.left:
            return False, "Аккаунт не состоит в чате"
        if e.banned_rights and e.banned_rights.send_messages:
            return False, "Аккаунт ограничен в чате"
        if (
            not is_admin
            and e.default_banned_rights
            and e.default_banned_rights.send_messages
        ):
            return False, "В чате запрещено писать участникам"
        return True, ""
    return False, "Неизвестный тип чата"


def reactions_of(m) -> list[dict]:
    res: list[dict] = []
    reactions = getattr(m, "reactions", None)
    if reactions and reactions.results:
        for rc in reactions.results:
            r = rc.reaction
            if isinstance(r, types.ReactionEmoji):
                key = r.emoticon
            elif isinstance(r, types.ReactionCustomEmoji):
                key = "custom"
            else:
                key = "⭐"
            res.append({"emoji": key, "count": rc.count})
    return res


def media_kind(m) -> str | None:
    if not getattr(m, "media", None):
        return None
    for attr in (
        "photo",
        "video",
        "voice",
        "video_note",
        "sticker",
        "gif",
        "audio",
        "poll",
        "contact",
        "geo",
    ):
        if getattr(m, attr, None):
            return attr
    if getattr(m, "document", None):
        return "file"
    if getattr(m, "web_preview", None):
        return None
    return "media"


def chat_info(e) -> ChatInfo:
    return ChatInfo(
        id=tg_utils.get_peer_id(e),
        title=tg_utils.get_display_name(e),
        username=chat_username(e),
        type=entity_type(e),
        access_hash=getattr(e, "access_hash", None),
    )


def profile(u: types.User) -> TgProfile:
    return TgProfile(
        id=u.id,
        phone=u.phone,
        username=u.username,
        first_name=u.first_name,
        last_name=u.last_name,
    )


def user_info(u: types.User) -> TgUserInfo:
    return TgUserInfo(
        id=u.id,
        username=chat_username(u),
        first_name=u.first_name,
        last_name=u.last_name,
        phone=u.phone,
        is_bot=bool(u.bot),
        is_premium=bool(getattr(u, "premium", False)),
        is_deleted=bool(u.deleted),
        is_min=bool(getattr(u, "min", False)),
    )


def message(m) -> TgMessage | None:
    if m is None or isinstance(m, types.MessageEmpty):
        return None
    is_service = isinstance(m, types.MessageService)
    sender = getattr(m, "sender", None)
    reply_to = getattr(m, "reply_to", None)
    replies = getattr(m, "replies", None)
    file = None if is_service else getattr(m, "file", None)
    return TgMessage(
        id=m.id,
        chat_id=tg_utils.get_peer_id(m.peer_id),
        date=m.date,
        text=(type(m.action).__name__ if is_service else m.message) or "",
        is_service=is_service,
        out=bool(m.out),
        post=bool(getattr(m, "post", False)),
        sender_id=m.sender_id,
        sender_name=tg_utils.get_display_name(sender) if sender else None,
        sender_username=chat_username(sender) if sender else None,
        sender_user=user_info(sender) if isinstance(sender, types.User) else None,
        views=getattr(m, "views", None),
        forwards=getattr(m, "forwards", None),
        replies=replies.replies if replies else None,
        reactions=reactions_of(m),
        reply_to_msg_id=(
            getattr(reply_to, "reply_to_msg_id", None) if reply_to else None
        ),
        reply_to_top_id=(
            getattr(reply_to, "reply_to_top_id", None) if reply_to else None
        ),
        media=None if is_service else media_kind(m),
        media_size=file.size if file else None,
        media_mime=file.mime_type if file else None,
        media_name=file.name if file else None,
        grouped_id=getattr(m, "grouped_id", None),
        edit_date=getattr(m, "edit_date", None),
    )


def messages(items) -> list[TgMessage]:
    return [x for x in (message(m) for m in items) if x is not None]


def dialog(d) -> Dialog:
    e = d.entity
    ok, reason = can_send(e)
    msg = d.message
    return Dialog(
        id=d.id,
        title=d.name or "",
        username=chat_username(e),
        type=entity_type(e),
        unread=d.unread_count,
        unread_mentions=getattr(d, "unread_mentions_count", 0),
        pinned=d.pinned,
        archived=d.archived,
        participants=getattr(e, "participants_count", None),
        is_admin=bool(getattr(e, "creator", False) or getattr(e, "admin_rights", None)),
        can_send=ok,
        cant_send_reason=reason or None,
        last_text=(
            (msg.message or "")
            if msg and not isinstance(msg, types.MessageService)
            else ""
        )[:120],
        last_date=msg.date if msg else None,
        top_message_id=msg.id if msg else 0,
        is_group=bool(d.is_group),
        unread_reactions=getattr(d.dialog, "unread_reactions_count", 0) or 0,
        unread_mark=bool(getattr(d.dialog, "unread_mark", False)),
        forum=bool(getattr(e, "forum", False)),
    )
