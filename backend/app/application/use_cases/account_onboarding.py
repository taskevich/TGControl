import asyncio
import json
import uuid
from dataclasses import replace

from app.application.dto import ClientParams, ImportResult, LoginStep, ParsedSession
from app.application.policies import Policies
from app.application.ports.repositories import UnitOfWork, UnitOfWorkFactory
from app.application.ports.services import Cipher, KeyValueStore, SessionFileParser
from app.application.ports.telegram import TelegramAuth
from app.application.services.proxies import ProxyRegistry
from app.application.services.telegram_access import AccountClients
from app.application.use_cases.accounts import AccountRegistrar
from app.domain.errors import (
    AccountUnavailable,
    DomainError,
    Gone,
    InvalidInput,
    InvalidPassword,
    NotFound,
    PasswordRequired,
)
from app.domain.values import ProxyAddress

IMPORT_CONCURRENCY = 5


async def resolve_proxy(
    uow: UnitOfWork, proxies: ProxyRegistry, proxy_id: int | None, url: str | None
) -> ProxyAddress | None:
    if proxy_id:
        proxy = await uow.proxies.get(proxy_id)
        if not proxy:
            raise NotFound("Прокси не найден")
        if not proxy.is_active:
            raise InvalidInput("Выбранный прокси отключён")
        return proxies.address(proxy)
    url = (url or "").strip()
    return ProxyAddress.parse(url) if url else None


class PhoneLogin:
    def __init__(
        self,
        uow: UnitOfWorkFactory,
        auth: TelegramAuth,
        kv: KeyValueStore,
        cipher: Cipher,
        proxies: ProxyRegistry,
        registrar: AccountRegistrar,
        clients: AccountClients,
        policies: Policies,
    ):
        self._uow = uow
        self._auth = auth
        self._kv = kv
        self._cipher = cipher
        self._proxies = proxies
        self._registrar = registrar
        self._clients = clients
        self._ttl = policies.login_flow_ttl

    async def _load(self, flow_id: str) -> dict:
        raw = await self._kv.get(f"tglogin:{flow_id}")
        if not raw:
            raise Gone("Сессия входа истекла, начните заново")
        return json.loads(raw)

    async def _save(self, flow_id: str, flow: dict) -> None:
        await self._kv.set(f"tglogin:{flow_id}", json.dumps(flow), ex=self._ttl)

    def _params(self, flow: dict) -> ClientParams:
        proxy = (
            ProxyAddress.parse(self._cipher.decrypt(flow["proxy_enc"]))
            if flow.get("proxy_enc")
            else None
        )
        return ClientParams(
            flow["session"],
            api_id=flow.get("api_id"),
            api_hash=flow.get("api_hash"),
            proxy=proxy,
        )

    async def _finish(
        self, flow_id: str, flow: dict, me, session: str, twofa: str | None = None
    ) -> LoginStep:
        proxy_url = None
        if flow.get("proxy_enc") and not flow.get("proxy_id"):
            proxy_url = self._cipher.decrypt(flow["proxy_enc"])
        async with self._uow() as uow:
            acc, _ = await self._registrar.register(
                uow,
                me,
                session,
                source="phone",
                phone=flow["phone"],
                api_id=flow.get("api_id"),
                api_hash=flow.get("api_hash"),
                twofa=twofa,
                proxy_id=flow.get("proxy_id"),
                proxy=proxy_url,
            )
            view = self._clients.view(acc)
        await self._kv.delete(f"tglogin:{flow_id}")
        return LoginStep(
            flow_id=flow_id, step="done", account=view, detail="Аккаунт добавлен"
        )

    async def start(
        self,
        phone: str,
        *,
        api_id: int | None = None,
        api_hash: str | None = None,
        proxy: str | None = None,
        proxy_id: int | None = None,
        password: str | None = None,
    ) -> LoginStep:
        async with self._uow() as uow:
            addr = await resolve_proxy(uow, self._proxies, proxy_id, proxy)
        try:
            sent = await self._auth.send_code(
                ClientParams(api_id=api_id, api_hash=api_hash, proxy=addr), phone
            )
        except AccountUnavailable as e:
            raise InvalidInput(str(e)) from e
        flow = {
            "phone": phone,
            "phone_code_hash": sent.phone_code_hash,
            "session": sent.session,
            "api_id": api_id,
            "api_hash": api_hash,
            "proxy_id": proxy_id,
            "proxy_enc": self._cipher.encrypt(addr.url()) if addr else None,
            "password_enc": self._cipher.encrypt(password) if password else None,
        }
        flow_id = uuid.uuid4().hex
        await self._save(flow_id, flow)
        where = "в Telegram" if sent.delivery == "App" else f"({sent.delivery})"
        return LoginStep(flow_id=flow_id, step="code", detail=f"Код отправлен {where}")

    async def submit_code(self, flow_id: str, code: str) -> LoginStep:
        flow = await self._load(flow_id)
        params = self._params(flow)
        try:
            me, session = await self._auth.sign_in(
                params,
                phone=flow["phone"],
                code=code.strip(),
                phone_code_hash=flow["phone_code_hash"],
            )
        except PasswordRequired as e:
            flow["session"] = e.session
            password = (
                self._cipher.decrypt(flow["password_enc"])
                if flow.get("password_enc")
                else None
            )
            if password:
                try:
                    me, session = await self._auth.sign_in_password(
                        replace(params, session=e.session), password
                    )
                    return await self._finish(
                        flow_id, flow, me, session, twofa=password
                    )
                except InvalidPassword:
                    flow["password_enc"] = None
                    detail = "Указанный пароль 2FA не подошёл - введите правильный"
            else:
                detail = "Требуется пароль 2FA"
            await self._save(flow_id, flow)
            return LoginStep(flow_id=flow_id, step="password", detail=detail)
        return await self._finish(flow_id, flow, me, session)

    async def submit_password(self, flow_id: str, password: str) -> LoginStep:
        flow = await self._load(flow_id)
        try:
            me, session = await self._auth.sign_in_password(
                self._params(flow), password
            )
        except InvalidPassword:
            raise InvalidPassword("Неверный пароль 2FA") from None
        return await self._finish(flow_id, flow, me, session, twofa=password)


class SessionImport:
    def __init__(
        self,
        uow: UnitOfWorkFactory,
        auth: TelegramAuth,
        parser: SessionFileParser,
        proxies: ProxyRegistry,
        registrar: AccountRegistrar,
    ):
        self._uow = uow
        self._auth = auth
        self._parser = parser
        self._proxies = proxies
        self._registrar = registrar

    async def run(
        self,
        files: list[tuple[str, bytes]],
        string_sessions: str = "",
        proxy: str = "",
        proxy_id: int | None = None,
        twofa: str = "",
    ) -> list[ImportResult]:
        async with self._uow() as uow:
            common = await resolve_proxy(uow, self._proxies, proxy_id, proxy)
        parsed = self._parser.parse(files, string_sessions)
        results = [
            ImportResult(name=e["name"], status="error", detail=e["error"])
            for e in parsed.errors
        ]
        if not parsed.accounts and not results:
            raise InvalidInput(
                "Не найдено ни одной сессии (.session, .json, .zip или строковые сессии)"
            )

        sem = asyncio.Semaphore(IMPORT_CONCURRENCY)

        async def probe(ps: ParsedSession):
            if ps.api_id and not ps.api_hash:
                ps.api_id = None
            async with sem:
                try:
                    params = ClientParams(
                        ps.session,
                        api_id=ps.api_id,
                        api_hash=ps.api_hash,
                        proxy=ProxyAddress.parse(ps.proxy) if ps.proxy else common,
                        device_model=ps.device_model,
                        system_version=ps.system_version,
                        app_version=ps.app_version,
                        lang_code=ps.lang_code,
                        system_lang_code=ps.system_lang_code,
                    )
                    me, session = await self._auth.probe(params)
                except DomainError as e:
                    return ps, None, str(e), None
                return ps, me, None, session

        async with self._uow() as uow:
            for ps, me, err, session in await asyncio.gather(
                *(probe(p) for p in parsed.accounts)
            ):
                if err:
                    results.append(
                        ImportResult(name=ps.name, status="error", detail=err)
                    )
                    continue
                acc, created = await self._registrar.register(
                    uow,
                    me,
                    session,
                    source=ps.source,
                    phone=ps.phone,
                    api_id=ps.api_id,
                    api_hash=ps.api_hash,
                    device_model=ps.device_model,
                    system_version=ps.system_version,
                    app_version=ps.app_version,
                    lang_code=ps.lang_code,
                    system_lang_code=ps.system_lang_code,
                    proxy=ps.proxy
                    or (None if proxy_id else (common.url() if common else None)),
                    proxy_id=None if ps.proxy else proxy_id,
                    twofa=ps.twofa or twofa.strip() or None,
                )
                title = f"@{me.username}" if me.username else (acc.phone or str(me.id))
                results.append(
                    ImportResult(
                        name=ps.name,
                        status="created" if created else "updated",
                        detail=title,
                        account_id=acc.id,
                    )
                )
        return results
