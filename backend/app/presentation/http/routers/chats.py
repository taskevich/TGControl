from fastapi import APIRouter, Depends

from app.container import Container
from app.presentation.http import presenters
from app.presentation.http.deps import container, current_user
from app.presentation.http.schemas import (
    CommentOut,
    CommentPostIn,
    Page,
    SendMessageIn,
    SendToIn,
    TargetIn,
)

router = APIRouter(
    prefix="/api/accounts/{account_id}",
    tags=["chats"],
    dependencies=[Depends(current_user)],
)


@router.get("/dialogs")
async def dialogs(
    account_id: int,
    refresh: bool = False,
    limit: int = 300,
    c: Container = Depends(container),
):
    return [
        presenters.dialog(d) for d in await c.chats.dialogs(account_id, refresh, limit)
    ]


@router.post("/read-all")
async def read_all(account_id: int, c: Container = Depends(container)):
    return await c.chats.read_all(account_id)


@router.get("/dialogs/{peer_id}/messages")
async def messages(
    account_id: int,
    peer_id: int,
    limit: int = 50,
    offset_id: int = 0,
    c: Container = Depends(container),
):
    return [
        presenters.tg_message(m)
        for m in await c.chats.history(account_id, peer_id, limit, offset_id)
    ]


@router.get("/dialogs/{peer_id}/messages/new")
async def new_messages(
    account_id: int,
    peer_id: int,
    after_id: int,
    limit: int = 100,
    c: Container = Depends(container),
):
    msgs, inserted = await c.chats.new_messages(account_id, peer_id, after_id, limit)
    return {"items": [presenters.tg_message(m) for m in msgs], "new": inserted}


@router.post("/dialogs/{peer_id}/send")
async def send(
    account_id: int,
    peer_id: int,
    data: SendMessageIn,
    c: Container = Depends(container),
):
    msg, tracked_id = await c.chats.send(
        account_id,
        peer_id,
        data.text,
        reply_to=data.reply_to,
        track=data.track,
        link_preview=data.link_preview,
    )
    return {"message": presenters.tg_message(msg), "tracked_id": tracked_id}


@router.post("/send-to")
async def send_to(account_id: int, data: SendToIn, c: Container = Depends(container)):
    msg, tracked_id = await c.chats.send_to(
        account_id,
        data.target,
        data.text,
        track=data.track,
        link_preview=data.link_preview,
    )
    return {"message": presenters.tg_message(msg), "tracked_id": tracked_id}


@router.post("/comment")
async def comment(
    account_id: int, data: CommentPostIn, c: Container = Depends(container)
):
    msg, tracked_id, link = await c.chats.comment(
        account_id, data.post_link, data.text, data.join_if_needed
    )
    return {
        "message": presenters.tg_message(msg),
        "tracked_id": tracked_id,
        "link": link,
    }


@router.post("/join")
async def join(account_id: int, data: TargetIn, c: Container = Depends(container)):
    return presenters.join_result(await c.chats.join(account_id, data.target))


@router.post("/leave")
async def leave(account_id: int, data: TargetIn, c: Container = Depends(container)):
    return presenters.join_result(await c.chats.leave(account_id, data.target))


@router.get("/dialogs/{peer_id}/messages/{msg_id}/replies")
async def replies(
    account_id: int, peer_id: int, msg_id: int, c: Container = Depends(container)
):
    return [
        presenters.tg_message(m)
        for m in await c.chats.replies(account_id, peer_id, msg_id)
    ]


@router.get("/comments", response_model=Page)
async def account_comments(
    account_id: int,
    kind: str | None = None,
    q: str | None = None,
    page: int = 1,
    page_size: int = 50,
    c: Container = Depends(container),
):
    res = await c.chats.comments(account_id, kind, q, page, page_size)
    return Page(
        items=[CommentOut.model_validate(x) for x in res.items], total=res.total
    )


@router.post("/comments/scan")
async def scan_account_comments(
    account_id: int, dialog_limit: int = 50, c: Container = Depends(container)
):
    return await c.chats.scan_comments(account_id, dialog_limit)
