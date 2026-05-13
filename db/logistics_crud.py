import logging
import time
from typing import Any, Optional, cast

from sqlalchemy import select, func, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from models.logistics import Logistics

logger = logging.getLogger(__name__)

_ALLOWED_FIELDS = {
    "name",
    "type",
    "min_days",
    "max_days",
    "price_limit_cny",
    "price_min_cny",
    "base_fee",
    "min_weight",
    "max_weight",
    "max_sum_of_sides",
    "max_longest_side",
    "max_second_side",
    "max_third_side",
    "min_second_side",
    "min_length",
    "max_cylinder_sum",
    "min_cylinder_sum",
    "max_cylinder_length",
    "min_cylinder_length",
    "volume_mode",
    "longest_side_threshold",
    "sum_of_sides_threshold",
    "allow_battery",
    "allow_liquid",
    "battery_capacity_limit_wh",
    "require_msds",
    "fee_mode",
    "first_fee",
    "first_weight_g",
    "continue_fee",
    "continue_unit",
    "volume_coefficient",
    "delivery_method",
    "priority_group",
    "scoring_group",
    "fulfillment_type",
    "destination",
    "fbp_service_level",
    "fbp_company",
    "is_smart",
    "is_active",
}


def _clean_fields(fields: dict) -> dict:
    return {key: value for key, value in fields.items() if key in _ALLOWED_FIELDS}


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


async def get_logistics_by_filters(
    session: AsyncSession,
    user_id: int,
    fulfillment_type: Optional[str] = None,
    destination: Optional[str] = None,
    type: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[dict], int]:
    filters = [Logistics.user_id == user_id]
    if fulfillment_type is not None:
        filters.append(Logistics.fulfillment_type == fulfillment_type)
    if destination is not None:
        filters.append(Logistics.destination == destination)
    if type is not None:
        filters.append(Logistics.type == type)

    count_stmt = select(func.count(Logistics.id)).where(*filters)
    total = await session.scalar(count_stmt) or 0

    stmt = (
        select(Logistics)
        .where(*filters)
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
    record = Logistics(user_id=user_id, **_clean_fields(data))
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
    for key, value in _clean_fields(fields).items():
        if hasattr(record, key):
            setattr(record, key, value)
    record.updated_at = int(time.time())
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
    rowcount = cast(Any, result).rowcount
    return rowcount or 0


def _logistics_to_dict(record: Logistics) -> dict:
    return {c.name: getattr(record, c.name) for c in Logistics.__table__.columns}
