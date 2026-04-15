import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.commission_category import CommissionCategory

logger = logging.getLogger(__name__)

_ALLOWED_UPDATE_FIELDS = {
    "name",
    "fbp_tier1_rate",
    "fbp_tier2_rate",
    "fbp_tier3_rate",
    "rfbs_tier1_rate",
    "rfbs_tier2_rate",
    "rfbs_tier3_rate",
    "is_active",
}


def _to_dict(category: CommissionCategory) -> dict:
    return {
        c.name: getattr(category, c.name) for c in CommissionCategory.__table__.columns
    }


async def get_all(
    session: AsyncSession,
    include_inactive: bool = False,
    user_id: int = 0,
) -> list[dict]:
    stmt = (
        select(CommissionCategory)
        .where(
            CommissionCategory.user_id == user_id,
        )
        .order_by(CommissionCategory.id)
    )
    if not include_inactive:
        stmt = stmt.where(CommissionCategory.is_active == 1)
    result = await session.execute(stmt)
    rows = result.scalars().all()
    await session.flush()
    return [_to_dict(row) for row in rows]


async def get_by_id(
    session: AsyncSession,
    category_id: int,
    user_id: int,
) -> Optional[dict]:
    result = await session.execute(
        select(CommissionCategory).where(
            CommissionCategory.id == category_id,
            CommissionCategory.user_id == user_id,
        ),
    )
    row = result.scalar_one_or_none()
    await session.flush()
    return _to_dict(row) if row else None


async def create(session: AsyncSession, data: dict) -> Optional[int]:
    existing = await session.scalar(
        select(CommissionCategory.id).where(
            CommissionCategory.name == data.get("name"),
            CommissionCategory.user_id == data.get("user_id"),
        ),
    )
    if existing is not None:
        await session.flush()
        return None
    category = CommissionCategory(**data)
    session.add(category)
    await session.flush()
    return category.id


async def update(
    session: AsyncSession,
    category_id: int,
    data: dict,
    user_id: int,
) -> bool:
    result = await session.execute(
        select(CommissionCategory).where(
            CommissionCategory.id == category_id,
            CommissionCategory.user_id == user_id,
        ),
    )
    category = result.scalar_one_or_none()
    if not category:
        await session.flush()
        return False
    if "name" in data:
        existing = await session.scalar(
            select(CommissionCategory.id).where(
                CommissionCategory.name == data["name"],
                CommissionCategory.user_id == user_id,
                CommissionCategory.id != category_id,
            ),
        )
        if existing is not None:
            await session.flush()
            return False
    for key, value in data.items():
        if key in _ALLOWED_UPDATE_FIELDS and hasattr(category, key):
            setattr(category, key, value)
    await session.flush()
    return True


async def soft_delete(
    session: AsyncSession,
    category_id: int,
    user_id: int,
) -> bool:
    result = await session.execute(
        select(CommissionCategory).where(
            CommissionCategory.id == category_id,
            CommissionCategory.user_id == user_id,
        ),
    )
    category = result.scalar_one_or_none()
    if not category:
        await session.flush()
        return False
    category.is_active = 0
    await session.flush()
    return True
