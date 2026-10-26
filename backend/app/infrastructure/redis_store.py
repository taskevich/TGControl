from redis.asyncio import Redis


class RedisStore:
    def __init__(self, url: str):
        self._redis: Redis = Redis.from_url(url, decode_responses=True)

    async def get(self, key: str) -> str | None:
        return await self._redis.get(key)

    async def set(
        self, key: str, value: str, *, ex: int | None = None, nx: bool = False
    ) -> bool:
        return bool(await self._redis.set(key, value, ex=ex, nx=nx))

    async def delete(self, key: str) -> None:
        await self._redis.delete(key)

    async def exists(self, key: str) -> bool:
        return bool(await self._redis.exists(key))

    async def incr(self, key: str, *, ex: int | None = None) -> int:
        value = await self._redis.incr(key)
        if ex:
            await self._redis.expire(key, ex)
        return value

    async def close(self) -> None:
        await self._redis.aclose()
