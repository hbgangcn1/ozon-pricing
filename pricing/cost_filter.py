from decimal import Decimal
from typing import Any, Callable, List, Tuple

from .filter import _debug_filter_reason  # pyright: ignore[reportPrivateUsage]
from .floating_price import calc_floating_price, _get_filter_rates  # pyright: ignore[reportPrivateUsage]


def _to_product_dict(product):
    if hasattr(product, "to_dict"):
        return product.to_dict()
    if isinstance(product, dict):
        return product
    if hasattr(product, "items"):
        product.get("test")
        return dict(product)
    product.get("test")
    raise AttributeError(f"对象 {type(product)} 没有 items() 方法")


def _iter_logistics(logistics):
    if hasattr(logistics, "empty"):
        if logistics.empty:
            return []
        return list(logistics.iterrows())
    if not logistics:
        return []
    return list(enumerate(logistics))


def _to_log_dict(log):
    if hasattr(log, "to_dict"):
        return log.to_dict()
    if hasattr(log, "items"):
        return dict(log)
    return log


def _check_price_upper(log_dict, rough):
    log_limit_value = _to_decimal(log_dict.get("price_limit_cny") or Decimal("0"))
    if log_limit_value > 0 and rough > log_limit_value:
        return f"估算售价 {rough:.2f} CNY 超过价格上限 {log_limit_value:.2f} CNY"
    return None


def _check_price_lower(log_dict, rough, debug_info):
    log_min_value = _to_decimal(log_dict.get("price_min_cny") or Decimal("0"))
    debug_info.append(
        f"价格下限检查: min_value={log_min_value:.2f} CNY, rough={rough:.2f} CNY"
    )
    if log_min_value > 0:
        debug_info.append(f"下限 {log_min_value:.2f} CNY, 估算 {rough:.2f} CNY")
        if rough < log_min_value:
            return f"估算售价 {rough:.2f} CNY 低于价格下限 {log_min_value:.2f} CNY"
        debug_info.append("通过价格下限检查")
    else:
        debug_info.append(f"无价格下限 (min_value={log_min_value})")
    return None


def _append_filtered(filtered_logistics, is_land, log_dict, reason):
    entry = {"name": log_dict.get("name", ""), "reason": reason}
    if is_land:
        filtered_logistics["land"].append(entry)
    else:
        filtered_logistics["air"].append(entry)


def _process_one_logistic(
    log_dict,
    product_dict,
    cached_cost,
    unit_price,
    labeling_fee,
    shipping_fee,
    rate,
    is_land,
    filtered_logistics,
    all_costs_debug,
):
    cost, debug_info = cached_cost(tuple(log_dict.items()), tuple(product_dict.items()))
    all_costs_debug.append({"logistic": log_dict, "cost": cost, "debug": debug_info})
    if cost is None:
        reason = _debug_filter_reason(log_dict, product_dict) or "未识别的淘汰原因"
        _append_filtered(filtered_logistics, is_land, log_dict, reason)
        return None
    base_cost_calc = unit_price + labeling_fee + shipping_fee + cost
    (
        target_margin,
        promotion_rate,
        commission_rate,
        withdrawal_rate,
        payment_rate,
        return_rate,
        vat_rate,
    ) = _get_filter_rates(product_dict)
    (rough, actual_commission, actual_payment_rub, fixed_payment) = calc_floating_price(
        base_cost_calc,
        target_margin,
        promotion_rate,
        commission_rate,
        withdrawal_rate,
        payment_rate,
        vat_rate,
        rate,
    )
    commission_in_numerator = actual_commission <= 15 or actual_commission >= 200
    payment_in_numerator = fixed_payment
    numerator = base_cost_calc
    denom_deductions = (
        target_margin
        + promotion_rate
        + commission_rate
        + withdrawal_rate
        + return_rate
        + vat_rate  # [PRC-W12R2-01] Already normalized by _get_filter_rates.
    )
    if commission_in_numerator:
        numerator += actual_commission * rate
    else:
        denom_deductions += Decimal("0.02")
    if payment_in_numerator:
        numerator += actual_payment_rub * rate
    else:
        denom_deductions += payment_rate
    denominator = Decimal("1") - denom_deductions
    if denominator <= 0:
        debug_info.append(f"定价分母不合法 ({denominator:.4f})，跳过此物流方案")
        _append_filtered(
            filtered_logistics,
            is_land,
            log_dict,
            f"费率配置异常，定价分母={denominator:.4f}",
        )
        return None
    rough = numerator / denominator
    pricing_parts = []
    pricing_parts.append(
        "代理费在分子中" if commission_in_numerator else "代理费在分母中"
    )
    pricing_parts.append("收单费在分子中" if payment_in_numerator else "收单费在分母中")
    pricing_mode = ", ".join(pricing_parts)
    debug_info.append(f"浮动代理费: {actual_commission:.2f} RUB")
    debug_info.append(
        f"浮动收单费: {actual_payment_rub:.2f} RUB"
        f"{' (固定下限)' if fixed_payment else ' (按比例)'}"
    )
    debug_info.append(f"定价模式: {pricing_mode}")
    debug_info.append(f"估算价格: {rough:.2f} CNY")
    log_limit_value = log_dict.get("price_limit_cny") or Decimal("0")
    if log_limit_value > 0:
        debug_info.append(
            f"限价判断: 估算售价 {rough:.2f} CNY, 上限 {log_limit_value:.2f} CNY"
        )
    err = _check_price_upper(log_dict, rough)
    if err:
        debug_info.append("超价格上限，跳过")
        _append_filtered(filtered_logistics, is_land, log_dict, err)
        return None
    err = _check_price_lower(log_dict, rough, debug_info)
    if err:
        debug_info.append("低于价格下限，跳过")
        _append_filtered(filtered_logistics, is_land, log_dict, err)
        return None
    return (log_dict, cost)


def _to_decimal(value):
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def cost_and_filter(
    logistics: Any,
    product: Any,
    land_logistics: Any,
    cached_cost: Callable,
    unit_price: Decimal,
    labeling_fee: Decimal,
    shipping_fee: Decimal,
    rate: Decimal,
    filtered_logistics: dict,
    all_costs_debug: list,
) -> List[Tuple[dict, Decimal]]:
    res = []
    product_dict = _to_product_dict(product)
    is_land = logistics is land_logistics
    candidates = _iter_logistics(logistics)
    if not candidates:
        return []
    for _, log in candidates:
        log_dict = _to_log_dict(log)
        result = _process_one_logistic(
            log_dict,
            product_dict,
            cached_cost,
            unit_price,
            labeling_fee,
            shipping_fee,
            rate,
            is_land,
            filtered_logistics,
            all_costs_debug,
        )
        if result is not None:
            res.append(result)
    return res
