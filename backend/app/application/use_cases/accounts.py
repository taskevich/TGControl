import asyncio

from app.application.dto import AccountView, PasswordResult, TgProfile
from app.application.ports.repositories import UnitOfWork, UnitOfWorkFactory
from app.application.ports.services import Cipher
from app.application.services.proxies import ProxyRegistry
from app.application.services.telegram_access import AccountClients
from app.domain.entities import Account, AccountStatus
from app.domain.errors import (
    AccountUnavailable,
    DomainError,
    InvalidPassword,
    NotFound,
)
from app.domain.values import check_new_account_password

CHECK_CONCURRENCY = 5


class AccountRegistrar:

    def __init__(self, cipher: Cipher, proxies: ProxyRegistry, clients: AccountClients):
        self._cipher = cipher
        self._proxies = proxies
        self._clients = clients

    async def register(
        self,
        uow: UnitOfWork,
        me: TgProfile,
        session: str,
        *,
        source: str | None,
        phone: str | None = None,
        proxy_id: int | None = None,
        proxy: str | None = None,
        twofa: str | None = None,
        **client_fields
    ) -> tuple[Account, bool]:
        acc = await uow.accounts.by_tg_id(me.id)
        created = acc is None
        if created:
            acc = Account(tg_id=me.id, source=source, session_enc="")
            uow.accounts.add(acc)
        acc.session_enc = self._cipher.encrypt(session)
        acc.phone = ("+" + me.phone) if me.phone else phone or acc.phone
        acc.username, acc.first_name, acc.last_name = (
            me.username,
            me.first_name,
            me.last_name,
        )
        for key in (
            "api_id",
            "api_hash",
            "device_model",
            "system_version",
            "app_version",
            "lang_code",
            "system_lang_code",
        ):
            if client_fields.get(key):
                setattr(acc, key, client_fields[key])
        if proxy_id:
            acc.proxy_id = proxy_id
        elif proxy:
            p, _ = await self._proxies.get_or_create(uow, proxy)
            acc.proxy_id = p.id
        if twofa:
            acc.twofa_enc = self._cipher.encrypt(twofa)
        acc.activate()
        acc.mark_checked()
        await uow.commit()
        await uow.accounts.load_proxy(acc)
        await self._clients.drop(acc.id)
        return acc, created


class Accounts:
    def __init__(
        self,
        uow: UnitOfWorkFactory,
        clients: AccountClients,
        cipher: Cipher,
        proxies: ProxyRegistry,
    ):
        self._uow = uow
        self._clients = clients
        self._cipher = cipher
        self._proxies = proxies

    async def all(self, status: str | None = None) -> list[AccountView]:
        async with self._uow() as uow:
            return [self._clients.view(a) for a in await uow.accounts.all(status)]

    async def get(self, account_id: int) -> AccountView:
        async with self._uow() as uow:
            return self._clients.view(await self._clients.account(uow, account_id))

    async def update(self, account_id: int, changes: dict) -> AccountView:
        async with self._uow() as uow:
            acc = await self._clients.account(uow, account_id)
            reconnect = False
            if "proxy_id" in changes or "proxy" in changes:
                url = (changes.get("proxy") or "").strip()
                if url:
                    proxy, _ = await self._proxies.get_or_create(uow, url)
                    acc.proxy_id = proxy.id
                else:
                    pid = changes.get("proxy_id")
                    if pid and not await uow.proxies.get(pid):
                        raise NotFound("Прокси не найден")
                    acc.proxy_id = pid or None
                reconnect = True
            if "api_id" in changes or "api_hash" in changes:
                acc.api_id = changes.get("api_id", acc.api_id) or None
                acc.api_hash = changes.get("api_hash", acc.api_hash) or None
                reconnect = True
            if "twofa" in changes:
                acc.twofa_enc = (
                    self._cipher.encrypt(changes["twofa"]) if changes["twofa"] else None
                )
            if "notes" in changes:
                acc.notes = changes["notes"]
            if changes.get("is_enabled") is not None:
                acc.is_enabled = changes["is_enabled"]
                reconnect = reconnect or not acc.is_enabled
            await uow.commit()
            await uow.accounts.load_proxy(acc)
            if reconnect:
                await self._clients.drop(acc.id)
            return self._clients.view(acc)

    async def delete(self, account_id: int, logout: bool = False) -> None:
        async with self._uow() as uow:
            acc = await self._clients.account(uow, account_id)
            if logout:
                try:
                    tg = await self._clients.session(uow, acc)
                    await tg.log_out()
                except DomainError:
                    pass
            await self._clients.drop(acc.id)
            await uow.accounts.delete(acc)
            await uow.commit()

    async def _check(self, uow: UnitOfWork, acc: Account) -> None:
        await self._clients.drop(acc.id)
        acc.mark_checked()
        try:
            tg = await self._clients.session(uow, acc)
            async with self._clients.guard(uow, acc):
                me = await tg.get_me()
            acc.update_profile(
                tg_id=me.id,
                username=me.username,
                first_name=me.first_name,
                last_name=me.last_name,
                phone=me.phone,
            )
        except AccountUnavailable:
            pass
        except DomainError as e:
            if acc.status == AccountStatus.ACTIVE:
                acc.mark_error(str(e))
        await uow.commit()

    async def check(self, account_id: int) -> AccountView:
        async with self._uow() as uow:
            acc = await self._clients.account(uow, account_id)
            await self._check(uow, acc)
            return self._clients.view(acc)

    async def check_all(self) -> list[AccountView]:
        async with self._uow() as uow:
            ids = await uow.accounts.enabled_ids()
        sem = asyncio.Semaphore(CHECK_CONCURRENCY)

        async def one(aid: int) -> None:
            async with sem, self._uow() as uow:
                acc = await uow.accounts.get(aid)
                if acc:
                    await self._check(uow, acc)

        await asyncio.gather(*(one(i) for i in ids), return_exceptions=True)
        return await self.all()

    async def _set_password(
        self, uow: UnitOfWork, acc: Account, password: str, hint: str
    ) -> None:
        check_new_account_password(password)
        current = (
            self._cipher.decrypt(acc.twofa_enc) if acc.twofa_enc else None
        )  # ignored if 2FA is off
        tg = await self._clients.session(uow, acc)
        try:
            async with self._clients.guard(uow, acc):
                await tg.edit_2fa(current, password, hint)
        except InvalidPassword:
            if current:
                raise DomainError(
                    "Сохранённый текущий пароль 2FA не подходит - укажите верный в настройках аккаунта"
                ) from None
            raise DomainError(
                "У аккаунта уже есть пароль 2FA, но он неизвестен панели - укажите его в настройках аккаунта"
            ) from None
        acc.twofa_enc = self._cipher.encrypt(password)
        await uow.commit()

    async def set_password(
        self, account_id: int, password: str, hint: str = ""
    ) -> AccountView:
        async with self._uow() as uow:
            acc = await self._clients.account(uow, account_id)
            await self._set_password(uow, acc, password, hint)
            return self._clients.view(acc)

    async def set_password_many(
        self, account_ids: list[int], password: str, hint: str = ""
    ) -> list[PasswordResult]:
        async with self._uow() as uow:
            ids = await uow.accounts.usable_ids(account_ids or None)
        if not ids:
            raise DomainError("Нет подходящих аккаунтов (включённых и активных)")
        sem = asyncio.Semaphore(CHECK_CONCURRENCY)

        async def one(aid: int) -> PasswordResult:
            async with sem, self._uow() as uow:
                acc = await uow.accounts.get(aid)
                try:
                    await self._set_password(uow, acc, password, hint)
                except DomainError as e:
                    return PasswordResult(aid, acc.label, "error", str(e))
                return PasswordResult(aid, acc.label, "ok", "Пароль установлен")

        return list(await asyncio.gather(*(one(i) for i in ids)))
