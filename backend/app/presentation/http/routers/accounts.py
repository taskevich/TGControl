from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.container import Container
from app.presentation.http import presenters
from app.presentation.http.deps import container, current_user
from app.presentation.http.schemas import (
    AccountOut,
    AccountUpdate,
    ImportResultItem,
    LoginCodeIn,
    LoginPasswordIn,
    LoginStartIn,
    LoginStepOut,
    SetPasswordAllIn,
    SetPasswordIn,
    SetPasswordResult,
)

router = APIRouter(
    prefix="/api/accounts", tags=["accounts"], dependencies=[Depends(current_user)]
)


def _step(step) -> LoginStepOut:
    return LoginStepOut(
        flow_id=step.flow_id,
        step=step.step,
        detail=step.detail,
        account=presenters.account(step.account) if step.account else None,
    )


@router.get("", response_model=list[AccountOut])
async def list_accounts(status: str | None = None, c: Container = Depends(container)):
    return [presenters.account(v) for v in await c.accounts.all(status)]


@router.get("/{account_id}", response_model=AccountOut)
async def get_account(account_id: int, c: Container = Depends(container)):
    return presenters.account(await c.accounts.get(account_id))


@router.patch("/{account_id}", response_model=AccountOut)
async def update_account(
    account_id: int, data: AccountUpdate, c: Container = Depends(container)
):
    return presenters.account(
        await c.accounts.update(account_id, data.model_dump(exclude_unset=True))
    )


@router.delete("/{account_id}")
async def delete_account(
    account_id: int, logout: bool = False, c: Container = Depends(container)
):
    await c.accounts.delete(account_id, logout)
    return {"ok": True}


@router.post("/{account_id}/check", response_model=AccountOut)
async def check_account(account_id: int, c: Container = Depends(container)):
    return presenters.account(await c.accounts.check(account_id))


@router.post("/check-all", response_model=list[AccountOut])
async def check_all(c: Container = Depends(container)):
    return [presenters.account(v) for v in await c.accounts.check_all()]


@router.post("/login/start", response_model=LoginStepOut)
async def login_start(data: LoginStartIn, c: Container = Depends(container)):
    return _step(
        await c.login.start(
            data.phone,
            api_id=data.api_id,
            api_hash=data.api_hash,
            proxy=data.proxy,
            proxy_id=data.proxy_id,
            password=data.password,
        )
    )


@router.post("/login/code", response_model=LoginStepOut)
async def login_code(data: LoginCodeIn, c: Container = Depends(container)):
    return _step(await c.login.submit_code(data.flow_id, data.code))


@router.post("/login/password", response_model=LoginStepOut)
async def login_password(data: LoginPasswordIn, c: Container = Depends(container)):
    return _step(await c.login.submit_password(data.flow_id, data.password))


@router.post("/password", response_model=list[SetPasswordResult])
async def set_password_all(data: SetPasswordAllIn, c: Container = Depends(container)):
    results = await c.accounts.set_password_many(
        data.account_ids, data.password, data.hint
    )
    return [SetPasswordResult(**vars(r)) for r in results]


@router.post("/{account_id}/password", response_model=AccountOut)
async def set_password(
    account_id: int, data: SetPasswordIn, c: Container = Depends(container)
):
    return presenters.account(
        await c.accounts.set_password(account_id, data.password, data.hint)
    )


@router.post("/import", response_model=list[ImportResultItem])
async def import_accounts(
    files: list[UploadFile] = File(default=[]),
    string_sessions: str = Form(default=""),
    proxy: str = Form(default=""),
    proxy_id: int | None = Form(default=None),
    twofa: str = Form(default=""),
    c: Container = Depends(container),
):
    payload = [(f.filename or "file", await f.read()) for f in files]
    results = await c.importer.run(payload, string_sessions, proxy, proxy_id, twofa)
    return [ImportResultItem(**vars(r)) for r in results]
