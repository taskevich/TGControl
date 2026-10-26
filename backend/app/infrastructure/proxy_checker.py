import asyncio
import time

from python_socks.async_.asyncio import Proxy as SocksProxy

from app.domain.values import ProxyAddress

CHECK_HOST = "149.154.167.51"
CHECK_PORT = 443


class SocksProxyChecker:
    def __init__(self, timeout: float = 10):
        self._timeout = timeout

    async def check(self, proxy: ProxyAddress) -> tuple[bool, int | None, str | None]:
        started = time.monotonic()
        try:
            socks = SocksProxy.from_url(proxy.url(), rdns=True)
            sock = await asyncio.wait_for(
                socks.connect(
                    dest_host=CHECK_HOST, dest_port=CHECK_PORT, timeout=self._timeout
                ),
                self._timeout + 2,
            )
            try:
                sock.close()
            except Exception:  # noqa: BLE001
                pass
            return True, int((time.monotonic() - started) * 1000), None
        except Exception as e:  # noqa: BLE001
            return False, None, f"{type(e).__name__}: {e}"[:500]
