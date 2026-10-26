from fastapi import APIRouter, Depends

from app.application.use_cases.auth import CurrentUser
from app.container import Container
from app.domain.entities import TaskKind
from app.presentation.http.deps import container, current_user
from app.presentation.http.schemas import (
    BulkJoinIn,
    BulkSendIn,
    Page,
    TaskDetailOut,
    TaskOut,
)

router = APIRouter(prefix="/api", tags=["bulk"], dependencies=[Depends(current_user)])


@router.post("/bulk/send", response_model=TaskOut)
async def bulk_send(
    data: BulkSendIn,
    user: CurrentUser = Depends(current_user),
    c: Container = Depends(container),
):
    kind = TaskKind.COMMENT if data.mode == "comment" else TaskKind.SEND
    return await c.bulk.create(kind, data.model_dump(), user.user.username)


@router.post("/bulk/join", response_model=TaskOut)
async def bulk_join(
    data: BulkJoinIn,
    user: CurrentUser = Depends(current_user),
    c: Container = Depends(container),
):
    return await c.bulk.create(TaskKind.JOIN, data.model_dump(), user.user.username)


@router.post("/bulk/leave", response_model=TaskOut)
async def bulk_leave(
    data: BulkJoinIn,
    user: CurrentUser = Depends(current_user),
    c: Container = Depends(container),
):
    return await c.bulk.create(TaskKind.LEAVE, data.model_dump(), user.user.username)


@router.get("/tasks", response_model=Page)
async def list_tasks(
    page: int = 1,
    page_size: int = 30,
    kind: str | None = None,
    c: Container = Depends(container),
):
    res = await c.bulk.all(page, page_size, kind)
    return Page(items=[TaskOut.model_validate(t) for t in res.items], total=res.total)


@router.get("/tasks/{task_id}", response_model=TaskDetailOut)
async def get_task(task_id: int, c: Container = Depends(container)):
    return await c.bulk.get(task_id)


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: int, c: Container = Depends(container)):
    await c.bulk.cancel(task_id)
    return {"ok": True}


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: int, c: Container = Depends(container)):
    await c.bulk.delete(task_id)
    return {"ok": True}
