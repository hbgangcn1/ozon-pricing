import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import Plan

logger = logging.getLogger(__name__)


def _decode_features(raw) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(item) for item in raw if item]
    if isinstance(raw, str):
        return [token.strip() for token in raw.split("|") if token.strip()]
    return []


def _plan_to_dict(plan: Plan) -> dict:
    return {
        "id": plan.id,
        "plan_code": plan.plan_code,
        "plan_name": plan.plan_name,
        "display_price_month": plan.display_price_month,
        "display_price_year": plan.display_price_year,
        "actual_price_month": plan.actual_price_month,
        "actual_price_year": plan.actual_price_year,
        "test_price_month": plan.test_price_month,
        "test_price_year": plan.test_price_year,
        "calc_limit": plan.calc_limit,
        "logistics_limit": plan.logistics_limit,
        "description": plan.description,
        "features": _decode_features(plan.features),
        "is_active": plan.is_active,
        "sort_order": plan.sort_order,
        "created_at": plan.created_at,
        "updated_at": plan.updated_at,
    }


async def get_plans(
    session: AsyncSession,
    active_only: bool = False,
    include_free: bool = True,
) -> list[dict]:
    stmt = select(Plan)
    if active_only:
        stmt = stmt.where(Plan.is_active == 1)
    if not include_free:
        stmt = stmt.where(Plan.plan_code != "free")
    stmt = stmt.order_by(Plan.sort_order)
    result = await session.execute(stmt)
    return [_plan_to_dict(p) for p in result.scalars().all()]


async def get_plan_by_code(
    session: AsyncSession,
    code: str,
) -> Optional[dict]:
    stmt = select(Plan).where(Plan.plan_code == code)
    result = await session.execute(stmt)
    plan = result.scalar_one_or_none()
    return _plan_to_dict(plan) if plan else None


async def get_plan_by_id(
    session: AsyncSession,
    plan_id: int,
) -> Optional[dict]:
    plan = await session.get(Plan, plan_id)
    return _plan_to_dict(plan) if plan else None


async def create_plan(
    session: AsyncSession,
    data: dict,
) -> int:
    plan = Plan(**data)
    session.add(plan)
    await session.flush()
    return plan.id


async def update_plan(
    session: AsyncSession,
    plan_id: int,
    data: dict,
) -> bool:
    plan = await session.get(Plan, plan_id)
    if not plan:
        return False
    for key, value in data.items():
        if hasattr(plan, key):
            setattr(plan, key, value)
    return True


async def delete_plan(
    session: AsyncSession,
    plan_id: int,
) -> bool:
    plan = await session.get(Plan, plan_id)
    if not plan:
        return False
    await session.delete(plan)
    return True


async def toggle_plan_active(
    session: AsyncSession,
    plan_id: int,
) -> Optional[int]:
    plan = await session.get(Plan, plan_id)
    if not plan:
        return None
    plan.is_active = 0 if plan.is_active == 1 else 1
    return plan.is_active


async def get_plan_price(
    session: AsyncSession,
    plan_code: str,
    billing_cycle: str = "month",
    use_test_price: bool = False,
) -> Optional[float]:
    stmt = select(Plan).where(Plan.plan_code == plan_code)
    result = await session.execute(stmt)
    plan = result.scalar_one_or_none()
    if not plan:
        return None
    if use_test_price:
        if billing_cycle == "year":
            return plan.test_price_year
        return plan.test_price_month
    if billing_cycle == "year":
        return plan.actual_price_year
    return plan.actual_price_month
