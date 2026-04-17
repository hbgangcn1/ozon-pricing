import logging
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.schemas import BreakdownItem, PricingComboResult, PricingResultItem
from models.logistics import Logistics

logger = logging.getLogger(__name__)

_FALLBACK_RUB_CNY_RATE: Decimal = Decimal("0.0904")
_FALLBACK_USD_CNY_RATE: Decimal = Decimal("7.2")
_ZERO: Decimal = Decimal("0")
_MONEY_PRECISION: Decimal = Decimal("0.01")
_RATE_PRECISION: Decimal = Decimal("0.0001")
_COST_PRECISION: Decimal = Decimal("0.0001")


def _to_decimal(value, default=_ZERO):
    if value is None:
        return default
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _quantize(value, precision):
    return _to_decimal(value).quantize(precision)


def _quantize_float(value, precision):
    return float(_quantize(value, precision))


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

        return _quantize(_get_rate(), _RATE_PRECISION)
    except ImportError:
        return _quantize(_FALLBACK_RUB_CNY_RATE, _RATE_PRECISION)


def get_fallback_usd_rate():
    try:
        from exchange_service import get_fallback_usd_rate as _get_rate

        return _quantize(_get_rate(), _RATE_PRECISION)
    except ImportError:
        return _quantize(_FALLBACK_USD_CNY_RATE, _RATE_PRECISION)


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
    rate = _to_decimal(rate)
    commission_rub = _to_decimal(commission_rub)
    logistics_cost_cny = _to_decimal(logistics_cost_cny)
    expected_profit = _to_decimal(expected_profit)
    unit_price_cny = _to_decimal(product.get("unit_price", _ZERO))
    labeling_fee_cny = _to_decimal(product.get("labeling_fee", _ZERO))
    shipping_fee_cny = _to_decimal(product.get("shipping_fee", _ZERO))

    agency_cny = _quantize(commission_rub * rate, _MONEY_PRECISION)

    def to_rate(val):
        decimal_val = _to_decimal(val)
        if decimal_val >= Decimal("1"):
            return decimal_val / Decimal("100")
        return decimal_val

    promotion_rate = to_rate(product.get("promotion_cost_rate", 0))
    commission_rate = to_rate(product.get("commission_rate", 0))
    withdrawal_rate = to_rate(product.get("withdrawal_fee_rate", 0))
    payment_rate = to_rate(product.get("payment_processing_fee", 0))
    return_rate = to_rate(product.get("return_rate", 0))
    vat_rate = to_rate(product.get("vat_rate", 0))

    price_cny_decimal = _to_decimal(price_cny)
    promotion_cny = _quantize(price_cny_decimal * promotion_rate, _MONEY_PRECISION)
    commission_cny = _quantize(price_cny_decimal * commission_rate, _MONEY_PRECISION)
    withdrawal_cny = _quantize(price_cny_decimal * withdrawal_rate, _MONEY_PRECISION)
    if payment_fixed:
        payment_cny = _quantize(Decimal("10") * rate, _MONEY_PRECISION)
    else:
        payment_cny = _quantize(price_cny_decimal * payment_rate, _MONEY_PRECISION)
    return_loss_cny = _quantize(price_cny_decimal * return_rate, _MONEY_PRECISION)
    vat_cny = _quantize(price_cny_decimal * vat_rate, _MONEY_PRECISION)

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
        ("运营利润", _quantize(expected_profit, _MONEY_PRECISION), "#52BE80"),
    ]
    return [
        BreakdownItem(label=label, value=_quantize(val, _MONEY_PRECISION), color=col)
        for label, val, col in items
        if abs(_to_decimal(val)) > _MONEY_PRECISION or label == "运营利润"
    ]


def format_result(res, product, rate, is_land=True):
    _unavailable = PricingResultItem(
        is_available=False,
        price_cny=_ZERO,
        price_rub=_ZERO,
        logistics_name="",
        logistics_cost=_ZERO,
        days_min=0,
        days_max=0,
        profit_cny=_ZERO,
        profit_margin_pct=_ZERO,
        priority_group="",
        pricing_mode="",
        avg_cost=_ZERO,
        saved_cost=_ZERO,
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
        "land_expected_profit" if is_land else "air_expected_profit", _ZERO
    )
    profit_margin = res.get(
        "land_profit_margin" if is_land else "air_profit_margin", _ZERO
    )
    pricing_mode = res.get("land_pricing_mode" if is_land else "air_pricing_mode", "")
    commission_rub = res.get(
        "land_commission_info" if is_land else "air_commission_info", _ZERO
    )
    payment_rub = res.get("land_payment_info" if is_land else "air_payment_info", _ZERO)
    payment_fixed = res.get(
        "land_payment_fixed" if is_land else "air_payment_fixed", False
    )
    avg_cost = res.get("avg_land_cost" if is_land else "avg_air_cost", _ZERO)
    avg_days = res.get("avg_land_days" if is_land else "avg_air_days", 0)
    saved_cost = res.get("saved_land_cost" if is_land else "saved_air_cost", _ZERO)
    saved_days = res.get("saved_land_days" if is_land else "saved_air_days", 0)

    return PricingResultItem(
        is_available=True,
        price_cny=_to_decimal(price),
        price_rub=_quantize(price / rate, _MONEY_PRECISION) if rate else _ZERO,
        logistics_name=best_log.get("name", "") if best_log else "",
        logistics_cost=_quantize(cost, _COST_PRECISION) if cost is not None else _ZERO,
        days_min=best_log.get("min_days", 0) if best_log else 0,
        days_max=best_log.get("max_days", 0) if best_log else 0,
        priority_group=best_log.get("priority_group", "") if best_log else "",
        pricing_mode=pricing_mode,
        profit_cny=_quantize(expected_profit, _MONEY_PRECISION),
        profit_margin_pct=_quantize(profit_margin, _MONEY_PRECISION),
        avg_cost=_quantize(avg_cost, _COST_PRECISION)
        if avg_cost is not None
        else _ZERO,
        saved_cost=_quantize(saved_cost, _COST_PRECISION)
        if saved_cost is not None
        else _ZERO,
        avg_days=_quantize_float(avg_days, _MONEY_PRECISION)
        if avg_days is not None
        else 0,
        saved_days=_quantize_float(saved_days, _MONEY_PRECISION)
        if saved_days is not None
        else 0,
        is_smart=best_log.get("is_smart", 0) if best_log else 0,
        breakdown=build_breakdown(
            product,
            _ZERO if cost is None else cost,
            price,
            _ZERO if commission_rub is None else commission_rub,
            _ZERO if payment_rub is None else payment_rub,
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
