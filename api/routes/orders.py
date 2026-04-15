from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user_id
from database import get_db
from db.orders import get_user_orders

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


class OrderListResponse(BaseModel):
    orders: List[OrderResponse]
    total: int
    page: int
    page_size: int


@router.get("", response_model=OrderListResponse)
async def get_orders(
    user_id: int = Depends(get_current_user_id),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    limit: Optional[int] = Query(None, ge=1, le=1000),
    offset: Optional[int] = Query(None, ge=0),
    session: AsyncSession = Depends(get_db),
):
    effective_page = page
    effective_page_size = page_size
    if limit is not None:
        effective_page_size = limit
        effective_page = 1 if offset is None else (offset // limit) + 1

    orders_data = await get_user_orders(
        session,
        user_id,
        limit=limit or effective_page_size,
        offset=offset or 0,
        status=status,
        page=effective_page,
        page_size=effective_page_size,
    )
    orders = []
    for row in orders_data["orders"]:
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

    return OrderListResponse(
        orders=orders,
        total=orders_data["total"],
        page=effective_page,
        page_size=effective_page_size,
    )
