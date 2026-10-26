from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol

from app.application.dto import ParsedUploads
from app.domain.values import ProxyAddress


class Cipher(Protocol):
    def encrypt(self, value: str) -> str: ...
    def decrypt(self, value: str) -> str: ...


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...
    def verify(self, password: str, password_hash: str) -> bool: ...


@dataclass(frozen=True)
class TokenClaims:
    subject: str
    token_id: str
    expires_at: float


class TokenService(Protocol):
    def issue(self, subject: str) -> tuple[str, int]: ...
    def decode(self, token: str) -> TokenClaims: ...


class KeyValueStore(Protocol):
    async def get(self, key: str) -> str | None: ...
    async def set(
        self, key: str, value: str, *, ex: int | None = None, nx: bool = False
    ) -> bool: ...

    async def delete(self, key: str) -> None: ...
    async def exists(self, key: str) -> bool: ...
    async def incr(self, key: str, *, ex: int | None = None) -> int: ...
    async def close(self) -> None: ...


@dataclass
class StoredObject:
    chunks: AsyncIterator[bytes]
    length: int
    content_type: str | None = None
    content_range: str | None = None


class FileStorage(Protocol):
    async def prepare(self) -> None: ...
    async def put_file(self, key: str, path: str, content_type: str | None) -> None: ...
    async def open(self, key: str, byte_range: str | None = None) -> StoredObject: ...
    async def delete(self, key: str) -> None: ...


class Signer(Protocol):
    def sign(self, value: str) -> str: ...
    def verify(self, value: str, signature: str) -> bool: ...


class ProxyChecker(Protocol):
    async def check(
        self, proxy: ProxyAddress
    ) -> tuple[bool, int | None, str | None]: ...


class SessionFileParser(Protocol):
    def parse(
        self, files: list[tuple[str, bytes]], string_sessions: str = ""
    ) -> ParsedUploads: ...
