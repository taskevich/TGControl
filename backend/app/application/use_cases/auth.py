import time
from dataclasses import dataclass

from app.application.policies import Policies
from app.application.ports.repositories import UnitOfWorkFactory
from app.application.ports.services import (
    KeyValueStore,
    PasswordHasher,
    TokenClaims,
    TokenService,
)
from app.domain.entities import PanelUser
from app.domain.errors import (
    AuthenticationFailed,
    DomainError,
    NotFound,
    TooManyRequests,
)

UNAUTHORIZED = "Требуется авторизация"


@dataclass
class CurrentUser:
    user: PanelUser
    claims: TokenClaims


class AuthService:
    def __init__(
        self,
        uow: UnitOfWorkFactory,
        hasher: PasswordHasher,
        tokens: TokenService,
        kv: KeyValueStore,
        policies: Policies,
    ):
        self._uow = uow
        self._hasher = hasher
        self._tokens = tokens
        self._kv = kv
        self._policies = policies

    async def login(
        self, username: str, password: str, client_ip: str
    ) -> tuple[str, int]:
        key = f"login:fail:{client_ip}"
        if int(await self._kv.get(key) or 0) >= self._policies.login_max_attempts:
            raise TooManyRequests(
                "Слишком много попыток входа, попробуйте через 15 минут"
            )
        async with self._uow() as uow:
            user = await uow.users.by_username(username)
        if (
            not user
            or not user.is_active
            or not self._hasher.verify(password, user.password_hash)
        ):
            await self._kv.incr(key, ex=self._policies.login_block_seconds)
            raise AuthenticationFailed("Неверный логин или пароль")
        await self._kv.delete(key)
        return self._tokens.issue(user.username)

    async def authenticate(self, token: str | None) -> CurrentUser:
        if not token:
            raise AuthenticationFailed(UNAUTHORIZED)
        try:
            claims = self._tokens.decode(token)
        except AuthenticationFailed:
            raise AuthenticationFailed(UNAUTHORIZED) from None
        if await self._kv.exists(f"jwt:blacklist:{claims.token_id}"):
            raise AuthenticationFailed(UNAUTHORIZED)
        async with self._uow() as uow:
            user = await uow.users.by_username(claims.subject)
        if not user or not user.is_active:
            raise AuthenticationFailed(UNAUTHORIZED)
        return CurrentUser(user, claims)

    async def logout(self, current: CurrentUser) -> None:
        ttl = max(int(current.claims.expires_at - time.time()), 1)
        await self._kv.set(f"jwt:blacklist:{current.claims.token_id}", "1", ex=ttl)

    async def change_password(
        self, user_id: int, old_password: str, new_password: str
    ) -> None:
        async with self._uow() as uow:
            user = await uow.users.get(user_id)
            if not user or not self._hasher.verify(old_password, user.password_hash):
                raise DomainError("Старый пароль неверен")
            user.password_hash = self._hasher.hash(new_password)
            await uow.commit()


class PanelUsers:
    def __init__(self, uow: UnitOfWorkFactory, hasher: PasswordHasher):
        self._uow = uow
        self._hasher = hasher

    async def all(self) -> list[PanelUser]:
        async with self._uow() as uow:
            return await uow.users.all()

    async def create(self, username: str, password: str) -> PanelUser:
        async with self._uow() as uow:
            if await uow.users.by_username(username):
                raise DomainError("Пользователь уже существует")
            user = PanelUser(
                username=username, password_hash=self._hasher.hash(password)
            )
            uow.users.add(user)
            await uow.commit()
            return user

    async def delete(self, user_id: int, current_user_id: int) -> None:
        if user_id == current_user_id:
            raise DomainError("Нельзя удалить самого себя")
        async with self._uow() as uow:
            user = await uow.users.get(user_id)
            if not user:
                raise NotFound("Не найден")
            await uow.users.delete(user)
            await uow.commit()

    async def set_password(self, username: str, password: str, *, create: bool) -> None:
        async with self._uow() as uow:
            user = await uow.users.by_username(username)
            if user is None:
                if not create:
                    raise NotFound(f"Пользователь {username} не найден")
                uow.users.add(
                    PanelUser(
                        username=username, password_hash=self._hasher.hash(password)
                    )
                )
            else:
                user.password_hash = self._hasher.hash(password)
                user.is_active = True
            await uow.commit()

    async def ensure_admin(self, username: str, password: str) -> bool:
        async with self._uow() as uow:
            if await uow.users.count():
                return False
            uow.users.add(
                PanelUser(username=username, password_hash=self._hasher.hash(password))
            )
            await uow.commit()
            return True
