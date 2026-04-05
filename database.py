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


async def run_migrations() -> None:
    """异步执行 Alembic upgrade head。在 app lifespan 中 await 调用。"""
    from alembic.config import Config
    import os

    alembic_ini = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "alembic.ini",
    )
    alembic_cfg = Config(alembic_ini)

    # 复用已有 engine 执行迁移，避免 asyncio.run() 冲突
    async with engine.connect() as connection:
        await connection.run_sync(_do_alembic_upgrade, alembic_cfg)
    logger.info("Alembic migrations applied successfully")


def _do_alembic_upgrade(connection, alembic_cfg):
    from alembic import command

    alembic_cfg.attributes["connection"] = connection
    command.upgrade(alembic_cfg, "head")
