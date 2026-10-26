from app.application.dto import ChatInfo, TgMessage
from app.application.ports.repositories import UnitOfWork
from app.application.ports.telegram import TelegramSession


class MessageArchive:
    def __init__(self, max_media_size: int | None = None):
        self._max_media_size = max_media_size

    async def save(
        self,
        uow: UnitOfWork,
        account_id: int,
        chat: ChatInfo,
        messages: list[TgMessage],
    ) -> int:
        if not messages:
            return 0
        senders = {m.sender_user.id: m.sender_user for m in messages if m.sender_user}
        if senders:
            await uow.tg_users.upsert_many(list(senders.values()))
        inserted = await uow.messages.upsert(
            account_id, chat, messages, self._max_media_size
        )
        await uow.commit()
        return inserted

    async def history(
        self,
        uow: UnitOfWork,
        tg: TelegramSession,
        account_id: int,
        peer_id: int,
        offset_id: int = 0,
        limit: int = 50,
    ) -> list[TgMessage]:
        chat, messages = await tg.history(peer_id, offset_id=offset_id, limit=limit)
        await self.save(uow, account_id, chat, messages)
        return messages

    async def fetch_new(
        self,
        uow: UnitOfWork,
        tg: TelegramSession,
        account_id: int,
        peer_id: int,
        after_id: int,
        limit: int = 100,
    ) -> tuple[list[TgMessage], int]:
        chat, messages = await tg.new_messages(peer_id, after_id=after_id, limit=limit)
        inserted = await self.save(uow, account_id, chat, messages)
        return messages, inserted
