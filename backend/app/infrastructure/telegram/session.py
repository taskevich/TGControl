import os

from telethon import TelegramClient, errors, types
from telethon import utils as tg_utils
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import (
    CheckChatInviteRequest,
    GetDiscussionMessageRequest,
    ImportChatInviteRequest,
    MarkDialogUnreadRequest,
    ReadDiscussionRequest,
    ReadMentionsRequest,
    ReadReactionsRequest,
)
from telethon.tl.types import InputMessagesFilterMyMentions

try:
    from telethon.tl.functions.messages import GetForumTopicsRequest
except ImportError:
    from telethon.tl.functions.channels import GetForumTopicsRequest

from app.application.dto import (
    ChatInfo,
    Dialog,
    DownloadedMedia,
    JoinResult,
    LocatedMessage,
    SentMessage,
    TgMessage,
    TgProfile,
)
from app.domain.errors import (
    InvalidInput,
    MediaTooLarge,
    NotFound,
    OperationSkipped,
    TelegramError,
)
from app.domain.values import Target, parse_target
from app.infrastructure.telegram import converters as conv
from app.infrastructure.telegram.client import rpc_errors, translated

WRITE_FORBIDDEN = rpc_errors(
    "ChatWriteForbiddenError",
    "ChatSendPlainForbiddenError",
    "ChatGuestSendForbiddenError",
    "UserBannedInChannelError",
    "ChatRestrictedError",
    "ChatAdminRequiredError",
    "UserIsBlockedError",
    "YouBlockedUserError",
    "PrivacyPremiumRequiredError",
    "ChannelPrivateError",
    "PeerIdInvalidError",
)
JOIN_REQUEST_SENT = rpc_errors("InviteRequestSentError")
ALREADY_PARTICIPANT = rpc_errors("UserAlreadyParticipantError")
INVITE_BAD = rpc_errors(
    "InviteHashExpiredError", "InviteHashInvalidError", "InviteHashEmptyError"
)
TOPICS_PAGE = 100
TOPICS_MAX_PAGES = 20


def _input_peer(chat_id: int, access_hash: int | None):
    real_id, peer_cls = tg_utils.resolve_id(chat_id)
    if peer_cls is types.PeerChannel:
        return types.InputPeerChannel(real_id, access_hash or 0)
    if peer_cls is types.PeerChat:
        return types.InputPeerChat(real_id)
    return types.InputPeerUser(real_id, access_hash or 0)


class TelethonSession:
    def __init__(self, client: TelegramClient):
        self.client = client

    async def _entity_by_id(self, peer_id: int):
        try:
            return await self.client.get_entity(peer_id)
        except ValueError:
            await self.client.get_dialogs(limit=None)
            return await self.client.get_entity(peer_id)

    async def _resolve(self, target: Target):
        c = self.client
        if target.kind in ("username", "public_msg"):
            return await c.get_entity(target.username)
        if target.kind == "invite":
            info = await c(CheckChatInviteRequest(target.invite_hash))
            if isinstance(info, (types.ChatInviteAlready, types.ChatInvitePeek)):
                return info.chat
            raise OperationSkipped("Аккаунт не состоит в чате по этому инвайту")
        if target.kind in ("id", "private_msg"):
            try:
                return await self._entity_by_id(target.peer_id)
            except ValueError as e:
                raise OperationSkipped("Чат не найден у этого аккаунта") from e
        raise InvalidInput(f"Неизвестный тип цели: {target.kind}")

    async def _refresh(self, entity):
        try:
            return await self.client.get_entity(entity)
        except Exception:  # noqa: BLE001
            return entity

    async def _stored_peer(self, chat_id: int, access_hash: int | None):
        _, peer_cls = tg_utils.resolve_id(chat_id)
        if access_hash or peer_cls is types.PeerChat:
            return _input_peer(chat_id, access_hash)
        return await self._entity_by_id(chat_id)

    @translated
    async def get_me(self) -> TgProfile:
        return conv.profile(await self.client.get_me())

    @translated
    async def log_out(self) -> None:
        await self.client.log_out()

    @translated
    async def edit_2fa(
        self, current_password: str | None, new_password: str, hint: str = ""
    ) -> None:
        await self.client.edit_2fa(
            current_password=current_password, new_password=new_password, hint=hint
        )

    @translated
    async def dialogs(self, limit: int) -> list[Dialog]:
        return [conv.dialog(d) for d in await self.client.get_dialogs(limit=limit)]

    @translated
    async def history(
        self, peer_id: int, *, offset_id: int, limit: int
    ) -> tuple[ChatInfo, list[TgMessage]]:
        entity = await self._entity_by_id(peer_id)
        msgs = await self.client.get_messages(entity, limit=limit, offset_id=offset_id)
        return conv.chat_info(entity), conv.messages(msgs)

    @translated
    async def new_messages(
        self, peer_id: int, *, after_id: int, limit: int
    ) -> tuple[ChatInfo, list[TgMessage]]:
        entity = await self._entity_by_id(peer_id)
        if after_id > 0:
            msgs = [
                m
                async for m in self.client.iter_messages(
                    entity, min_id=after_id, reverse=True, limit=limit
                )
            ]
        else:
            msgs = list(await self.client.get_messages(entity, limit=limit))
        return conv.chat_info(entity), sorted(
            conv.messages(msgs), key=lambda m: m.id, reverse=True
        )

    @translated
    async def replies(self, peer_id: int, msg_id: int) -> list[TgMessage]:
        entity = await self._entity_by_id(peer_id)
        msg = await self.client.get_messages(entity, ids=msg_id)
        if not msg:
            raise InvalidInput("Сообщение не найдено")
        return await self._collect_replies(entity, conv.message(msg))

    @translated
    async def fetch_by_ids(
        self, chat_id: int, access_hash: int | None, ids: list[int]
    ) -> list[TgMessage | None]:
        peer = await self._stored_peer(chat_id, access_hash)
        return [conv.message(m) for m in await self.client.get_messages(peer, ids=ids)]

    @translated
    async def replies_to(
        self, chat_id: int, access_hash: int | None, message: TgMessage
    ) -> list[TgMessage]:
        return await self._collect_replies(
            await self._stored_peer(chat_id, access_hash), message
        )

    @translated
    async def mentions(self, chat_id: int, limit: int) -> list[TgMessage]:
        entity = await self._entity_by_id(chat_id)
        return conv.messages(
            [
                m
                async for m in self.client.iter_messages(
                    entity, filter=InputMessagesFilterMyMentions, limit=limit
                )
            ]
        )

    @translated
    async def download_media(
        self, chat_id: int, msg_id: int, dest_dir: str, max_size: int
    ) -> DownloadedMedia:
        entity = await self._entity_by_id(chat_id)
        msg = await self.client.get_messages(entity, ids=msg_id)
        if not msg or isinstance(msg, types.MessageEmpty):
            raise NotFound("Сообщение удалено")
        file = msg.file
        if file is None:
            raise InvalidInput("У сообщения нет файла")
        if file.size and file.size > max_size:
            raise MediaTooLarge(file.size, max_size)
        path = await self.client.download_media(msg, file=dest_dir)
        if not path or not os.path.isfile(path):
            raise TelegramError("Не удалось скачать файл")
        return DownloadedMedia(
            path,
            os.path.getsize(path),
            file.mime_type,
            file.name or os.path.basename(path),
        )

    @translated
    async def unread_dialogs(self) -> list[Dialog]:
        return [
            d
            for d in (conv.dialog(x) for x in await self.client.get_dialogs(limit=None))
            if d.has_unread
        ]

    @translated
    async def read_dialog(self, dialog: Dialog) -> int:
        peer = await self.client.get_input_entity(dialog.id)
        topics = await self._read_topics(peer) if dialog.forum else 0
        await self.client.send_read_acknowledge(
            peer,
            max_id=dialog.top_message_id or 0,
            clear_mentions=bool(dialog.unread_mentions),
            clear_reactions=bool(dialog.unread_reactions),
        )
        if dialog.unread_mark:
            await self.client(
                MarkDialogUnreadRequest(peer=types.InputDialogPeer(peer), unread=False)
            )
        return topics

    async def _read_topics(self, peer) -> int:
        read, offset_date, offset_id, offset_topic = 0, None, 0, 0
        for _ in range(TOPICS_MAX_PAGES):
            res = await self.client(
                GetForumTopicsRequest(
                    peer, offset_date, offset_id, offset_topic, TOPICS_PAGE
                )
            )
            topics = [t for t in res.topics if isinstance(t, types.ForumTopic)]
            for t in topics:
                if not (
                    t.unread_count
                    or t.unread_mentions_count
                    or t.unread_reactions_count
                ):
                    continue
                if t.unread_count:
                    await self.client(
                        ReadDiscussionRequest(
                            peer, msg_id=t.id, read_max_id=t.top_message
                        )
                    )
                if t.unread_mentions_count:
                    await self.client(ReadMentionsRequest(peer, top_msg_id=t.id))
                if t.unread_reactions_count:
                    await self.client(ReadReactionsRequest(peer, top_msg_id=t.id))
                read += 1
            if len(res.topics) < TOPICS_PAGE or not topics:
                break
            last = topics[-1]
            top = next((m for m in res.messages if m.id == last.top_message), None)
            offset_date, offset_id, offset_topic = (
                (top.date if top else None),
                last.top_message,
                last.id,
            )
        return read

    async def _collect_replies(
        self, peer, msg: TgMessage, limit: int = 300
    ) -> list[TgMessage]:
        found: dict[int, object] = {}
        top = msg.thread_root_id
        roots = [msg.id] + ([top] if top and top != msg.id else [])

        for root in roots:
            try:
                async for r in self.client.iter_messages(
                    peer, reply_to=root, limit=limit
                ):
                    if r.id == msg.id:
                        continue
                    if root == msg.id or (
                        r.reply_to and r.reply_to.reply_to_msg_id == msg.id
                    ):
                        found[r.id] = r
            except errors.RPCError:
                continue
            if found:
                break

        if not found and not msg.post:
            try:
                async for r in self.client.iter_messages(
                    peer, min_id=msg.id, limit=limit
                ):
                    if r.reply_to and r.reply_to.reply_to_msg_id == msg.id:
                        found[r.id] = r
            except errors.RPCError:
                pass
        return conv.messages(found.values())

    @translated
    async def locate(self, link: str) -> LocatedMessage:
        t = parse_target(link)
        if not t.msg_id:
            raise InvalidInput(
                "Нужна ссылка на сообщение: https://t.me/chat/123 или https://t.me/c/123/456"
            )
        entity = await self._resolve(t)
        is_comment, parent_link, top = False, None, None
        if t.comment_id and isinstance(entity, types.Channel) and entity.broadcast:
            disc = await self.client(
                GetDiscussionMessageRequest(peer=entity, msg_id=t.msg_id)
            )
            root = disc.messages[0]
            gid = tg_utils.get_peer_id(root.peer_id)
            entity = next(c for c in disc.chats if tg_utils.get_peer_id(c) == gid)
            msg = await self.client.get_messages(entity, ids=t.comment_id)
            is_comment, parent_link, top = True, link.split("?")[0], root.id
        else:
            msg = await self.client.get_messages(entity, ids=t.msg_id)
        found = conv.message(msg)
        if not found:
            raise InvalidInput("Сообщение не найдено")
        return LocatedMessage(
            found, conv.chat_info(entity), is_comment, parent_link, top
        )

    @translated
    async def join(self, target: Target) -> JoinResult:
        c = self.client
        if target.kind == "invite":
            try:
                info = await c(CheckChatInviteRequest(target.invite_hash))
            except INVITE_BAD as e:
                raise OperationSkipped(
                    f"Инвайт недействителен: {type(e).__name__}"
                ) from e
            if isinstance(info, types.ChatInviteAlready):
                return JoinResult("skipped", "Уже в чате", conv.chat_info(info.chat))
            try:
                updates = await c(ImportChatInviteRequest(target.invite_hash))
            except ALREADY_PARTICIPANT:
                return JoinResult("skipped", "Уже в чате")
            except JOIN_REQUEST_SENT:
                return JoinResult("ok", "Заявка на вступление отправлена")
            chat = updates.chats[0] if getattr(updates, "chats", None) else None
            return JoinResult("ok", "Вступил", conv.chat_info(chat) if chat else None)

        entity = await self._resolve(target)
        if isinstance(entity, types.User):
            raise OperationSkipped("Это пользователь, а не чат")
        if conv.is_member(entity):
            return JoinResult("skipped", "Уже в чате", conv.chat_info(entity))
        if isinstance(entity, types.Chat):
            raise OperationSkipped("В обычную группу можно вступить только по инвайту")
        try:
            await c(JoinChannelRequest(entity))
        except ALREADY_PARTICIPANT:
            return JoinResult("skipped", "Уже в чате", conv.chat_info(entity))
        except JOIN_REQUEST_SENT:
            return JoinResult(
                "ok", "Заявка на вступление отправлена", conv.chat_info(entity)
            )
        return JoinResult("ok", "Вступил", conv.chat_info(entity))

    @translated
    async def leave(self, target: Target) -> JoinResult:
        entity = await self._resolve(target)
        if isinstance(entity, types.User):
            raise OperationSkipped("Это пользователь, а не чат")
        if not conv.is_member(entity):
            raise OperationSkipped("Аккаунт не состоит в чате")
        await self.client.delete_dialog(entity)
        return JoinResult("ok", "Вышел из чата", conv.chat_info(entity))

    async def _send(
        self,
        t: Target,
        text: str,
        *,
        join_if_needed: bool,
        reply_to: int | None,
        link_preview: bool,
    ) -> SentMessage:
        entity = await self._resolve(t)
        if not conv.is_member(entity):
            if not join_if_needed:
                raise OperationSkipped("Аккаунт не состоит в чате")
            await self.join(t)
            entity = await self._refresh(entity)
        ok, reason = conv.can_send(entity)
        if not ok:
            raise OperationSkipped(reason)
        if reply_to is None and t.is_message_link:
            reply_to = t.comment_id or t.msg_id
        try:
            msg = await self.client.send_message(
                entity, text, reply_to=reply_to, link_preview=link_preview
            )
        except WRITE_FORBIDDEN as e:
            raise OperationSkipped(f"Нет прав на отправку ({type(e).__name__})") from e
        except errors.SlowModeWaitError as e:
            raise OperationSkipped(f"Slow mode: подождать {e.seconds} с") from e
        return SentMessage(conv.message(msg), conv.chat_info(entity))

    @translated
    async def send(
        self,
        target: Target,
        text: str,
        *,
        reply_to: int | None = None,
        join_if_needed: bool = False,
        link_preview: bool = True,
    ) -> SentMessage:
        return await self._send(
            target,
            text,
            join_if_needed=join_if_needed,
            reply_to=reply_to,
            link_preview=link_preview,
        )

    @translated
    async def comment(
        self,
        post: Target,
        text: str,
        *,
        join_if_needed: bool = False,
        link_preview: bool = True,
    ) -> SentMessage:
        t = post
        if not t.is_message_link or not t.msg_id:
            raise InvalidInput(
                "Нужна ссылка на пост канала, например https://t.me/channel/123"
            )
        channel = await self._resolve(t)
        if not isinstance(channel, types.Channel) or not channel.broadcast:
            # Link to a message in a group – just reply to it.
            sent = await self._send(
                t,
                text,
                join_if_needed=join_if_needed,
                reply_to=None,
                link_preview=link_preview,
            )
            return SentMessage(sent.message, sent.chat, sent.message.reply_to_top_id)

        try:
            disc = await self.client(
                GetDiscussionMessageRequest(peer=channel, msg_id=t.msg_id)
            )
        except (errors.MsgIdInvalidError, *rpc_errors("ChannelPrivateError")) as e:
            raise OperationSkipped("Комментарии к посту недоступны") from e
        if not disc.messages:
            raise OperationSkipped("Комментарии к посту отключены")
        root = disc.messages[0]
        group_id = tg_utils.get_peer_id(root.peer_id)
        group = next(
            (c for c in disc.chats if tg_utils.get_peer_id(c) == group_id), None
        )
        if group is None:
            raise OperationSkipped("Не найдена группа обсуждения")

        if (
            isinstance(group, types.Channel)
            and group.left
            and getattr(group, "join_to_send", False)
        ):
            if not join_if_needed:
                raise OperationSkipped(
                    "Для комментариев нужно вступить в группу обсуждения"
                )
            try:
                await self.client(JoinChannelRequest(group))
            except ALREADY_PARTICIPANT:
                pass
            except JOIN_REQUEST_SENT as e:
                raise OperationSkipped(
                    "Отправлена заявка в группу обсуждения, комментировать пока нельзя"
                ) from e
            group = await self._refresh(group)

        ok, reason = conv.can_send(group, require_member=False)
        if not ok:
            raise OperationSkipped(reason)
        try:
            msg = await self.client.send_message(
                group,
                text,
                reply_to=t.comment_id or root.id,
                link_preview=link_preview,
            )
        except WRITE_FORBIDDEN as e:
            raise OperationSkipped(
                f"Нет прав на комментирование ({type(e).__name__})"
            ) from e
        except errors.SlowModeWaitError as e:
            raise OperationSkipped(f"Slow mode: подождать {e.seconds} с") from e
        return SentMessage(conv.message(msg), conv.chat_info(group), root.id)
