from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.application.use_cases.auth import CurrentUser
from app.container import Container

bearer = HTTPBearer(auto_error=False)


def container(request: Request) -> Container:
    return request.app.state.container


async def current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    c: Container = Depends(container),
) -> CurrentUser:
    return await c.auth.authenticate(creds.credentials if creds else None)
