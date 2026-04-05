def _get_profit_rates(product):
    target_margin = product.get("target_profit_margin", 0.2)
    promotion_rate = product.get("promotion_cost_rate", 0)
    commission_rate = product.get("commission_rate", 0.08)
    withdrawal_rate = product.get("withdrawal_fee_rate", 0.02)
    payment_rate = product.get("payment_processing_fee", 0)
    return_rate = product.get("return_rate", 0)
    vat_rate = product.get("vat_rate", 0)
    if target_margin >= 1:
        target_margin /= 100
    if promotion_rate >= 1:
        promotion_rate /= 100
    if commission_rate >= 1:
        commission_rate /= 100
    if withdrawal_rate >= 1:
        withdrawal_rate /= 100
    if payment_rate >= 1:
        payment_rate /= 100
    if return_rate >= 1:
        return_rate /= 100
    return (
        target_margin,
        promotion_rate,
        commission_rate,
        withdrawal_rate,
        payment_rate,
        return_rate,
        vat_rate,
    )


def _append_profit_debug(
    debug_list,
    label,
    base_cost,
    commission_fee,
    actual_commission,
    payment_fee,
    actual_payment,
    payment_fixed,
    pricing_mode,
    total_cost,
    price,
    promotion_rate,
    commission_rate,
    withdrawal_rate,
    payment_rate,
    return_rate,
    vat_rate,
    revenue_deductions,
    expected_profit,
    profit_margin,
    target_margin,
):
    debug_list.append(f"{label}预期利润计算:")
    debug_list.append(f"  产品成本: {base_cost[0]}")
    debug_list.append(f"  贴标费: {base_cost[1]}")
    debug_list.append(f"  运费: {base_cost[2]}")
    debug_list.append(f"  {label}物流成本: {base_cost[3]}")
    base_total = sum(base_cost)
    debug_list.append(f"  {label}基础总成本: {base_total}")
    debug_list.append(
        f"  {label}代理费: {commission_fee:.2f} ({actual_commission:.2f} RUB)"
    )
    debug_list.append(
        f"  {label}收单费: {payment_fee:.2f} ({actual_payment:.2f} RUB)"
        f"{' (固定下限)' if payment_fixed else ' (按比例)'}"
    )
    debug_list.append(f"  定价模式: {pricing_mode}")
    debug_list.append(f"  {label}总成本(用于利润计算): {total_cost}")
    debug_list.append(f"  {label}售价: {price}")
    debug_list.append("  实际收入计算:")
    debug_list.append(f"    售价: {price:.2f}")
    debug_list.append(f"    推广费率: -{promotion_rate * 100:.2f}%")
    debug_list.append(f"    佣金率: -{commission_rate * 100:.2f}%")
    debug_list.append(f"    提现费率: -{withdrawal_rate * 100:.2f}%")
    if payment_fixed:
        debug_list.append(f"    收单费: {actual_payment:.2f} RUB (固定，在分子中)")
    else:
        debug_list.append(f"    收单费率: -{payment_rate * 100:.2f}%")
    debug_list.append(f"    退货率: -{return_rate * 100:.2f}%")
    debug_list.append(f"    增值税率: -{vat_rate * 100:.2f}%")
    if "代理费在分母中" in pricing_mode:
        debug_list.append("    代理费率: -2.00%")
    revenue_factor = 1 - revenue_deductions
    debug_list.append(f"    收入系数: {revenue_factor:.4f}")
    debug_list.append(
        f"    实际收入: {price:.2f} × {revenue_factor:.4f} = "
        f"{price * revenue_factor:.2f}"
    )
    debug_list.append(f"  {label}预期利润: {expected_profit:.2f} CNY")
    debug_list.append(f"  {label}利润率: {profit_margin:.2f}%")
    debug_list.append(f"  目标利润率: {target_margin * 100:.2f}%")
    debug_list.append(f"  利润率差异: {profit_margin - target_margin * 100:+.2f}%")


def calc_profit(
    price,
    cost,
    commission_info,
    payment_info,
    payment_fixed,
    pricing_mode,
    unit_price,
    labeling_fee,
    shipping_fee,
    rate,
    product,
    label,
    debug_list,
):
    (
        target_margin,
        promotion_rate,
        commission_rate,
        withdrawal_rate,
        payment_rate,
        return_rate,
        vat_rate,
    ) = _get_profit_rates(product)
    base_cost = unit_price + labeling_fee + shipping_fee + cost
    actual_commission = commission_info
    commission_fee = actual_commission * rate
    actual_payment = payment_info if payment_info is not None else 0
    payment_fee = actual_payment * rate
    total_cost = base_cost
    revenue_deductions = (
        promotion_rate + commission_rate + withdrawal_rate + return_rate + vat_rate
    )
    if "代理费在分子中" in (pricing_mode or ""):
        total_cost += commission_fee
    else:
        revenue_deductions += 0.02
    if payment_fixed:
        total_cost += payment_fee
    else:
        revenue_deductions += payment_rate
    actual_revenue = price * (1 - revenue_deductions)
    expected_profit = actual_revenue - total_cost
    profit_margin = expected_profit / price * 100 if price > 0 else 0
    _append_profit_debug(
        debug_list,
        label,
        (unit_price, labeling_fee, shipping_fee, cost),
        commission_fee,
        actual_commission,
        payment_fee,
        actual_payment,
        payment_fixed,
        pricing_mode or "",
        total_cost,
        price,
        promotion_rate,
        commission_rate,
        withdrawal_rate,
        payment_rate,
        return_rate,
        vat_rate,
        revenue_deductions,
        expected_profit,
        profit_margin,
        target_margin,
    )
    return expected_profit, profit_margin
