from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.order import PaymentOrder


async def get_user_orders(
    session: AsyncSession,
    user_id: int,
    limit: int = 100,
    offset: int = 0,
):
    stmt = (
        select(PaymentOrder)
        .where(PaymentOrder.user_id == user_id)
        .order_by(PaymentOrder.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "order_id": r.order_id,
            "order_type": r.order_type,
            "amount": float(r.amount) if r.amount else 0,
            "status": r.status,
            "created_at": str(r.created_at) if r.created_at else "",
            "updated_at": str(r.updated_at) if r.updated_at else None,
        }
        for r in rows
    ]
