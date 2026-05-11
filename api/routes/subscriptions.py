from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel, Field
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user_id, require_admin
from database import get_db
from db.config import is_registration_open
from db.plans import (
    create_plan,
    delete_plan,
    get_plan_by_code,
    get_plan_by_id,
    get_plans,
    toggle_plan_active,
    update_plan,
)
from db.subscriptions import get_user_subscription_info
from models.user import User
from services.trial_service import claim_trial, get_trial_status

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
    effective_price_month: float
    effective_price_year: float
    use_test_price: bool
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


class PlanCreateRequest(BaseModel):
    plan_code: str
    plan_name: str
    display_price_month: float = 0
    display_price_year: float = 0
    actual_price_month: float = 0
    actual_price_year: float = 0
    test_price_month: float = 0
    test_price_year: float = 0
    calc_limit: int = -1
    logistics_limit: int = 1
    description: str = ""
    features: List[str] = Field(default_factory=list)
    sort_order: int = 0
    is_active: int = 1


class PlanUpdateRequest(BaseModel):
    plan_code: Optional[str] = None
    plan_name: Optional[str] = None
    display_price_month: Optional[float] = None
    display_price_year: Optional[float] = None
    actual_price_month: Optional[float] = None
    actual_price_year: Optional[float] = None
    test_price_month: Optional[float] = None
    test_price_year: Optional[float] = None
    calc_limit: Optional[int] = None
    logistics_limit: Optional[int] = None
    description: Optional[str] = None
    features: Optional[List[str]] = None
    sort_order: Optional[int] = None
    is_active: Optional[int] = None


def _to_plan_response(
    p: dict,
    use_test_price: bool = False,
) -> PlanResponse:
    features = p.get("features", "")
    if isinstance(features, str):
        features = (
            [f.strip() for f in features.split("|")]
            if features else []
        )

    actual_m = p.get("actual_price_month", 0)
    actual_y = p.get("actual_price_year", 0)
    test_m = p.get("test_price_month", 0)
    test_y = p.get("test_price_year", 0)

    return PlanResponse(
        id=p["id"],
        code=p["plan_code"],
        name=p["plan_name"],
        display_price_month=p.get("display_price_month", 0),
        display_price_year=p.get("display_price_year", 0),
        actual_price_month=actual_m,
        actual_price_year=actual_y,
        test_price_month=test_m,
        test_price_year=test_y,
        effective_price_month=test_m if use_test_price else actual_m,
        effective_price_year=test_y if use_test_price else actual_y,
        use_test_price=use_test_price,
        calc_limit=p.get("calc_limit", -1),
        logistics_limit=p.get("logistics_limit", 1),
        sort=p.get("sort_order", 0),
        status=bool(p.get("is_active", True)),
        description=p.get("description", ""),
        features=features,
    )


@router.get("/plans", response_model=List[PlanResponse])
async def get_plans_route(
    active_only: bool = True,
    session: AsyncSession = Depends(get_db),
):
    try:
        is_open = await is_registration_open(session)
        use_test = not is_open
        plans = await get_plans(session, active_only=active_only)
    except Exception as e:
        logger.exception(f"获取套餐列表失败: {e}")
        return []
    return [_to_plan_response(plan, use_test_price=use_test) for plan in plans]


@router.get("/current", response_model=SubscriptionResponse)
async def get_current_subscription(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    try:
        info = await get_user_subscription_info(session, user_id)
    except Exception as e:
        logger.exception(f"获取当前订阅信息失败: user_id={user_id}, error={e}")
        raise HTTPException(status_code=404, detail="用户不存在")
    if not info:
        raise HTTPException(status_code=404, detail="用户不存在")

    plan_code = info.get("subscription_type") or info.get("user_type") or "free"
    try:
        plan = await get_plan_by_code(session, plan_code)
    except Exception as e:
        logger.exception(f"获取订阅套餐失败: user_id={user_id}, plan_code={plan_code}, error={e}")
        plan = None
    if not plan and plan_code != "free":
        plan_code = "free"
        try:
            plan = await get_plan_by_code(session, plan_code)
        except Exception as e:
            logger.exception(f"获取默认订阅套餐失败: user_id={user_id}, error={e}")
            plan = None
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


@router.post("/plans", response_model=PlanResponse, status_code=201)
async def create_plan_route(
    req: PlanCreateRequest,
    admin_id: int = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    del admin_id
    data = req.model_dump()
    data["features"] = "|".join(data["features"])
    plan_id = await create_plan(session, data)
    await session.commit()
    plan = await get_plan_by_id(session, plan_id)
    if not plan:
        raise HTTPException(status_code=500, detail="套餐创建失败")
    return _to_plan_response(plan)


@router.put("/plans/{plan_id}", response_model=PlanResponse)
async def update_plan_route(
    plan_id: int,
    req: PlanUpdateRequest,
    admin_id: int = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    del admin_id
    data = req.model_dump(exclude_unset=True)
    if "features" in data:
        data["features"] = "|".join(data["features"])
    success = await update_plan(session, plan_id, data)
    if not success:
        raise HTTPException(status_code=404, detail="套餐不存在")
    await session.commit()
    plan = await get_plan_by_id(session, plan_id)
    if not plan:
        raise HTTPException(status_code=500, detail="套餐更新失败")
    return _to_plan_response(plan)


@router.delete("/plans/{plan_id}")
async def delete_plan_route(
    plan_id: int,
    admin_id: int = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    del admin_id
    success = await delete_plan(session, plan_id)
    if not success:
        raise HTTPException(status_code=404, detail="套餐不存在")
    await session.commit()
    return {"message": "套餐已删除"}


@router.patch("/plans/{plan_id}/toggle")
async def toggle_plan_route(
    plan_id: int,
    admin_id: int = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    del admin_id
    new_status = await toggle_plan_active(session, plan_id)
    if new_status is None:
        raise HTTPException(status_code=404, detail="套餐不存在")
    await session.commit()
    return {"is_active": bool(new_status)}


class TrialClaimResponse(BaseModel):
    status: str
    trial_started_at: int
    trial_expires_at: int


class TrialStatusResponse(BaseModel):
    eligible: bool
    in_trial: bool
    trial_used: bool
    remaining_seconds: int
    trial_expires_at: int
    trial_started_at: int


@router.post("/trial/claim", response_model=TrialClaimResponse)
async def claim_trial_route(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    result = await claim_trial(session, user_id)
    if result.status == "user_not_found":
        raise HTTPException(status_code=404, detail="用户不存在")
    if result.status == "already_used":
        raise HTTPException(status_code=409, detail="试用已使用")
    if result.status == "ineligible_plan":
        raise HTTPException(status_code=409, detail="当前套餐不可领取试用")
    await session.commit()
    return TrialClaimResponse(
        status=result.status,
        trial_started_at=result.trial_started_at,
        trial_expires_at=result.trial_expires_at,
    )


@router.get("/trial/status", response_model=TrialStatusResponse)
async def trial_status_route(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    status = get_trial_status(user)
    return TrialStatusResponse(
        eligible=status.eligible,
        in_trial=status.in_trial,
        trial_used=status.trial_used,
        remaining_seconds=status.remaining_seconds,
        trial_expires_at=status.trial_expires_at,
        trial_started_at=status.trial_started_at,
    )
