from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from typing import List, Optional

from db_utils import get_db_connection, _safe_adapt_sql
from api.dependencies import get_current_user_id

router = APIRouter(prefix="/api/orders", tags=["订单"])

PLAN_NAMES = {
    "free": "免费版",
    "efficiency": "效率版",
    "professional": "专业版",
    "enterprise": "企业版",
}


class OrderResponse(BaseModel):
    id: int
    order_id: str
    order_type: str
    plan_name: str
    amount: float
    status: str
    created_at: str
    updated_at: Optional[str] = None


@router.get("", response_model=List[OrderResponse])
def get_orders(
    user_id: int = Depends(get_current_user_id),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    with get_db_connection() as (conn, c):
        sql_raw = """
            SELECT id, order_id, order_type, amount,
                   status, created_at, updated_at
            FROM payment_orders
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """
        sql = _safe_adapt_sql(sql_raw, conn)
        c.execute(sql, (user_id, limit, offset))
        orders = []
        for row in c.fetchall():
            code = row[2] or ""
            orders.append(
                OrderResponse(
                    id=row[0],
                    order_id=row[1] or "",
                    order_type=code,
                    plan_name=PLAN_NAMES.get(code, code),
                    amount=float(row[3]) if row[3] else 0,
                    status=row[4] or "pending",
                    created_at=str(row[5]) if row[5] else "",
                    updated_at=str(row[6]) if row[6] else None,
                )
            )
        return orders
