from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.order import PaymentOrder


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
