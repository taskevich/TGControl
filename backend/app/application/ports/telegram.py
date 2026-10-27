from typing import Protocol

from app.application.dto import (
    ChatInfo,
    ClientParams,
    Dialog,
    DownloadedMedia,
    JoinResult,
    LocatedMessage,
    LoginCode,
    SentMessage,
    TgMessage,
    TgProfile,
)
from app.domain.values import Target


class SessionNotAuthorized(Exception):
    pass


class ConnectionFailed(Exception):
    pass


class TelegramSession(Protocol):
    async def get_me(self) -> TgProfile: ...
    async def log_out(self) -> None: ...
    async def reset_other_sessions(self) -> int: ...
    async def edit_2fa(
        self, current_password: str | None, new_password: str, hint: str = ""
    ) -> None: ...

    async def dialogs(self, limit: int) -> list[Dialog]: ...
    async def history(
        self, peer_id: int, *, offset_id: int, limit: int
    ) -> tuple[ChatInfo, list[TgMessage]]: ...
    async def new_messages(
        self, peer_id: int, *, after_id: int, limit: int
    ) -> tuple[ChatInfo, list[TgMessage]]: ...
    async def replies(self, peer_id: int, msg_id: int) -> list[TgMessage]: ...
    async def unread_dialogs(self) -> list[Dialog]: ...
    async def read_dialog(self, dialog: Dialog) -> int: ...
    async def download_media(
        self, chat_id: int, msg_id: int, dest_dir: str, max_size: int
    ) -> DownloadedMedia: ...

    async def send(
        self,
        target: Target,
        text: str,
        *,
        reply_to: int | None = None,
        join_if_needed: bool = False,
        link_preview: bool = True
    ) -> SentMessage: ...
    async def comment(
        self,
        post: Target,
        text: str,
        *,
        join_if_needed: bool = False,
        link_preview: bool = True
    ) -> SentMessage: ...

    async def join(self, target: Target) -> JoinResult: ...
    async def leave(self, target: Target) -> JoinResult: ...
    async def locate(self, link: str) -> LocatedMessage: ...

    async def fetch_by_ids(
        self, chat_id: int, access_hash: int | None, ids: list[int]
    ) -> list[TgMessage | None]: ...

    async def replies_to(
        self, chat_id: int, access_hash: int | None, message: TgMessage
    ) -> list[TgMessage]: ...
    async def mentions(self, chat_id: int, limit: int) -> list[TgMessage]: ...


class TelegramConnector(Protocol):
    async def connect(
        self, account_id: int, params: ClientParams
    ) -> tuple[TelegramSession, str | None]: ...

    def is_connected(self, account_id: int) -> bool: ...
    async def drop(self, account_id: int) -> None: ...
    async def shutdown(self) -> None: ...


class TelegramAuth(Protocol):
    async def send_code(self, params: ClientParams, phone: str) -> LoginCode: ...
    async def sign_in(
        self, params: ClientParams, *, phone: str, code: str, phone_code_hash: str
    ) -> tuple[TgProfile, str]: ...

    async def sign_in_password(
        self, params: ClientParams, password: str
    ) -> tuple[TgProfile, str]: ...
    async def probe(self, params: ClientParams) -> tuple[TgProfile, str]: ...
