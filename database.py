import logging
from collections.abc import AsyncGenerator
from urllib.parse import quote_plus

from sqlalchemy.exc import InterfaceError as SAInterfaceError
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)

from db_config import POSTGRES_CONFIG

logger = logging.getLogger(__name__)


def _is_connection_dead(exc: Exception) -> bool:
    if isinstance(exc, SAInterfaceError):
        return True
    msg = str(exc).lower()
    return "connection" in msg and ("closed" in msg or "does not exist" in msg)


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
    pool_pre_ping=True,
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
        except Exception as exc:
            if _is_connection_dead(exc):
                logger.warning(
                    "数据库连接已断开，跳过 commit（%s）",
                    type(exc).__name__,
                )
                return
            try:
                await session.rollback()
            except Exception:
                logger.warning("数据库连接已断开，跳过 rollback")
            raise


async def run_migrations() -> None:
    """异步执行 Alembic upgrade head。使用 advisory lock 防止多 worker 竞争。"""
    from alembic.config import Config
    from sqlalchemy import text
    import os

    alembic_ini = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "alembic.ini",
    )
    alembic_cfg = Config(alembic_ini)

    async with engine.connect() as connection:
        lock_acquired = await connection.scalar(
            text("SELECT pg_try_advisory_lock(73571)")
        )
        if not lock_acquired:
            logger.info("Another worker is running migrations, skipping")
            return
        try:
            await connection.run_sync(_do_alembic_upgrade, alembic_cfg)
            logger.info("Alembic migrations applied successfully")
        finally:
            await connection.execute(text("SELECT pg_advisory_unlock(73571)"))


def _do_alembic_upgrade(connection, alembic_cfg):
    from alembic import command

    alembic_cfg.attributes["connection"] = connection
    command.upgrade(alembic_cfg, "head")
