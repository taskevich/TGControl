from app.application.ports.repositories import UnitOfWork
from app.application.ports.services import Cipher
from app.domain.entities import Proxy
from app.domain.values import ProxyAddress


class ProxyRegistry:
    def __init__(self, cipher: Cipher):
        self._cipher = cipher

    def password(self, proxy: Proxy) -> str | None:
        return self._cipher.decrypt(proxy.password_enc) if proxy.password_enc else None

    def address(self, proxy: Proxy) -> ProxyAddress:
        return ProxyAddress(
            proxy.scheme, proxy.host, proxy.port, proxy.username, self.password(proxy)
        )

    def masked_url(self, proxy: Proxy) -> str:
        return ProxyAddress(proxy.scheme, proxy.host, proxy.port, proxy.username).url(
            mask=True
        )

    def set_address(self, proxy: Proxy, addr: ProxyAddress) -> None:
        proxy.scheme, proxy.host, proxy.port, proxy.username = (
            addr.scheme,
            addr.host,
            addr.port,
            addr.username,
        )
        if addr.password:
            proxy.password_enc = self._cipher.encrypt(addr.password)
        elif not addr.username:
            proxy.password_enc = None
        proxy.reset_check()

    async def get_or_create(
        self, uow: UnitOfWork, url: str, name: str | None = None
    ) -> tuple[Proxy, bool]:
        addr = ProxyAddress.parse(url)
        proxy = await uow.proxies.find(addr.scheme, addr.host, addr.port, addr.username)
        if proxy:
            if addr.password and self.password(proxy) != addr.password:
                proxy.password_enc = self._cipher.encrypt(addr.password)
            return proxy, False
        proxy = Proxy(
            name=name,
            scheme=addr.scheme,
            host=addr.host,
            port=addr.port,
            username=addr.username,
            password_enc=self._cipher.encrypt(addr.password) if addr.password else None,
        )
        await uow.proxies.add(proxy)
        return proxy, True
