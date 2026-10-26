from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from app.application.dto import AccountView, ClientParams
from app.application.ports.repositories import UnitOfWork
from app.application.ports.services import Cipher
from app.application.ports.telegram import (
    ConnectionFailed,
    SessionNotAuthorized,
    TelegramConnector,
    TelegramSession,
)
from app.application.services.proxies import ProxyRegistry
from app.domain.entities import Account, AccountStatus
from app.domain.errors import AccountDead, AccountUnavailable, NotFound

NOT_AUTHORIZED = "Сессия не авторизована (вышли из аккаунта или сессия отозвана)"


class AccountClients:
    def __init__(
        self, connector: TelegramConnector, cipher: Cipher, proxies: ProxyRegistry
    ):
        self._connector = connector
        self._cipher = cipher
        self._proxies = proxies

    @staticmethod
    async def account(uow: UnitOfWork, account_id: int) -> Account:
        account = await uow.accounts.get(account_id)
        if not account:
            raise NotFound("Аккаунт не найден")
        return account

    def view(self, account: Account) -> AccountView:
        return AccountView(
            account=account,
            connected=self._connector.is_connected(account.id),
            twofa=(
                self._cipher.decrypt(account.twofa_enc) if account.twofa_enc else None
            ),
        )

    def params(self, account: Account) -> ClientParams:
        proxy = None
        if account.proxy is not None:
            account.proxy.ensure_usable()
            proxy = self._proxies.address(account.proxy)
        return ClientParams(
            session=self._cipher.decrypt(account.session_enc),
            api_id=account.api_id,
            api_hash=account.api_hash,
            proxy=proxy,
            device_model=account.device_model,
            system_version=account.system_version,
            app_version=account.app_version,
            lang_code=account.lang_code,
            system_lang_code=account.system_lang_code,
        )

    async def session(self, uow: UnitOfWork, account: Account) -> TelegramSession:
        account.ensure_enabled()
        params = self.params(account)
        try:
            session, session_string = await self._connector.connect(account.id, params)
        except AccountDead as e:
            await self._mark_dead(uow, account, e)
            raise AccountUnavailable(f"Аккаунт недоступен: {e.name}") from e
        except SessionNotAuthorized as e:
            account.mark_unauthorized(NOT_AUTHORIZED)
            await uow.commit()
            raise AccountUnavailable(NOT_AUTHORIZED) from e
        except ConnectionFailed as e:
            account.mark_error(f"Ошибка подключения: {e}")
            await uow.commit()
            raise AccountUnavailable(account.status_detail) from e
        if session_string is None:
            return session
        if session_string and session_string != params.session:
            account.session_enc = self._cipher.encrypt(session_string)
        if account.status != AccountStatus.ACTIVE:
            account.activate()
        await uow.commit()
        return session

    @asynccontextmanager
    async def guard(self, uow: UnitOfWork, account: Account) -> AsyncIterator[None]:
        try:
            yield
        except AccountDead as e:
            await self._mark_dead(uow, account, e)
            raise

    async def _mark_dead(
        self, uow: UnitOfWork, account: Account, e: AccountDead
    ) -> None:
        account.mark_dead(banned=e.banned, detail=str(e))
        await uow.commit()
        await self._connector.drop(account.id)

    def is_connected(self, account_id: int) -> bool:
        return self._connector.is_connected(account_id)

    async def drop(self, account_id: int) -> None:
        await self._connector.drop(account_id)

    async def drop_many(self, account_ids: list[int]) -> None:
        for aid in account_ids:
            await self._connector.drop(aid)

    async def shutdown(self) -> None:
        await self._connector.shutdown()
