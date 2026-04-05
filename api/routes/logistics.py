from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from db.logistics_crud import (
    get_logistics_list,
    get_logistics_by_id,
    create_logistics,
    update_logistics,
    delete_logistics,
    batch_delete_logistics,
)
from api.models.schemas import (
    LogisticsCreate,
    LogisticsUpdate,
    LogisticsResponse,
    MessageResponse,
)
from api.dependencies import get_current_user_id

router = APIRouter(prefix="/api/logistics", tags=["物流"])


@router.get("", response_model=List[LogisticsResponse])
async def get_logistics(
    user_id: int = Depends(get_current_user_id),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
):
    items, _ = await get_logistics_list(session, user_id, limit=limit, offset=offset)
    return items


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
    for key in ["allow_battery", "allow_liquid", "require_msds", "is_active"]:
        if key in data and isinstance(data[key], bool):
            data[key] = 1 if data[key] else 0
    new_id = await create_logistics(session, user_id, data)
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
        "price_limit",
        "price_limit_rub",
        "price_min",
        "price_min_rub",
        "base_fee",
        "min_weight",
        "max_weight",
        "max_sum_of_sides",
        "max_longest_side",
        "max_second_side",
        "min_second_side",
        "min_length",
        "max_cylinder_sum",
        "min_cylinder_sum",
        "max_cylinder_length",
        "min_cylinder_length",
        "volume_mode",
        "longest_side_threshold",
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
        "price_limit_currency",
        "price_min_currency",
        "is_active",
    }

    update_data = logistics.model_dump(exclude_unset=True)
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
    return MessageResponse(message="删除成功")


@router.post("/batch-delete", response_model=MessageResponse)
async def batch_delete_logistics_endpoint(
    ids: List[int],
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    if not ids:
        raise HTTPException(status_code=400, detail="请提供要删除的ID列表")
    deleted_count = await batch_delete_logistics(session, ids, user_id)
    return MessageResponse(message=f"成功删除 {deleted_count} 条规则")
