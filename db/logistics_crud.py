import logging
from typing import Optional

from sqlalchemy import select, func, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from models.logistics import Logistics

logger = logging.getLogger(__name__)


async def get_logistics_list(
    session: AsyncSession,
    user_id: int,
    limit: int = 100,
    offset: int = 0,
) -> tuple:
    count_stmt = select(func.count(Logistics.id)).where(
        Logistics.user_id == user_id,
    )
    total = await session.scalar(count_stmt) or 0
    stmt = (
        select(Logistics)
        .where(Logistics.user_id == user_id)
        .order_by(Logistics.id.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [_logistics_to_dict(r) for r in rows], total


async def get_logistics_by_id(
    session: AsyncSession,
    logistics_id: int,
    user_id: int,
) -> Optional[dict]:
    stmt = select(Logistics).where(
        Logistics.id == logistics_id,
        Logistics.user_id == user_id,
    )
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    return _logistics_to_dict(row) if row else None


async def create_logistics(
    session: AsyncSession,
    user_id: int,
    data: dict,
) -> int:
    record = Logistics(user_id=user_id, **data)
    session.add(record)
    await session.flush()
    return record.id


async def update_logistics(
    session: AsyncSession,
    logistics_id: int,
    user_id: int,
    fields: dict,
) -> bool:
    stmt = select(Logistics).where(
        Logistics.id == logistics_id,
        Logistics.user_id == user_id,
    )
    result = await session.execute(stmt)
    record = result.scalar_one_or_none()
    if not record:
        return False
    for key, value in fields.items():
        if hasattr(record, key):
            setattr(record, key, value)
    return True


async def delete_logistics(
    session: AsyncSession,
    logistics_id: int,
    user_id: int,
) -> bool:
    stmt = select(Logistics).where(
        Logistics.id == logistics_id,
        Logistics.user_id == user_id,
    )
    result = await session.execute(stmt)
    record = result.scalar_one_or_none()
    if not record:
        return False
    await session.delete(record)
    return True


async def batch_delete_logistics(
    session: AsyncSession,
    ids: list,
    user_id: int,
) -> int:
    stmt = sa_delete(Logistics).where(
        Logistics.id.in_(ids),
        Logistics.user_id == user_id,
    )
    result = await session.execute(stmt)
    return result.rowcount


def _logistics_to_dict(record: Logistics) -> dict:
    return {c.name: getattr(record, c.name) for c in Logistics.__table__.columns}
