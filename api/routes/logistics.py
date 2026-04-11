from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List, Optional
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

router = APIRouter(prefix="/api/logistics", tags=["物流"])

OPTIONAL_LOGISTICS_FIELDS = {"delivery_method", "fbp_service_level"}


@router.get("")
async def get_logistics(
    user_id: int = Depends(get_current_user_id),
    limit: int = Query(100, ge=1, le=1000),
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
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    item = await get_logistics_by_id(session, logistics_id, user_id)
    if not item:
        raise HTTPException(status_code=404, detail="物流规则不存在")
    return item


@router.post("", response_model=LogisticsResponse, status_code=status.HTTP_201_CREATED)
async def create_logistics_endpoint(
    logistics: LogisticsCreate,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
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
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
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
