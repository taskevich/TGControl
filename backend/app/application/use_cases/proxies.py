import asyncio
from dataclasses import dataclass

from app.application.ports.repositories import UnitOfWork, UnitOfWorkFactory
from app.application.ports.services import ProxyChecker
from app.application.services.proxies import ProxyRegistry
from app.application.services.telegram_access import AccountClients
from app.domain.entities import Proxy
from app.domain.errors import Conflict, DomainError, InvalidInput, NotFound
from app.domain.values import ProxyAddress

CHECK_CONCURRENCY = 20


@dataclass
class ProxyView:
    proxy: Proxy
    accounts_count: int
    url_masked: str


class Proxies:
    def __init__(
        self,
        uow: UnitOfWorkFactory,
        registry: ProxyRegistry,
        checker: ProxyChecker,
        clients: AccountClients,
    ):
        self._uow = uow
        self._registry = registry
        self._checker = checker
        self._clients = clients

    def _view(self, proxy: Proxy, counts: dict[int, int]) -> ProxyView:
        return ProxyView(
            proxy, counts.get(proxy.id, 0), self._registry.masked_url(proxy)
        )

    @staticmethod
    async def _get(uow: UnitOfWork, proxy_id: int) -> Proxy:
        proxy = await uow.proxies.get(proxy_id)
        if not proxy:
            raise NotFound("Прокси не найден")
        return proxy

    async def _check(self, uow: UnitOfWork, proxy: Proxy) -> Proxy:
        ok, latency, error = await self._checker.check(self._registry.address(proxy))
        proxy.record_check(ok, latency, error)
        await uow.commit()
        return proxy

    async def _drop_clients(self, uow: UnitOfWork, proxy_id: int) -> None:
        await self._clients.drop_many(await uow.accounts.ids_by_proxy(proxy_id))

    async def all(self) -> list[ProxyView]:
        async with self._uow() as uow:
            counts = await uow.accounts.count_by_proxy()
            return [self._view(p, counts) for p in await uow.proxies.all()]

    async def create(self, url: str, name: str | None = None) -> ProxyView:
        async with self._uow() as uow:
            proxy, created = await self._registry.get_or_create(uow, url, name)
            if not created:
                raise DomainError(f"Такой прокси уже есть (#{proxy.id})")
            await uow.commit()
            return self._view(await self._check(uow, proxy), {})

    async def create_many(self, text: str) -> dict:
        created, existing, errors = 0, 0, []
        async with self._uow() as uow:
            for line in text.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                url, _, name = line.partition(" ")
                try:
                    _, is_new = await self._registry.get_or_create(
                        uow, url, name.strip() or None
                    )
                except InvalidInput as e:
                    errors.append({"line": line, "error": str(e)})
                    continue
                created += is_new
                existing += not is_new
            await uow.commit()
        return {"created": created, "existing": existing, "errors": errors}

    async def update(self, proxy_id: int, changes: dict) -> ProxyView:
        async with self._uow() as uow:
            proxy = await self._get(uow, proxy_id)
            if "name" in changes:
                proxy.name = changes["name"] or None
            if changes.get("url"):
                self._registry.set_address(proxy, ProxyAddress.parse(changes["url"]))
            if changes.get("is_active") is not None:
                proxy.is_active = changes["is_active"]
            await uow.commit()
            await self._drop_clients(uow, proxy.id)
            return self._view(proxy, await uow.accounts.count_by_proxy())

    async def delete(self, proxy_id: int, force: bool = False) -> int:
        async with self._uow() as uow:
            proxy = await self._get(uow, proxy_id)
            bound = (await uow.accounts.count_by_proxy()).get(proxy.id, 0)
            if bound and not force:
                raise Conflict(
                    f"Прокси привязан к {bound} аккаунт(ам). Отвяжите их или удалите с force - "
                    "они будут работать без прокси"
                )
            await self._drop_clients(uow, proxy.id)
            await uow.proxies.delete(proxy)
            await uow.commit()
            return bound

    async def check(self, proxy_id: int) -> ProxyView:
        async with self._uow() as uow:
            proxy = await self._check(uow, await self._get(uow, proxy_id))
            return self._view(proxy, await uow.accounts.count_by_proxy())

    async def check_all(self) -> dict:
        async with self._uow() as uow:
            ids = await uow.proxies.ids()
        sem = asyncio.Semaphore(CHECK_CONCURRENCY)

        async def one(pid: int) -> str:
            async with sem, self._uow() as uow:
                proxy = await uow.proxies.get(pid)
                return (await self._check(uow, proxy)).status if proxy else "missing"

        statuses = await asyncio.gather(*(one(i) for i in ids))
        return {
            "checked": len(ids),
            "ok": statuses.count("ok"),
            "error": statuses.count("error"),
        }

    async def auto_assign(
        self, account_ids: list[int], max_per_proxy: int, only_working: bool
    ) -> dict:
        async with self._uow() as uow:
            accounts = await uow.accounts.without_proxy(account_ids)
            proxies = await uow.proxies.active(only_working)
            load = await uow.accounts.count_by_proxy()
            assigned = 0
            for acc in accounts:
                free = [p for p in proxies if load.get(p.id, 0) < max_per_proxy]
                if not free:
                    break
                p = min(free, key=lambda x: (load.get(x.id, 0), x.latency_ms or 10**6))
                acc.proxy_id = p.id
                load[p.id] = load.get(p.id, 0) + 1
                assigned += 1
                await self._clients.drop(acc.id)
            await uow.commit()
        return {"assigned": assigned, "left_without_proxy": len(accounts) - assigned}
