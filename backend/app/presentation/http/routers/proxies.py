from fastapi import APIRouter, Depends

from app.container import Container
from app.presentation.http import presenters
from app.presentation.http.deps import container, current_user
from app.presentation.http.schemas import (
    ProxyAssignIn,
    ProxyBulkIn,
    ProxyCreate,
    ProxyOut,
    ProxyUpdate,
)

router = APIRouter(
    prefix="/api/proxies", tags=["proxies"], dependencies=[Depends(current_user)]
)


@router.get("", response_model=list[ProxyOut])
async def list_proxies(c: Container = Depends(container)):
    return [presenters.proxy(v) for v in await c.proxies.all()]


@router.post("", response_model=ProxyOut)
async def create_proxy(data: ProxyCreate, c: Container = Depends(container)):
    return presenters.proxy(await c.proxies.create(data.url, data.name))


@router.post("/bulk")
async def create_bulk(data: ProxyBulkIn, c: Container = Depends(container)):
    return await c.proxies.create_many(data.text)


@router.patch("/{proxy_id}", response_model=ProxyOut)
async def update_proxy(
    proxy_id: int, data: ProxyUpdate, c: Container = Depends(container)
):
    return presenters.proxy(
        await c.proxies.update(proxy_id, data.model_dump(exclude_unset=True))
    )


@router.delete("/{proxy_id}")
async def delete_proxy(
    proxy_id: int, force: bool = False, c: Container = Depends(container)
):
    return {"ok": True, "unbound": await c.proxies.delete(proxy_id, force)}


@router.post("/{proxy_id}/check", response_model=ProxyOut)
async def check(proxy_id: int, c: Container = Depends(container)):
    return presenters.proxy(await c.proxies.check(proxy_id))


@router.post("/check-all")
async def check_all(c: Container = Depends(container)):
    return await c.proxies.check_all()


@router.post("/assign")
async def auto_assign(data: ProxyAssignIn, c: Container = Depends(container)):
    return await c.proxies.auto_assign(
        data.account_ids, data.max_per_proxy, data.only_working
    )
