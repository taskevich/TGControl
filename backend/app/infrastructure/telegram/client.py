import asyncio
import functools
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar

from telethon import TelegramClient, errors
from telethon.sessions import StringSession

from app.application.dto import ClientParams
from app.domain.errors import (
    AccountDead,
    AccountUnavailable,
    DomainError,
    FloodWait,
    InvalidCode,
    InvalidInput,
    InvalidPassword,
    PasswordRequired,
    TelegramError,
)
from app.domain.values import ProxyAddress


def rpc_errors(*names: str) -> tuple:
    return tuple(e for e in (getattr(errors, n, None) for n in names) if e)


BANNED_ERRORS = rpc_errors(
    "UserDeactivatedError",
    "UserDeactivatedBanError",
    "PhoneNumberBannedError",
)
UNAUTHORIZED_ERRORS = rpc_errors(
    "AuthKeyUnregisteredError",
    "SessionRevokedError",
    "SessionExpiredError",
    "AuthKeyDuplicatedError",
    "AuthKeyInvalidError",
)
DEAD_ERRORS = BANNED_ERRORS + UNAUTHORIZED_ERRORS
CODE_ERRORS = rpc_errors(
    "PhoneCodeInvalidError",
    "PhoneCodeExpiredError",
    "PhoneCodeEmptyError",
)


def error_text(e: BaseException) -> str:
    if isinstance(e, errors.FloodWaitError):
        return f"FloodWait: подождать {e.seconds} с"
    if isinstance(e, errors.RPCError):
        return f"{type(e).__name__}: {e.message}"
    return f"{type(e).__name__}: {e}"


def dead_error(e: BaseException) -> AccountDead:
    return AccountDead(
        f"{type(e).__name__}: {e}",
        banned=isinstance(e, BANNED_ERRORS),
        name=type(e).__name__,
    )


def translate(e: Exception) -> DomainError:
    if isinstance(e, DomainError):
        return e
    if isinstance(e, errors.FloodWaitError):
        return FloodWait(e.seconds)
    if isinstance(e, DEAD_ERRORS):
        return dead_error(e)
    if isinstance(e, errors.PasswordHashInvalidError):
        return InvalidPassword(error_text(e))
    if isinstance(e, errors.SessionPasswordNeededError):
        return PasswordRequired("")
    if isinstance(e, CODE_ERRORS):
        return InvalidCode(f"Неверный или истёкший код ({type(e).__name__})")
    if isinstance(e, ValueError):
        return InvalidInput(str(e))
    return TelegramError(error_text(e))


T = TypeVar("T")


def translated(fn: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        try:
            return await fn(*args, **kwargs)
        except DomainError:
            raise
        except Exception as e:  # noqa: BLE001
            raise translate(e) from e

    return wrapper


def telethon_proxy(proxy: ProxyAddress | None) -> dict | None:
    if proxy is None:
        return None
    return {
        "proxy_type": proxy.scheme,
        "addr": proxy.host,
        "port": proxy.port,
        "username": proxy.username,
        "password": proxy.password,
        "rdns": True,
    }


@dataclass(frozen=True)
class ClientDefaults:
    api_id: int = 0
    api_hash: str = ""
    device_model: str = "PC 64bit"
    system_version: str = "Windows 10"
    app_version: str = "5.6.3 x64"
    lang_code: str = "ru"
    system_lang_code: str = "ru-RU"


class ClientFactory:
    def __init__(self, defaults: ClientDefaults):
        self._d = defaults

    def build(self, p: ClientParams) -> TelegramClient:
        api_id = p.api_id or self._d.api_id
        api_hash = p.api_hash or self._d.api_hash
        if not api_id or not api_hash:
            raise AccountUnavailable(
                "Не заданы TG_API_ID / TG_API_HASH (в .env или в настройках аккаунта)"
            )
        return TelegramClient(
            StringSession(p.session or None),
            api_id,
            api_hash,
            proxy=telethon_proxy(p.proxy),
            device_model=p.device_model or self._d.device_model,
            system_version=p.system_version or self._d.system_version,
            app_version=p.app_version or self._d.app_version,
            lang_code=p.lang_code or self._d.lang_code,
            system_lang_code=p.system_lang_code or self._d.system_lang_code,
            connection_retries=2,
            request_retries=2,
            timeout=20,
            flood_sleep_threshold=10,
            receive_updates=False,
        )


async def safe_disconnect(client: TelegramClient | None) -> None:
    if client is None:
        return
    try:
        await asyncio.wait_for(client.disconnect(), 10)
    except Exception:  # noqa: BLE001
        pass
