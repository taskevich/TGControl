from fastapi import APIRouter, Depends

from app.container import Container
from app.presentation.http.deps import container, current_user
from app.presentation.http.schemas import (
    CommentOut,
    Page,
    RefreshIn,
    SnapshotOut,
    TrackedDetailOut,
    TrackedOut,
    TrackLinkIn,
)

router = APIRouter(
    prefix="/api/stats", tags=["stats"], dependencies=[Depends(current_user)]
)


@router.get("/summary")
async def summary(
    days: int = 14, account_id: int | None = None, c: Container = Depends(container)
):
    return await c.stats.summary(days, account_id)


@router.get("/messages", response_model=Page)
async def list_messages(
    account_id: int | None = None,
    source: str | None = None,
    comments_only: bool = False,
    q: str | None = None,
    sort: str = "sent_at",
    order: str = "desc",
    page: int = 1,
    page_size: int = 50,
    c: Container = Depends(container),
):
    res = await c.stats.tracked(
        account_id=account_id,
        source=source,
        comments_only=comments_only,
        q=q,
        sort=sort,
        order=order,
        page=page,
        page_size=page_size,
    )
    return Page(
        items=[TrackedOut.model_validate(r) for r in res.items], total=res.total
    )


@router.get("/messages/{tracked_id}", response_model=TrackedDetailOut)
async def message_detail(tracked_id: int, c: Container = Depends(container)):
    d = await c.stats.details(tracked_id)
    return TrackedDetailOut(
        **TrackedOut.model_validate(d.message).model_dump(),
        snapshots=[SnapshotOut.model_validate(s) for s in d.snapshots],
        comments=[CommentOut.model_validate(x) for x in d.comments],
    )


@router.post("/messages/refresh")
async def refresh(data: RefreshIn, c: Container = Depends(container)):
    return await c.stats.refresh(data.ids, data.account_id)


@router.post("/messages/track", response_model=TrackedOut)
async def track_by_link(data: TrackLinkIn, c: Container = Depends(container)):
    return await c.stats.track_link(data.account_id, data.link)


@router.delete("/messages/{tracked_id}")
async def untrack(tracked_id: int, c: Container = Depends(container)):
    await c.stats.untrack(tracked_id)
    return {"ok": True}


@router.get("/comments", response_model=Page)
async def all_comments(
    account_id: int | None = None,
    kind: str | None = None,
    q: str | None = None,
    page: int = 1,
    page_size: int = 50,
    c: Container = Depends(container),
):
    res = await c.stats.comments(
        account_id=account_id, kind=kind, q=q, page=page, page_size=page_size
    )
    return Page(
        items=[CommentOut.model_validate(r) for r in res.items], total=res.total
    )


@router.get("/chat-messages")
async def chat_messages_stats(
    account_id: int | None = None,
    days: int = 14,
    top: int = 10,
    c: Container = Depends(container),
):
    return await c.stats.chat_messages(account_id, days, top)
