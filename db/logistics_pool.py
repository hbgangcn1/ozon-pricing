import logging
from typing import Optional

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.logistics_pool import LogisticsPool

logger = logging.getLogger(__name__)

_FIELDS = {c.name for c in LogisticsPool.__table__.columns}
_UPSERT_FIELDS = _FIELDS - {"id"}


def _to_dict(record: LogisticsPool) -> dict:
    return {c.name: getattr(record, c.name) for c in LogisticsPool.__table__.columns}


async def get_all(
    session: AsyncSession,
    fulfillment_type: Optional[str] = None,
    destination: Optional[str] = None,
    fbp_service_level: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[dict], int]:
    stmt = select(LogisticsPool)
    count_stmt = select(func.count(LogisticsPool.id))
    for field, value in {
        "fulfillment_type": fulfillment_type,
        "destination": destination,
        "fbp_service_level": fbp_service_level,
    }.items():
        if value is not None:
            column = getattr(LogisticsPool, field)
            stmt = stmt.where(column == value)
            count_stmt = count_stmt.where(column == value)
    total = await session.scalar(count_stmt) or 0
    result = await session.execute(
        stmt.order_by(LogisticsPool.id.desc()).limit(limit).offset(offset),
    )
    rows = result.scalars().all()
    await session.flush()
    return [_to_dict(row) for row in rows], total


async def get_by_id(session: AsyncSession, pool_id: int) -> Optional[dict]:
    result = await session.execute(
        select(LogisticsPool).where(LogisticsPool.id == pool_id),
    )
    row = result.scalar_one_or_none()
    await session.flush()
    return _to_dict(row) if row else None


async def upsert(session: AsyncSession, data: dict) -> int:
    result = await session.execute(
        select(LogisticsPool).where(
            LogisticsPool.source_file == data.get("source_file"),
            LogisticsPool.delivery_method == data.get("delivery_method"),
            LogisticsPool.destination == data.get("destination"),
        ),
    )
    record = result.scalar_one_or_none()
    clean = {k: v for k, v in data.items() if k in _UPSERT_FIELDS}
    if record:
        for key, value in clean.items():
            setattr(record, key, value)
    else:
        record = LogisticsPool(**clean)
        session.add(record)
    await session.flush()
    return record.id


async def insert_row(session: AsyncSession, data: dict) -> int:
    clean = {k: v for k, v in data.items() if k in _UPSERT_FIELDS}
    record = LogisticsPool(**clean)
    session.add(record)
    await session.flush()
    return record.id


async def set_active(session: AsyncSession, pool_id: int, is_active: int) -> bool:
    result = await session.execute(
        select(LogisticsPool).where(LogisticsPool.id == pool_id),
    )
    record = result.scalar_one_or_none()
    if not record:
        await session.flush()
        return False
    record.is_active = is_active
    await session.flush()
    return True


async def delete_all(session: AsyncSession) -> int:
    result = await session.execute(select(func.count(LogisticsPool.id)))
    count = result.scalar() or 0
    await session.execute(
        delete(LogisticsPool).execution_options(synchronize_session=False)
    )
    await session.flush()
    return count
