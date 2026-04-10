from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def get_commission_rate(
    price_rub: float,
    category_id: Optional[int],
    fulfillment_type: str,
    db_session: AsyncSession,
) -> Optional[float]:
    if category_id is None:
        return None

    from models.commission_category import CommissionCategory

    result = await db_session.execute(
        select(CommissionCategory).where(
            CommissionCategory.id == category_id,
            CommissionCategory.is_active == 1,
        )
    )
    category = result.scalar_one_or_none()
    if category is None:
        return None

    if price_rub <= 1500:
        rate_value = category.fbp_tier1_rate
    elif price_rub <= 5000:
        rate_value = category.fbp_tier2_rate
    else:
        rate_value = category.fbp_tier3_rate

    if rate_value is None:
        return None
    fbp_rate = float(rate_value)

    if fulfillment_type == "rfbs":
        return round(fbp_rate + 0.01, 4)
    return round(fbp_rate, 4)
