from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from db.orders import get_user_orders
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
async def get_orders(
    user_id: int = Depends(get_current_user_id),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
):
    orders_data = await get_user_orders(session, user_id, limit=limit, offset=offset)
    orders = []
    for row in orders_data:
        code = row.get("order_type") or ""
        orders.append(
            OrderResponse(
                id=row["id"],
                order_id=row.get("order_id") or "",
                order_type=code,
                plan_name=PLAN_NAMES.get(code, code),
                amount=row.get("amount", 0),
                status=row.get("status") or "pending",
                created_at=row.get("created_at") or "",
                updated_at=row.get("updated_at"),
            )
        )
    return orders
