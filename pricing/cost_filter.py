from .logistic_cost import calculate_logistic_cost
from .filter import _debug_filter_reason
from .floating_price import calc_floating_price, _get_filter_rates


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


def _check_price_upper(log_dict, rough, rate, usd_rate):
    log_limit_currency = log_dict.get("price_limit_currency", "RUB")
    if log_limit_currency == "RUB":
        log_limit_value = float(log_dict.get("price_limit_rub") or 0)
    else:
        log_limit_value = float(log_dict.get("price_limit") or 0)
    if log_limit_currency == "USD" and log_limit_value > 0:
        rough_usd = rough / usd_rate
        if rough_usd > log_limit_value:
            return (
                f"估算售价 {rough_usd:.2f} USD 超过价格上限 {log_limit_value:.2f} USD"
            )
    elif log_limit_currency == "RUB" and log_limit_value > 0:
        rough_rub = rough / rate
        if rough_rub > log_limit_value:
            return (
                f"估算售价 {rough_rub:.2f} RUB 超过价格上限 {log_limit_value:.2f} RUB"
            )
    return None


def _check_price_lower(log_dict, rough, rate, usd_rate, debug_info):
    log_min_currency = log_dict.get("price_min_currency", "RUB")
    if log_min_currency == "RUB":
        log_min_value = float(log_dict.get("price_min_rub") or 0)
    else:
        log_min_value = float(log_dict.get("price_min") or 0)
    rough_rub_dbg = rough / rate
    debug_info.append(
        f"价格下限检查: currency={log_min_currency}, "
        f"min_value={log_min_value}, "
        f"rough={rough:.2f} CNY, "
        f"rough_rub={rough_rub_dbg:.2f} RUB"
    )
    if log_min_currency == "USD" and log_min_value > 0:
        rough_usd = rough / usd_rate
        debug_info.append(f"下限 {log_min_value:.2f} USD, 估算 {rough_usd:.2f} USD")
        if rough_usd < log_min_value:
            return f"估算售价 {rough_usd:.2f} USD 低于价格下限 {log_min_value:.2f} USD"
        debug_info.append("通过价格下限检查")
    elif log_min_currency == "RUB" and log_min_value > 0:
        rough_rub = rough / rate
        debug_info.append(f"下限 {log_min_value:.2f} RUB, 估算 {rough_rub:.2f} RUB")
        if rough_rub < log_min_value:
            return f"估算售价 {rough_rub:.2f} RUB 低于价格下限 {log_min_value:.2f} RUB"
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
    usd_rate,
    is_land,
    filtered_logistics,
    all_costs_debug,
):
    cost, debug_info = cached_cost(tuple(log_dict.items()), tuple(product_dict.items()))
    all_costs_debug.append({"logistic": log_dict, "cost": cost, "debug": debug_info})
    if cost is None:
        reason = _debug_filter_reason(log_dict, product_dict)
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
        + vat_rate
    )
    if commission_in_numerator:
        numerator += actual_commission * rate
    else:
        denom_deductions += 0.02
    if payment_in_numerator:
        numerator += actual_payment_rub * rate
    else:
        denom_deductions += payment_rate
    denominator = 1 - denom_deductions
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
    log_limit_currency = log_dict.get("price_limit_currency", "RUB")
    if log_limit_currency == "USD" and float(log_dict.get("price_limit") or 0) > 0:
        rough_usd = rough / usd_rate
        debug_info.append(
            f"限价判断: 估算售价 {rough_usd:.2f} USD, "
            f"上限 {float(log_dict.get('price_limit') or 0):.2f} USD"
        )
    err = _check_price_upper(log_dict, rough, rate, usd_rate)
    if err:
        debug_info.append("超价格上限，跳过")
        _append_filtered(filtered_logistics, is_land, log_dict, err)
        return None
    err = _check_price_lower(log_dict, rough, rate, usd_rate, debug_info)
    if err:
        debug_info.append("低于价格下限，跳过")
        _append_filtered(filtered_logistics, is_land, log_dict, err)
        return None
    return (log_dict, cost)


def cost_and_filter(
    logistics,
    product,
    land_logistics,
    cached_cost,
    unit_price,
    labeling_fee,
    shipping_fee,
    rate,
    usd_rate,
    filtered_logistics,
    all_costs_debug,
):
    res = []
    product_dict = _to_product_dict(product)
    is_land = logistics is land_logistics
    for _, log in _iter_logistics(logistics):
        log_dict = _to_log_dict(log)
        result = _process_one_logistic(
            log_dict,
            product_dict,
            cached_cost,
            unit_price,
            labeling_fee,
            shipping_fee,
            rate,
            usd_rate,
            is_land,
            filtered_logistics,
            all_costs_debug,
        )
        if result is not None:
            res.append(result)
    return res
