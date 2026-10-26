from datetime import datetime

from fastapi import APIRouter, Depends

from app.container import Container
from app.presentation.http import presenters
from app.presentation.http.deps import container, current_user
from app.presentation.http.schemas import (
    MessageFeedOut,
    MessageOut,
    MessagesSyncIn,
    ReadAllIn,
    SavedChatOut,
    TgUserDetailOut,
    TgUserOut,
)

router = APIRouter(
    prefix="/api/messages", tags=["messages"], dependencies=[Depends(current_user)]
)
users_router = APIRouter(
    prefix="/api/tg-users", tags=["messages"], dependencies=[Depends(current_user)]
)


@router.get("", response_model=MessageFeedOut)
async def feed(
    account_id: int | None = None,
    chat_id: int | None = None,
    sender_id: int | None = None,
    q: str | None = None,
    out: bool | None = None,
    chat_type: str | None = None,
    with_media: bool | None = None,
    media_status: str | None = None,
    media_kind: str | None = None,
    before_date: datetime | None = None,
    before_id: int | None = None,
    after_id: int | None = None,
    limit: int = 50,
    c: Container = Depends(container),
):
    res = await c.messages.feed(
        account_id=account_id,
        chat_id=chat_id,
        sender_id=sender_id,
        q=q,
        out=out,
        chat_type=chat_type,
        with_media=with_media,
        media_status=media_status,
        media_kind=media_kind,
        before_date=before_date,
        before_id=before_id,
        after_id=after_id,
        limit=limit,
    )
    return MessageFeedOut(
        items=[presenters.chat_message(m, c.media.url_for(m)) for m in res.items],
        next_before_date=res.next_before_date,
        next_before_id=res.next_before_id,
    )


@router.get("/chats", response_model=list[SavedChatOut])
async def saved_chats(account_id: int | None = None, c: Container = Depends(container)):
    return [SavedChatOut(**row) for row in await c.messages.chats(account_id)]


@router.get("/summary")
async def summary(account_id: int | None = None, c: Container = Depends(container)):
    return {**await c.messages.summary(account_id), "media_enabled": c.media.enabled}


@router.post("/sync")
async def sync(data: MessagesSyncIn, c: Container = Depends(container)):
    return await c.messages.sync(data.account_id, data.dialog_limit, data.per_chat)


@router.post("/read-all")
async def read_all(data: ReadAllIn, c: Container = Depends(container)):
    return await c.chats.read_all(data.account_id)


@router.get("/{message_id}", response_model=MessageOut)
async def get_message(message_id: int, c: Container = Depends(container)):
    m = await c.messages.get(message_id)
    return presenters.chat_message(m, c.media.url_for(m))


@router.post("/{message_id}/media", response_model=MessageOut)
async def queue_media(message_id: int, c: Container = Depends(container)):
    m = await c.media.retry(message_id)
    return presenters.chat_message(m, c.media.url_for(m))


@users_router.get("", response_model=list[TgUserOut])
async def list_users(
    q: str | None = None, limit: int = 50, c: Container = Depends(container)
):
    return await c.messages.users(q, limit)


@users_router.get("/{user_id}", response_model=TgUserDetailOut)
async def get_user(user_id: int, c: Container = Depends(container)):
    a = await c.messages.user(user_id)
    out = TgUserDetailOut.model_validate(a.user)
    out.messages_count, out.chats_count, out.last_message_at = (
        a.messages_count,
        a.chats_count,
        a.last_message_at,
    )
    return out
