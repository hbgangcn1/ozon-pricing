import decimal
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.schemas import BreakdownItem, PricingComboResult, PricingResultItem
from models.logistics import Logistics

logger = logging.getLogger(__name__)


def convert_decimals(obj):
    if isinstance(obj, dict):
        return {k: convert_decimals(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_decimals(v) for v in obj]
    elif isinstance(obj, decimal.Decimal):
        return float(obj)
    return obj


async def get_user_logistics(session: AsyncSession, user_id, logistics_type=None):
    stmt = select(Logistics).where(
        Logistics.user_id == user_id,
        Logistics.is_active == 1,
    )
    if logistics_type:
        stmt = stmt.where(Logistics.type == logistics_type)
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [{c.key: getattr(row, c.key) for c in row.__table__.columns} for row in rows]


def get_fallback_exchange_rate():
    try:
        from exchange_service import get_fallback_exchange_rate as _get_rate

        return round(_get_rate(), 4)
    except ImportError:
        return round(0.0904, 4)


def get_fallback_usd_rate():
    try:
        from exchange_service import get_fallback_usd_rate as _get_rate

        return round(_get_rate(), 4)
    except ImportError:
        return round(7.2, 4)


def build_breakdown(
    product,
    logistics_cost_cny,
    price_cny,
    commission_rub,
    payment_rub,
    payment_fixed,
    expected_profit,
    profit_margin_pct,
    rate,
):
    unit_price_cny = product.get("unit_price", 0)
    labeling_fee_cny = product.get("labeling_fee", 0)
    shipping_fee_cny = product.get("shipping_fee", 0)

    agency_cny = round(commission_rub * rate, 2) if commission_rub is not None else 0

    def to_rate(val):
        return (
            val / 100 if (val is not None and val >= 1) else (0 if val is None else val)
        )

    promotion_rate = to_rate(product.get("promotion_cost_rate", 0))
    commission_rate = to_rate(product.get("commission_rate", 0))
    withdrawal_rate = to_rate(product.get("withdrawal_fee_rate", 0))
    payment_rate = to_rate(product.get("payment_processing_fee", 0))
    return_rate = to_rate(product.get("return_rate", 0))
    vat_rate = to_rate(product.get("vat_rate", 0))

    promotion_cny = (
        round(price_cny * promotion_rate, 2) if promotion_rate is not None else 0
    )
    commission_cny = (
        round(price_cny * commission_rate, 2) if commission_rate is not None else 0
    )
    withdrawal_cny = (
        round(price_cny * withdrawal_rate, 2) if withdrawal_rate is not None else 0
    )
    if payment_fixed:
        payment_cny = round(10 * rate, 2)
    else:
        payment_cny = (
            round(price_cny * payment_rate, 2) if payment_rate is not None else 0
        )
    return_loss_cny = (
        round(price_cny * return_rate, 2) if return_rate is not None else 0
    )
    vat_cny = round(price_cny * vat_rate, 2) if vat_rate is not None else 0

    items = [
        ("进货单价", unit_price_cny, "#FF6B6B"),
        ("贴标费用", labeling_fee_cny, "#4ECDC4"),
        ("供货运费", shipping_fee_cny, "#45B7D1"),
        ("物流运费", logistics_cost_cny, "#FFA07A"),
        ("代理费", agency_cny, "#98D8C8"),
        ("推广费", promotion_cny, "#F7DC6F"),
        ("佣金", commission_cny, "#BB8FCE"),
        ("提现费", withdrawal_cny, "#85C1E9"),
        ("收单费", payment_cny, "#F8B739"),
        ("退货损失", return_loss_cny, "#EB984E"),
        ("增值税", vat_cny, "#A569BD"),
        ("运营利润", round(expected_profit, 2), "#52BE80"),
    ]
    return [
        BreakdownItem(label=label, value=round(val, 2), color=col)
        for label, val, col in items
        if abs(val) > 0.01 or label == "运营利润"
    ]


def format_result(res, product, rate, is_land=True):
    _unavailable = PricingResultItem(
        is_available=False,
        price_cny=0,
        price_rub=0,
        logistics_name="",
        logistics_cost=0,
        days_min=0,
        days_max=0,
        profit_cny=0,
        profit_margin_pct=0,
        priority_group="",
        pricing_mode="",
        avg_cost=0,
        saved_cost=0,
        avg_days=0,
        saved_days=0,
        is_smart=0,
        breakdown=[],
    )
    if not res:
        return _unavailable

    price = res.get("land_price") if is_land else res.get("air_price")
    if price is None:
        return _unavailable

    cost = res.get("land_cost") if is_land else res.get("air_cost")
    best_log = res.get("best_land") if is_land else res.get("best_air")
    expected_profit = res.get(
        "land_expected_profit" if is_land else "air_expected_profit", 0
    )
    profit_margin = res.get("land_profit_margin" if is_land else "air_profit_margin", 0)
    pricing_mode = res.get("land_pricing_mode" if is_land else "air_pricing_mode", "")
    commission_rub = res.get(
        "land_commission_info" if is_land else "air_commission_info", 0
    )
    payment_rub = res.get("land_payment_info" if is_land else "air_payment_info", 0)
    payment_fixed = res.get(
        "land_payment_fixed" if is_land else "air_payment_fixed", False
    )
    avg_cost = res.get("avg_land_cost" if is_land else "avg_air_cost", 0)
    avg_days = res.get("avg_land_days" if is_land else "avg_air_days", 0)
    saved_cost = res.get("saved_land_cost" if is_land else "saved_air_cost", 0)
    saved_days = res.get("saved_land_days" if is_land else "saved_air_days", 0)

    return PricingResultItem(
        is_available=True,
        price_cny=price,
        price_rub=round(price / rate, 2) if rate else 0,
        logistics_name=best_log.get("name", "") if best_log else "",
        logistics_cost=round(cost, 4) if cost is not None else 0,
        days_min=best_log.get("min_days", 0) if best_log else 0,
        days_max=best_log.get("max_days", 0) if best_log else 0,
        priority_group=best_log.get("priority_group", "") if best_log else "",
        pricing_mode=pricing_mode,
        profit_cny=round(expected_profit, 2),
        profit_margin_pct=round(profit_margin, 2),
        avg_cost=round(avg_cost, 4) if avg_cost is not None else 0,
        saved_cost=round(saved_cost, 4) if saved_cost is not None else 0,
        avg_days=round(avg_days, 2) if avg_days is not None else 0,
        saved_days=round(saved_days, 2) if saved_days is not None else 0,
        is_smart=best_log.get("is_smart", 0) if best_log else 0,
        breakdown=build_breakdown(
            product,
            0 if cost is None else cost,
            price,
            0 if commission_rub is None else commission_rub,
            0 if payment_rub is None else payment_rub,
            payment_fixed,
            expected_profit,
            profit_margin,
            rate,
        ),
    )


def format_combo(combo_results):
    return PricingComboResult(
        land=combo_results.get("land", PricingResultItem()),
        air=combo_results.get("air", PricingResultItem()),
    )
