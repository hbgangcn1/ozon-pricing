import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.config import SystemConfig

logger = logging.getLogger(__name__)


async def get_system_config(
    session: AsyncSession,
    key: str,
) -> Optional[str]:
    stmt = select(SystemConfig.config_value).where(
        SystemConfig.config_key == key,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def set_system_config(
    session: AsyncSession,
    key: str,
    value: str,
    description: str = "",
) -> None:
    stmt = select(SystemConfig).where(
        SystemConfig.config_key == key,
    )
    result = await session.execute(stmt)
    config = result.scalar_one_or_none()
    if config:
        config.config_value = value
        if description:
            config.description = description
    else:
        config = SystemConfig(
            config_key=key,
            config_value=value,
            description=description,
        )
        session.add(config)


async def is_registration_open(session: AsyncSession) -> bool:
    value = await get_system_config(session, "registration_open")
    return value != "0"


async def get_all_config(session: AsyncSession) -> list[dict]:
    stmt = select(SystemConfig).order_by(SystemConfig.config_key)
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "config_key": r.config_key,
            "config_value": r.config_value,
            "description": r.description,
            "updated_at": (r.updated_at.isoformat() if r.updated_at else None),
        }
        for r in rows
    ]
