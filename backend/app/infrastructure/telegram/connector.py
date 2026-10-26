import asyncio
from collections import defaultdict

from telethon import TelegramClient, errors

from app.application.dto import ClientParams, LoginCode, TgProfile
from app.application.ports.telegram import ConnectionFailed, SessionNotAuthorized
from app.domain.errors import (
    AccountUnavailable,
    DomainError,
    PasswordRequired,
    TelegramError,
)
from app.infrastructure.telegram import converters as conv
from app.infrastructure.telegram.client import (
    DEAD_ERRORS,
    ClientFactory,
    dead_error,
    error_text,
    safe_disconnect,
    translate,
)
from app.infrastructure.telegram.session import TelethonSession

CONNECT_TIMEOUT = 40


class TelethonConnector:
    def __init__(self, factory: ClientFactory):
        self._factory = factory
        self._clients: dict[int, TelegramClient] = {}
        self._locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)

    def is_connected(self, account_id: int) -> bool:
        c = self._clients.get(account_id)
        return bool(c and c.is_connected())

    async def connect(
        self, account_id: int, params: ClientParams
    ) -> tuple[TelethonSession, str | None]:
        async with self._locks[account_id]:
            client = self._clients.get(account_id)
            if client and client.is_connected():
                return TelethonSession(client), None
            await safe_disconnect(client)
            self._clients.pop(account_id, None)

            client = self._factory.build(params)
            try:
                await asyncio.wait_for(client.connect(), CONNECT_TIMEOUT)
                authorized = await client.is_user_authorized()
            except DEAD_ERRORS as e:
                await safe_disconnect(client)
                raise dead_error(e) from e
            except Exception as e:  # noqa: BLE001
                await safe_disconnect(client)
                raise ConnectionFailed(f"{type(e).__name__}: {e}") from e
            if not authorized:
                await safe_disconnect(client)
                raise SessionNotAuthorized()
            self._clients[account_id] = client
            return TelethonSession(client), client.session.save()

    async def drop(self, account_id: int) -> None:
        await safe_disconnect(self._clients.pop(account_id, None))

    async def shutdown(self) -> None:
        await asyncio.gather(
            *(safe_disconnect(c) for c in self._clients.values()),
            return_exceptions=True,
        )
        self._clients.clear()


class TelethonAuth:
    def __init__(self, factory: ClientFactory):
        self._factory = factory

    async def send_code(self, params: ClientParams, phone: str) -> LoginCode:
        client = self._factory.build(params)
        try:
            await asyncio.wait_for(client.connect(), CONNECT_TIMEOUT)
            sent = await client.send_code_request(phone)
            return LoginCode(
                session=client.session.save(),
                phone_code_hash=sent.phone_code_hash,
                delivery=type(sent.type).__name__.replace("SentCodeType", ""),
            )
        except (
            errors.FloodWaitError,
            errors.PhoneNumberInvalidError,
            errors.PhoneNumberBannedError,
            errors.ApiIdInvalidError,
        ) as e:
            raise translate(e) from e
        except DomainError:
            raise
        except Exception as e:  # noqa: BLE001
            raise TelegramError(f"Не удалось отправить код: {error_text(e)}") from e
        finally:
            await safe_disconnect(client)

    async def sign_in(
        self, params: ClientParams, *, phone: str, code: str, phone_code_hash: str
    ) -> tuple[TgProfile, str]:
        client = self._factory.build(params)
        try:
            await client.connect()
            try:
                await client.sign_in(
                    phone=phone, code=code, phone_code_hash=phone_code_hash
                )
            except errors.SessionPasswordNeededError:
                raise PasswordRequired(client.session.save()) from None
            return conv.profile(await client.get_me()), client.session.save()
        except DomainError:
            raise
        except Exception as e:  # noqa: BLE001
            raise translate(e) from e
        finally:
            await safe_disconnect(client)

    async def sign_in_password(
        self, params: ClientParams, password: str
    ) -> tuple[TgProfile, str]:
        client = self._factory.build(params)
        try:
            await client.connect()
            await client.sign_in(password=password)
            return conv.profile(await client.get_me()), client.session.save()
        except DomainError:
            raise
        except Exception as e:  # noqa: BLE001
            raise translate(e) from e
        finally:
            await safe_disconnect(client)

    async def probe(self, params: ClientParams) -> tuple[TgProfile, str]:
        client = self._factory.build(params)
        try:
            await asyncio.wait_for(client.connect(), CONNECT_TIMEOUT)
            if not await client.is_user_authorized():
                raise AccountUnavailable("Сессия не авторизована")
            return conv.profile(await client.get_me()), client.session.save()
        except DomainError:
            raise
        except Exception as e:  # noqa: BLE001
            raise TelegramError(error_text(e)) from e
        finally:
            await safe_disconnect(client)
