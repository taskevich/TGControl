from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine

from app.application.services.archive import MessageArchive
from app.application.services.proxies import ProxyRegistry
from app.application.services.telegram_access import AccountClients
from app.application.services.tracking import MessageTracker
from app.application.use_cases.account_onboarding import PhoneLogin, SessionImport
from app.application.use_cases.accounts import AccountRegistrar, Accounts
from app.application.use_cases.auth import AuthService, PanelUsers
from app.application.use_cases.bulk import BulkTasks
from app.application.use_cases.chats import AccountChats
from app.application.use_cases.media import MediaFiles
from app.application.use_cases.messages import SavedMessages
from app.application.use_cases.proxies import Proxies
from app.application.use_cases.stats import Statistics
from app.infrastructure.config import Settings
from app.infrastructure.db.uow import UnitOfWorkFactory, create_engine
from app.infrastructure.proxy_checker import SocksProxyChecker
from app.infrastructure.redis_store import RedisStore
from app.infrastructure.s3_storage import S3FileStorage
from app.infrastructure.security import BcryptHasher, FernetCipher, HmacSigner, JwtTokenService
from app.infrastructure.telegram.client import ClientFactory
from app.infrastructure.telegram.connector import TelethonAuth, TelethonConnector
from app.infrastructure.telegram.session_files import (
    TelethonSessionFileBuilder,
    TelethonSessionFileParser,
)


@dataclass
class Container:
    settings: Settings
    engine: AsyncEngine
    kv: RedisStore
    clients: AccountClients
    auth: AuthService
    users: PanelUsers
    accounts: Accounts
    login: PhoneLogin
    importer: SessionImport
    proxies: Proxies
    chats: AccountChats
    messages: SavedMessages
    media: MediaFiles
    stats: Statistics
    bulk: BulkTasks

    async def close(self) -> None:
        await self.clients.shutdown()
        await self.kv.close()
        await self.engine.dispose()


def build_container(settings: Settings) -> Container:
    policies = settings.policies()
    engine = create_engine(settings.DATABASE_URL)
    uow = UnitOfWorkFactory(engine)
    kv = RedisStore(settings.REDIS_URL)
    cipher = FernetCipher(settings.SESSION_ENCRYPTION_KEY, settings.SECRET_KEY)
    hasher = BcryptHasher()
    tokens = JwtTokenService(settings.SECRET_KEY, settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    factory = ClientFactory(settings.client_defaults())
    tg_auth = TelethonAuth(factory)

    registry = ProxyRegistry(cipher)
    clients = AccountClients(TelethonConnector(factory), cipher, registry)
    s3 = settings.s3_config()
    media = MediaFiles(uow, clients, S3FileStorage(s3) if s3 else None, HmacSigner(settings.SECRET_KEY), kv, policies,
                       settings.MEDIA_TMP_DIR)
    archive = MessageArchive(media.max_size)
    tracker = MessageTracker(clients, policies)
    registrar = AccountRegistrar(cipher, registry, clients)

    return Container(
        settings=settings,
        engine=engine,
        kv=kv,
        clients=clients,
        auth=AuthService(uow, hasher, tokens, kv, policies),
        users=PanelUsers(uow, hasher),
        accounts=Accounts(uow, clients, cipher, registry, TelethonSessionFileBuilder()),
        login=PhoneLogin(uow, tg_auth, kv, cipher, registry, registrar, clients, policies),
        importer=SessionImport(uow, tg_auth, TelethonSessionFileParser(), registry, registrar),
        proxies=Proxies(uow, registry, SocksProxyChecker(), clients),
        chats=AccountChats(uow, clients, archive, tracker, kv, policies),
        messages=SavedMessages(uow, clients, archive, kv, policies),
        media=media,
        stats=Statistics(uow, clients, tracker, kv, policies),
        bulk=BulkTasks(uow, clients, tracker, kv, policies),
    )
