from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from typing import List

from db_utils import get_db_connection, _safe_adapt_sql
from api.models.schemas import (
    LogisticsCreate,
    LogisticsUpdate,
    LogisticsResponse,
    MessageResponse,
)

router = APIRouter(prefix="/api/logistics", tags=["物流"])
security = HTTPBearer()


def get_current_user_id(api_key: str = Depends(security)) -> int:
    return 1


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
                user_id, name, type, min_days, max_days, price_limit,
                base_fee, weight_factor, min_weight, max_weight,
                max_sum_of_sides, max_longest_side, volume_mode
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                logistics.base_fee,
                logistics.weight_factor,
                logistics.min_weight,
                logistics.max_weight,
                logistics.max_sum_of_sides,
                logistics.max_longest_side,
                logistics.volume_mode,
            ),
        )
        conn.commit()
        c.execute("SELECT lastval()")
        logistics_id = c.fetchone()[0]
        return get_logistics_by_id(logistics_id, user_id)


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

    set_clause = ", ".join([f"{k} = %s" for k in update_data.keys()])
    sql_raw = f"UPDATE logistics SET {set_clause} WHERE id = %s AND user_id = %s"
    params = list(update_data.values()) + [logistics_id, user_id]

    with get_db_connection() as (conn, c):
        sql = _safe_adapt_sql(sql_raw, conn)
        c.execute(sql, params)
        conn.commit()

    return get_logistics_by_id(logistics_id, user_id)


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
