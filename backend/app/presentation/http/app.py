import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.container import Container
from app.presentation.http import errors
from app.presentation.http.routers import accounts, auth, bulk, chats, files, messages, proxies, stats

log = logging.getLogger("tgcontrol")


def _report_stopped(task: asyncio.Task) -> None:
    if task.cancelled():
        return
    if task.exception():
        log.error("Background job %s stopped", task.get_name(), exc_info=task.exception())


def create_app(container: Container) -> FastAPI:
    settings = container.settings

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if settings.SECRET_KEY == "change-me-please":
            log.warning("SECRET_KEY is default – set your own in .env!")
        if await container.users.ensure_admin(settings.ADMIN_USERNAME, settings.ADMIN_PASSWORD):
            log.warning("Created panel admin '%s' – change the password after first login!", settings.ADMIN_USERNAME)
        await container.bulk.mark_interrupted()
        jobs = [
            asyncio.create_task(container.stats.refresh_periodically(), name="stats-refresh"),
            asyncio.create_task(container.messages.sync_periodically(), name="messages-sync"),
            asyncio.create_task(container.media.run_periodically(), name="media-worker"),
        ]
        for t in jobs:
            t.add_done_callback(_report_stopped)
        yield
        for t in jobs:
            t.cancel()
        await container.close()

    app = FastAPI(title="TG Control", version="1.0.0", lifespan=lifespan)
    app.state.container = container
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    errors.install(app)

    app.include_router(auth.router)
    app.include_router(auth.users_router)
    app.include_router(accounts.router)
    app.include_router(proxies.router)
    app.include_router(chats.router)
    app.include_router(bulk.router)
    app.include_router(stats.router)
    app.include_router(messages.router)
    app.include_router(messages.users_router)
    app.include_router(files.router)
    app.include_router(files.public_router)

    @app.get("/api/health")
    async def health():
        return {"ok": True}

    return app
