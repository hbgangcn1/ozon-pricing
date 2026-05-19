from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.order import PaymentOrder
from models.user import User


def _order_to_dict(order: PaymentOrder) -> dict:
    return {
        "id": order.id,
        "order_id": order.order_id,
        "order_type": order.order_type,
        "amount": float(order.amount) if order.amount else 0,
        "status": order.status,
        "created_at": str(order.created_at) if order.created_at else "",
        "updated_at": str(order.updated_at) if order.updated_at else None,
    }


async def get_user_orders(
    session: AsyncSession,
    user_id: int,
    limit: int = 100,
    offset: int = 0,
    status: Optional[str] = None,
    page: Optional[int] = None,
    page_size: Optional[int] = None,
) -> dict:
    if page is not None and page_size is not None:
        page_num = page
        size = page_size
        effective_limit = size
        effective_offset = (page_num - 1) * size
    else:
        effective_limit = limit
        effective_offset = offset

    filters = [PaymentOrder.user_id == user_id]
    if status:
        filters.append(PaymentOrder.status == status)

    total = await session.scalar(select(func.count(PaymentOrder.id)).where(*filters))
    stmt = (
        select(PaymentOrder)
        .where(*filters)
        .order_by(PaymentOrder.created_at.desc(), PaymentOrder.id.desc())
        .limit(effective_limit)
        .offset(effective_offset)
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return {
        "orders": [_order_to_dict(row) for row in rows],
        "total": total or 0,
    }


async def get_all_orders(
    session: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    search: str = "",
    status: Optional[str] = None,
    date_from: Optional[int] = None,
    date_to: Optional[int] = None,
) -> dict:
    offset = (page - 1) * page_size

    filters = []
    if status:
        filters.append(PaymentOrder.status == status)
    if date_from is not None:
        filters.append(PaymentOrder.created_at >= date_from)
    if date_to is not None:
        filters.append(PaymentOrder.created_at <= date_to)

    base_query = (
        select(PaymentOrder, User.username)
        .outerjoin(User, User.id == PaymentOrder.user_id)
    )
    if filters:
        base_query = base_query.where(*filters)
    if search:
        keyword = f"%{search.strip()}%"
        search_filter = func.coalesce(User.username, "").ilike(keyword) | PaymentOrder.order_id.ilike(keyword)
        base_query = base_query.where(search_filter)

    count_stmt = select(func.count()).select_from(base_query.subquery())
    total = await session.scalar(count_stmt) or 0

    stmt = (
        base_query
        .order_by(PaymentOrder.created_at.desc(), PaymentOrder.id.desc())
        .limit(page_size)
        .offset(offset)
    )
    result = await session.execute(stmt)
    rows = result.all()

    orders = []
    for order, username in rows:
        orders.append({
            "order_id": order.order_id,
            "username": username or "",
            "amount": float(order.amount) if order.amount else 0,
            "order_type": order.order_type or "",
            "status": order.status or "",
            "created_at": str(order.created_at) if order.created_at else "",
        })

    return {
        "orders": orders,
        "total": total,
    }
