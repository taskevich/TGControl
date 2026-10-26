from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.domain.errors import (
    AuthenticationFailed,
    Conflict,
    DomainError,
    Gone,
    NotFound,
    OperationSkipped,
    TooManyRequests,
)

STATUS_CODES: list[tuple[type[DomainError], int]] = [
    (TooManyRequests, 429),
    (AuthenticationFailed, 401),
    (OperationSkipped, 403),
    (NotFound, 404),
    (Conflict, 409),
    (Gone, 410),
]


def status_for(error: DomainError) -> int:
    return next((code for cls, code in STATUS_CODES if isinstance(error, cls)), 400)


async def _domain_error(_: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse({"detail": str(exc)}, status_code=status_for(exc))


def install(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, _domain_error)
