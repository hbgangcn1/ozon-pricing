import logging
from collections.abc import AsyncGenerator
from urllib.parse import quote_plus

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)

from db_config import POSTGRES_CONFIG

logger = logging.getLogger(__name__)

_cfg = POSTGRES_CONFIG
_pw = quote_plus(_cfg["password"])
_async_url = (
    f"postgresql+asyncpg://{_cfg['user']}:{_pw}"
    f"@{_cfg['host']}:{_cfg['port']}/{_cfg['database']}"
)

engine = create_async_engine(
    _async_url,
    pool_size=20,
    max_overflow=10,
    pool_recycle=3600,
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """请求级会话依赖。自动 commit/rollback。"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def run_migrations() -> None:
    """同步调用 Alembic upgrade head。在 app startup 时调用。"""
    from alembic.config import Config
    from alembic import command
    import os

    alembic_ini = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "alembic.ini",
    )
    alembic_cfg = Config(alembic_ini)
    command.upgrade(alembic_cfg, "head")
    logger.info("Alembic migrations applied successfully")
