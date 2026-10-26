from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.infrastructure.db.mapper import EntityTracker
from app.infrastructure.db.repositories import (
    SqlAccountRepository,
    SqlBulkTaskRepository,
    SqlChatMessageRepository,
    SqlCommentRepository,
    SqlPanelUserRepository,
    SqlProxyRepository,
    SqlTgUserRepository,
    SqlTrackedMessageRepository,
)
from app.infrastructure.db.stats_queries import SqlStatsQueries


def create_engine(url: str) -> AsyncEngine:
    return create_async_engine(
        url,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )


class SqlAlchemyUnitOfWork:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory

    async def __aenter__(self) -> "SqlAlchemyUnitOfWork":
        self.session = self._session_factory()
        db = self.session
        self._tracker = t = EntityTracker(db)
        self.users = SqlPanelUserRepository(db, t)
        self.accounts = SqlAccountRepository(db, t)
        self.proxies = SqlProxyRepository(db, t)
        self.tasks = SqlBulkTaskRepository(db, t)
        self.tracked = SqlTrackedMessageRepository(db, t)
        self.comments = SqlCommentRepository(db, t)
        self.messages = SqlChatMessageRepository(db, t)
        self.tg_users = SqlTgUserRepository(db, t)
        self.stats = SqlStatsQueries(db)
        return self

    async def __aexit__(self, *exc) -> None:
        await self.session.close()  # uncommitted changes are rolled back

    async def commit(self) -> None:
        self._tracker.sync()
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()
        self._tracker.clear()  # entities changed in this unit of work are not saved anymore


class UnitOfWorkFactory:
    def __init__(self, engine: AsyncEngine):
        self._session_factory = async_sessionmaker(engine, expire_on_commit=False)

    def __call__(self) -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(self._session_factory)
