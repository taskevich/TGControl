from fastapi import APIRouter, Depends, Request

from app.application.use_cases.auth import CurrentUser
from app.container import Container
from app.presentation.http.deps import container, current_user
from app.presentation.http.schemas import (
    ChangePasswordIn,
    LoginIn,
    PanelUserCreate,
    PanelUserOut,
    TokenOut,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])
users_router = APIRouter(
    prefix="/api/users", tags=["users"], dependencies=[Depends(current_user)]
)


@router.post("/login", response_model=TokenOut)
async def login(data: LoginIn, request: Request, c: Container = Depends(container)):
    ip = request.headers.get("x-real-ip") or (
        request.client.host if request.client else "unknown"
    )
    token, expires = await c.auth.login(data.username, data.password, ip)
    return TokenOut(access_token=token, expires_in=expires)


@router.post("/logout")
async def logout(
    user: CurrentUser = Depends(current_user), c: Container = Depends(container)
):
    await c.auth.logout(user)
    return {"ok": True}


@router.get("/me", response_model=PanelUserOut)
async def me(user: CurrentUser = Depends(current_user)):
    return user.user


@router.post("/change-password")
async def change_password(
    data: ChangePasswordIn,
    user: CurrentUser = Depends(current_user),
    c: Container = Depends(container),
):
    await c.auth.change_password(user.user.id, data.old_password, data.new_password)
    return {"ok": True}


@users_router.get("", response_model=list[PanelUserOut])
async def list_users(c: Container = Depends(container)):
    return await c.users.all()


@users_router.post("", response_model=PanelUserOut)
async def create_user(data: PanelUserCreate, c: Container = Depends(container)):
    return await c.users.create(data.username, data.password)


@users_router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    user: CurrentUser = Depends(current_user),
    c: Container = Depends(container),
):
    await c.users.delete(user_id, user.user.id)
    return {"ok": True}
