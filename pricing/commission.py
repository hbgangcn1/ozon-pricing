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


async def fetch_commission_category(
    category_id: Optional[int],
    db_session: AsyncSession,
) -> Optional[dict]:
    """从DB查出commission_category记录，返回dict或None。"""
    if category_id is None:
        return None

    from models.commission_category import CommissionCategory

    result = await db_session.execute(
        select(CommissionCategory).where(
            CommissionCategory.id == category_id,
            CommissionCategory.is_active == 1,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        return None
    return {
        "rfbs_tier1_rate": float(row.rfbs_tier1_rate or 0),
        "rfbs_tier2_rate": float(row.rfbs_tier2_rate or 0),
        "rfbs_tier3_rate": float(row.rfbs_tier3_rate or 0),
        "fbp_tier1_rate": float(row.fbp_tier1_rate or 0),
        "fbp_tier2_rate": float(row.fbp_tier2_rate or 0),
        "fbp_tier3_rate": float(row.fbp_tier3_rate or 0),
    }


def select_commission_rate_from_category(
    category: dict,
    fulfillment_type: str,
    price_rub: float,
) -> float:
    """根据fulfillment_type和price_rub从category dict选择佣金率。

    纯同步函数，无DB操作。
    """
    prefix = "rfbs" if fulfillment_type == "rfbs" else "fbp"
    if price_rub <= 1500:
        tier = "tier1"
    elif price_rub <= 5000:
        tier = "tier2"
    else:
        tier = "tier3"
    return category.get(f"{prefix}_{tier}_rate", 0)
