from fastapi import APIRouter, Depends, HTTPException, status
from typing import List

from db_utils import get_db_connection, _safe_adapt_sql
from api.models.schemas import (
    LogisticsCreate,
    LogisticsUpdate,
    LogisticsResponse,
    MessageResponse,
)
from api.dependencies import get_current_user_id

router = APIRouter(prefix="/api/logistics", tags=["物流"])


@router.get("", response_model=List[LogisticsResponse])
async def get_logistics(user_id: int = Depends(get_current_user_id)):
    with get_db_connection() as (conn, c):
        sql_raw = "SELECT * FROM logistics WHERE user_id = %s"
        sql = _safe_adapt_sql(sql_raw, conn)
        c.execute(sql, (user_id,))
        columns = [desc[0] for desc in c.description]
        logistics_list = [dict(zip(columns, row)) for row in c.fetchall()]
        return logistics_list


@router.get("/{logistics_id}", response_model=LogisticsResponse)
async def get_logistics_by_id(
    logistics_id: int, user_id: int = Depends(get_current_user_id)
):
    with get_db_connection() as (conn, c):
        sql_raw = "SELECT * FROM logistics WHERE id = %s AND user_id = %s"
        sql = _safe_adapt_sql(sql_raw, conn)
        c.execute(sql, (logistics_id, user_id))
        row = c.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="物流规则不存在")
        columns = [desc[0] for desc in c.description]
        return dict(zip(columns, row))


@router.post("", response_model=LogisticsResponse, status_code=status.HTTP_201_CREATED)
async def create_logistics(
    logistics: LogisticsCreate, user_id: int = Depends(get_current_user_id)
):
    with get_db_connection() as (conn, c):
        sql_raw = """
            INSERT INTO logistics (
                user_id, name, type, min_days, max_days,
                price_limit, price_limit_rub, price_min, price_min_rub,
                base_fee, min_weight, max_weight,
                max_sum_of_sides, max_longest_side, max_second_side, min_second_side, min_length,
                max_cylinder_sum, min_cylinder_sum, max_cylinder_length, min_cylinder_length,
                volume_mode, longest_side_threshold,
                allow_battery, allow_liquid, battery_capacity_limit_wh, require_msds,
                fee_mode, first_fee, first_weight_g, continue_fee, continue_unit,
                volume_coefficient, delivery_method, priority_group,
                price_limit_currency, price_min_currency, is_active
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s
            )
        """
        sql = _safe_adapt_sql(sql_raw, conn)
        c.execute(
            sql,
            (
                user_id,
                logistics.name,
                logistics.type,
                logistics.min_days,
                logistics.max_days,
                logistics.price_limit,
                logistics.price_limit_rub,
                logistics.price_min,
                logistics.price_min_rub,
                logistics.base_fee,
                logistics.min_weight,
                logistics.max_weight,
                logistics.max_sum_of_sides,
                logistics.max_longest_side,
                logistics.max_second_side,
                logistics.min_second_side,
                logistics.min_length,
                logistics.max_cylinder_sum,
                logistics.min_cylinder_sum,
                logistics.max_cylinder_length,
                logistics.min_cylinder_length,
                logistics.volume_mode,
                logistics.longest_side_threshold,
                1 if logistics.allow_battery else 0,
                1 if logistics.allow_liquid else 0,
                logistics.battery_capacity_limit_wh,
                1 if logistics.require_msds else 0,
                logistics.fee_mode,
                logistics.first_fee,
                logistics.first_weight_g,
                logistics.continue_fee,
                logistics.continue_unit,
                logistics.volume_coefficient,
                logistics.delivery_method,
                logistics.priority_group,
                logistics.price_limit_currency,
                logistics.price_min_currency,
                1 if logistics.is_active else 0,
            ),
        )
        conn.commit()
        c.execute("SELECT lastval()")
        logistics_id = c.fetchone()[0]

        # Query the created record
        sql_raw = "SELECT * FROM logistics WHERE id = %s AND user_id = %s"
        sql = _safe_adapt_sql(sql_raw, conn)
        c.execute(sql, (logistics_id, user_id))
        row = c.fetchone()
        columns = [desc[0] for desc in c.description]
        return dict(zip(columns, row))


@router.put("/{logistics_id}", response_model=LogisticsResponse)
async def update_logistics_endpoint(
    logistics_id: int,
    logistics: LogisticsUpdate,
    user_id: int = Depends(get_current_user_id),
):
    existing = get_logistics_by_id(logistics_id, user_id)
    if not existing:
        raise HTTPException(status_code=404, detail="物流规则不存在")

    update_data = logistics.model_dump(exclude_unset=True)
    if not update_data:
        return existing

    for key in ["allow_battery", "allow_liquid", "require_msds", "is_active"]:
        if key in update_data and isinstance(update_data[key], bool):
            update_data[key] = 1 if update_data[key] else 0

    set_clause = ", ".join([f"{k} = %s" for k in update_data.keys()])
    sql_raw = f"UPDATE logistics SET {set_clause} WHERE id = %s AND user_id = %s"
    params = list(update_data.values()) + [logistics_id, user_id]

    with get_db_connection() as (conn, c):
        sql = _safe_adapt_sql(sql_raw, conn)
        c.execute(sql, params)
        conn.commit()

    return await get_logistics_by_id(logistics_id, user_id)


@router.delete("/{logistics_id}", response_model=MessageResponse)
async def delete_logistics_endpoint(
    logistics_id: int, user_id: int = Depends(get_current_user_id)
):
    with get_db_connection() as (conn, c):
        sql_raw = "DELETE FROM logistics WHERE id = %s AND user_id = %s"
        sql = _safe_adapt_sql(sql_raw, conn)
        c.execute(sql, (logistics_id, user_id))
        conn.commit()
        if c.rowcount == 0:
            raise HTTPException(status_code=404, detail="物流规则不存在或删除失败")
    return MessageResponse(message="删除成功")


@router.post("/batch-delete", response_model=MessageResponse)
async def batch_delete_logistics(
    ids: List[int], user_id: int = Depends(get_current_user_id)
):
    if not ids:
        raise HTTPException(status_code=400, detail="请提供要删除的ID列表")
    placeholders = ", ".join(["%s"] * len(ids))
    with get_db_connection() as (conn, c):
        sql_raw = f"DELETE FROM logistics WHERE id IN ({placeholders}) AND user_id = %s"
        sql = _safe_adapt_sql(sql_raw, conn)
        c.execute(sql, (*ids, user_id))
        conn.commit()
        deleted_count = c.rowcount
    return MessageResponse(message=f"成功删除 {deleted_count} 条规则")
