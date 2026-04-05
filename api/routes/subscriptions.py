from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from db.subscriptions import get_user_subscription_info
from db.plans import get_plans, get_plan_by_code
from api.dependencies import get_current_user_id

router = APIRouter(prefix="/api/subscriptions", tags=["订阅"])


class PlanResponse(BaseModel):
    id: int
    code: str
    name: str
    display_price_month: float
    display_price_year: float
    actual_price_month: float
    actual_price_year: float
    test_price_month: float
    test_price_year: float
    calc_limit: int
    logistics_limit: int
    sort: int
    status: bool
    description: str
    features: List[str]


class SubscriptionResponse(BaseModel):
    plan_code: str
    calc_limit: int
    logistics_limit: int
    expired_at: Optional[str] = None


@router.get("/plans", response_model=List[PlanResponse])
async def get_plans_route(session: AsyncSession = Depends(get_db)):
    try:
        plans = await get_plans(session, active_only=True)
    except Exception:
        return []
    result = []
    for p in plans:
        features = p.get("features", "")
        if isinstance(features, str):
            features = features.split(",") if features else []
        result.append(
            PlanResponse(
                id=p["id"],
                code=p["plan_code"],
                name=p["plan_name"],
                display_price_month=p.get("display_price_month", 0),
                display_price_year=p.get("display_price_year", 0),
                actual_price_month=p.get("actual_price_month", 0),
                actual_price_year=p.get("actual_price_year", 0),
                test_price_month=p.get("test_price_month", 0),
                test_price_year=p.get("test_price_year", 0),
                calc_limit=p.get("calc_limit", -1),
                logistics_limit=p.get("logistics_limit", 1),
                sort=p.get("sort_order", 0),
                status=bool(p.get("is_active", True)),
                description=p.get("description", ""),
                features=features,
            )
        )
    return result


@router.get("/current", response_model=SubscriptionResponse)
async def get_current_subscription(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    info = await get_user_subscription_info(session, user_id)
    if not info:
        raise HTTPException(status_code=404, detail="用户不存在")

    plan_code = info.get("user_type") or "free"
    plan = await get_plan_by_code(session, plan_code)
    calc_limit = plan.get("calc_limit", -1) if plan else -1
    logistics_limit = plan.get("logistics_limit", 1) if plan else 1

    subscription_expires = info.get("subscription_expires")
    expired_at = str(subscription_expires) if subscription_expires else None

    return SubscriptionResponse(
        plan_code=plan_code,
        calc_limit=calc_limit,
        logistics_limit=logistics_limit,
        expired_at=expired_at,
    )
