from urllib.parse import quote

from fastapi import APIRouter, Depends, Header
from fastapi.responses import StreamingResponse

from app.container import Container
from app.presentation.http.deps import container, current_user

router = APIRouter(
    prefix="/api/media", tags=["files"], dependencies=[Depends(current_user)]
)
public_router = APIRouter(prefix="/api/files", tags=["files"])


@router.get("/stats")
async def stats(
    account_id: int | None = None,
    days: int | None = None,
    c: Container = Depends(container),
):
    return await c.media.stats(account_id, days)


@public_router.get("/{message_id}")
async def file(
    message_id: int,
    exp: int,
    sig: str,
    download: bool = False,
    range: str | None = Header(default=None),
    c: Container = Depends(container),
):  # noqa: A002
    f = await c.media.open(message_id, exp, sig, range)
    disposition = "attachment" if download else "inline"
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(f.content.length),
        "Content-Disposition": f"{disposition}; filename*=UTF-8''{quote(f.file_name)}",
        "Cache-Control": "private, max-age=3600",
    }
    if f.content.content_range:
        headers["Content-Range"] = f.content.content_range
    return StreamingResponse(
        f.content.chunks,
        status_code=206 if f.content.content_range else 200,
        media_type=f.content.content_type
        or f.message.media_mime
        or "application/octet-stream",
        headers=headers,
    )
