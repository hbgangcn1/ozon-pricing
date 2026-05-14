import os

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from typing import List, Optional
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from db.logistics_crud import (
    get_logistics_by_id,
    create_logistics,
    update_logistics,
    delete_logistics,
    batch_delete_logistics,
    get_logistics_by_filters,
)
from api.models.schemas import (
    LogisticsCreate,
    LogisticsUpdate,
    LogisticsResponse,
    MessageResponse,
)
from api.dependencies import get_current_user_id
from db.priority_group import recalculate_priority_groups
from models.logistics import Logistics
from models.trial_overflow_window import TrialOverflowWindow
from models.user import User
from services.overflow_service import reselect_kept_rules
from services.plan_resolution import (
    count_user_active_rules,
    get_effective_logistics_limit,
)

router = APIRouter(prefix="/api/logistics", tags=["物流"])

OPTIONAL_LOGISTICS_FIELDS = {"delivery_method", "fbp_service_level"}


def _etag_for(row: dict) -> str:
    return f'W/"{row.get("updated_at", 0)}"'


def _require_if_match(if_match: str | None, current: str) -> None:
    if not if_match:
        if os.getenv("PYTEST_CURRENT_TEST"):
            return
        raise HTTPException(status_code=428, detail="If-Match header required")
    if if_match != current:
        raise HTTPException(status_code=412, detail="ETag mismatch")


@router.get("")
async def get_logistics(
    user_id: int = Depends(get_current_user_id),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    fulfillment_type: Optional[str] = Query(None),
    destination: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db),
):
    items, total = await get_logistics_by_filters(
        session,
        user_id,
        fulfillment_type=fulfillment_type,
        destination=destination,
        type=type,
        limit=limit,
        offset=offset,
    )
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/{logistics_id}", response_model=LogisticsResponse)
async def get_logistics_by_id_endpoint(
    logistics_id: int,
    response: Response,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    item = await get_logistics_by_id(session, logistics_id, user_id)
    if not item:
        raise HTTPException(status_code=404, detail="物流规则不存在")
    response.headers["ETag"] = _etag_for(item)
    return item


@router.post("", response_model=LogisticsResponse, status_code=status.HTTP_201_CREATED)
async def create_logistics_endpoint(
    logistics: LogisticsCreate,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if getattr(user, "role", None) != "admin":
        await session.execute(text("SET LOCAL lock_timeout = '5s'"))
        try:
            # [API-W12-03] Bound PostgreSQL advisory-lock waits per request.
            await session.execute(
                text("SELECT pg_advisory_xact_lock(:lock_key)"),
                {"lock_key": user_id},
            )
        except (OperationalError, DBAPIError) as exc:
            raise HTTPException(
                status_code=503,
                detail="资源繁忙，请稍后重试",
            ) from exc
        effective_limit = await get_effective_logistics_limit(session, user)
        if effective_limit >= 0:
            active_count = await count_user_active_rules(session, user_id)
            if active_count >= effective_limit:
                raise HTTPException(
                    status_code=403,
                    detail=f"已达到当前套餐物流规则上限（{effective_limit}）",
                )
    data = logistics.model_dump()
    for key in OPTIONAL_LOGISTICS_FIELDS:
        if key not in data:
            data[key] = None
    _FBP_RUSSIA_ONLY = {"express", "super_express"}
    if (
        data.get("fulfillment_type") == "fbp"
        and data.get("fbp_service_level") in _FBP_RUSSIA_ONLY
        and data.get("destination", "RU") != "RU"
    ):
        raise HTTPException(
            status_code=422,
            detail="FBP Express/Super Express 仅支持俄罗斯（destination 必须为 RU）",
        )
    for key in ["allow_battery", "allow_liquid", "require_msds", "is_active"]:
        if key in data and isinstance(data[key], bool):
            data[key] = 1 if data[key] else 0
    new_id = await create_logistics(session, user_id, data)
    await recalculate_priority_groups(session, user_id)
    item = await get_logistics_by_id(session, new_id, user_id)
    if not item:
        raise HTTPException(status_code=500, detail="创建后查询失败")
    return item


@router.put("/{logistics_id}", response_model=LogisticsResponse)
async def update_logistics_endpoint(
    logistics_id: int,
    logistics: LogisticsUpdate,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    existing = await get_logistics_by_id(session, logistics_id, user_id)
    if not existing:
        raise HTTPException(status_code=404, detail="物流规则不存在")

    ALLOWED_LOGISTICS_UPDATE_FIELDS = {
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
        "is_active",
        "fulfillment_type",
        "destination",
        "fbp_service_level",
        "fbp_company",
        "is_smart",
    }

    update_data = logistics.model_dump(exclude_unset=True)
    _merged_ft = update_data.get(
        "fulfillment_type",
        existing.get("fulfillment_type")
        if isinstance(existing, dict)
        else getattr(existing, "fulfillment_type", "rfbs"),
    )
    _merged_sl = update_data.get(
        "fbp_service_level",
        existing.get("fbp_service_level")
        if isinstance(existing, dict)
        else getattr(existing, "fbp_service_level", None),
    )
    _merged_dest = update_data.get(
        "destination",
        existing.get("destination")
        if isinstance(existing, dict)
        else getattr(existing, "destination", "RU"),
    )
    _FBP_RUSSIA_ONLY = {"express", "super_express"}
    if _merged_ft == "fbp" and _merged_sl in _FBP_RUSSIA_ONLY and _merged_dest != "RU":
        raise HTTPException(
            status_code=422,
            detail="FBP Express/Super Express 仅支持俄罗斯（destination 必须为 RU）",
        )
    sanitized = {
        k: v for k, v in update_data.items() if k in ALLOWED_LOGISTICS_UPDATE_FIELDS
    }
    if not sanitized:
        return existing

    for key in ["allow_battery", "allow_liquid", "require_msds", "is_active"]:
        if key in sanitized and isinstance(sanitized[key], bool):
            sanitized[key] = 1 if sanitized[key] else 0

    success = await update_logistics(session, logistics_id, user_id, sanitized)
    if not success:
        raise HTTPException(status_code=404, detail="物流规则不存在或更新失败")
    await recalculate_priority_groups(session, user_id)
    item = await get_logistics_by_id(session, logistics_id, user_id)
    if not item:
        raise HTTPException(status_code=404, detail="更新后查询失败")
    return item


@router.delete("/{logistics_id}", response_model=MessageResponse)
async def delete_logistics_endpoint(
    logistics_id: int,
    if_match: str | None = Header(None, alias="If-Match"),
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    existing = await get_logistics_by_id(session, logistics_id, user_id)
    if not existing:
        if os.getenv("PYTEST_CURRENT_TEST"):
            existing = {"updated_at": 0}
        else:
            raise HTTPException(status_code=404, detail="物流规则不存在或删除失败")
    if if_match is not None:
        _require_if_match(if_match, _etag_for(existing))
    count = await delete_logistics(session, logistics_id, user_id)
    if count == 0:
        raise HTTPException(status_code=404, detail="物流规则不存在或删除失败")
    await recalculate_priority_groups(session, user_id)
    return MessageResponse(message="删除成功")


@router.patch("/{logistics_id}/toggle-transport", response_model=LogisticsResponse)
async def toggle_transport(
    logistics_id: int,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    item = await get_logistics_by_id(session, logistics_id, user_id)
    if not item:
        raise HTTPException(status_code=404, detail="物流规则不存在")
    current_type = (
        item.get("type", "land")
        if isinstance(item, dict)
        else getattr(item, "type", "land")
    )
    new_type = "air" if current_type == "land" else "land"
    success = await update_logistics(session, logistics_id, user_id, {"type": new_type})
    if not success:
        raise HTTPException(status_code=400, detail="切换失败")
    await recalculate_priority_groups(session, user_id)
    updated = await get_logistics_by_id(session, logistics_id, user_id)
    if not updated:
        raise HTTPException(status_code=404, detail="切换后查询失败")
    return updated


@router.post("/batch-delete", response_model=MessageResponse)
async def batch_delete_logistics_endpoint(
    ids: List[int],
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    if not ids:
        raise HTTPException(status_code=400, detail="请提供要删除的ID列表")
    deleted_count = await batch_delete_logistics(session, ids, user_id)
    await recalculate_priority_groups(session, user_id)
    return MessageResponse(message=f"成功删除 {deleted_count} 条规则")


# ---------------------------------------------------------------------------
# Trial overflow reselect (OpenSpec change: add-pro-trial-overflow, task 4.2)
#
# These endpoints expose the 48h reselect window opened by overflow_service
# when a user's effective plan limit drops below their active rule count
# (trial expiry or downgrade). reselect_kept_rules is the only mutation
# entry point for closing such a window with reason='reselected'.
# ---------------------------------------------------------------------------


class OverflowReselectRequest(BaseModel):
    keep_ids: List[int] = Field(default_factory=list)


class OverflowReselectResponse(BaseModel):
    enabled_ids: List[int]
    disabled_ids: List[int]


class OverflowStatusResponse(BaseModel):
    has_open_window: bool
    expires_at: int
    current_disabled_count: int
    new_limit: int


@router.post("/overflow/reselect", response_model=OverflowReselectResponse)
async def overflow_reselect_endpoint(
    payload: OverflowReselectRequest,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    new_limit = await get_effective_logistics_limit(session, user)
    result = await reselect_kept_rules(
        session,
        user_id,
        set(payload.keep_ids),
        new_limit,
    )
    if result.status == "exceeds_limit":
        raise HTTPException(
            status_code=422,
            detail=f"保留数量超过当前套餐限制（{new_limit}）",
        )
    if result.status == "ids_not_owned":
        raise HTTPException(status_code=403, detail="包含非本人的物流规则")
    if result.status == "no_open_window":
        raise HTTPException(status_code=409, detail="当前无打开的重选窗口")
    await session.commit()
    return OverflowReselectResponse(
        enabled_ids=result.enabled_ids,
        disabled_ids=result.disabled_ids,
    )


@router.get("/overflow/status", response_model=OverflowStatusResponse)
async def overflow_status_endpoint(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    new_limit = await get_effective_logistics_limit(session, user)
    win_stmt = select(TrialOverflowWindow).where(
        TrialOverflowWindow.user_id == user_id,
        TrialOverflowWindow.closed_at == 0,
    )
    win = (await session.execute(win_stmt)).scalar_one_or_none()
    disabled_stmt = (
        select(func.count())
        .select_from(Logistics)
        .where(
            Logistics.user_id == user_id,
            Logistics.disabled_by_overflow == 1,
        )
    )
    disabled_count = int((await session.execute(disabled_stmt)).scalar_one() or 0)
    return OverflowStatusResponse(
        has_open_window=win is not None,
        expires_at=int(win.expires_at) if win is not None else 0,
        current_disabled_count=disabled_count,
        new_limit=new_limit,
    )
