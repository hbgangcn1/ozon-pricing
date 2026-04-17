from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

_Q4 = Decimal("0.0001")


async def get_commission_rate(
    price_rub: Decimal,
    category_id: Optional[int],
    fulfillment_type: str,
    db_session: AsyncSession,
    user_id: Optional[int] = None,
) -> Optional[Decimal]:
    if category_id is None:
        return None

    from models.commission_category import CommissionCategory

    conditions = [
        CommissionCategory.id == category_id,
        CommissionCategory.is_active == 1,
    ]
    if user_id is not None:
        conditions.append(CommissionCategory.user_id == user_id)

    result = await db_session.execute(select(CommissionCategory).where(*conditions))
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
    fbp_rate = rate_value

    if fulfillment_type == "rfbs":
        return (fbp_rate + Decimal("0.01")).quantize(_Q4, rounding=ROUND_HALF_UP)
    return fbp_rate.quantize(_Q4, rounding=ROUND_HALF_UP)


async def fetch_commission_category(
    category_id: Optional[int],
    db_session: AsyncSession,
    user_id: Optional[int] = None,
) -> Optional[dict]:
    """从DB查出commission_category记录，返回dict或None。"""
    if category_id is None:
        return None

    from models.commission_category import CommissionCategory

    conditions = [
        CommissionCategory.id == category_id,
        CommissionCategory.is_active == 1,
    ]
    if user_id is not None:
        conditions.append(CommissionCategory.user_id == user_id)

    result = await db_session.execute(select(CommissionCategory).where(*conditions))
    row = result.scalar_one_or_none()
    if row is None:
        return None
    return {
        "rfbs_tier1_rate": row.rfbs_tier1_rate or Decimal("0"),
        "rfbs_tier2_rate": row.rfbs_tier2_rate or Decimal("0"),
        "rfbs_tier3_rate": row.rfbs_tier3_rate or Decimal("0"),
        "fbp_tier1_rate": row.fbp_tier1_rate or Decimal("0"),
        "fbp_tier2_rate": row.fbp_tier2_rate or Decimal("0"),
        "fbp_tier3_rate": row.fbp_tier3_rate or Decimal("0"),
    }


def select_commission_rate_from_category(
    category: dict,
    fulfillment_type: str,
    price_rub: Decimal,
) -> Decimal:
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
    return category.get(f"{prefix}_{tier}_rate", Decimal("0"))
