def calc_final_commission(
    cost_input,
    target_margin_input,
    promotion_rate_input,
    commission_rate_input,
    withdrawal_rate_input,
    payment_rate_input,
    return_rate_input,
    vat_rate_input,
    rate_input,
    max_iter=5,
):
    commission_fee = 15 * rate_input
    payment_fee_fixed = 10 * rate_input
    use_fixed_payment = payment_rate_input > 0
    price = 0
    price_rub = 0.0

    for _ in range(max_iter):
        if use_fixed_payment:
            iter_total_cost = cost_input + commission_fee + payment_fee_fixed
            final_price_denominator = (
                1
                - target_margin_input
                - promotion_rate_input
                - commission_rate_input
                - withdrawal_rate_input
                - return_rate_input
                - vat_rate_input
            )
        else:
            iter_total_cost = cost_input + commission_fee
            final_price_denominator = (
                1
                - target_margin_input
                - promotion_rate_input
                - commission_rate_input
                - withdrawal_rate_input
                - payment_rate_input
                - return_rate_input
                - vat_rate_input
            )
        price = iter_total_cost / final_price_denominator
        price_rub = price / rate_input
        new_commission_rub = max(15, min(200, price_rub * 0.02))
        new_commission_fee = new_commission_rub * rate_input
        if payment_rate_input > 0:
            payment_by_rate = price_rub * payment_rate_input
            if payment_by_rate < 10:
                use_fixed_payment = True
                payment_fee_fixed = 10 * rate_input
            else:
                use_fixed_payment = False
        if abs(new_commission_fee - commission_fee) < 0.01:
            break
        commission_fee = new_commission_fee

    actual_payment_rub = 10.0 if use_fixed_payment else price_rub * payment_rate_input
    return (
        price,
        commission_fee / rate_input,
        actual_payment_rub,
        use_fixed_payment,
    )


def _get_final_rates(product):
    final_target_margin = product.get("target_profit_margin", 0.2)
    final_promotion_rate = product.get("promotion_cost_rate", 0)
    final_commission_rate = product.get("commission_rate", 0.08)
    final_withdrawal_rate = product.get("withdrawal_fee_rate", 0.02)
    final_payment_rate = product.get("payment_processing_fee", 0)
    final_return_rate = product.get("return_rate", 0)
    final_vat_rate = product.get("vat_rate", 0)
    if final_target_margin >= 1:
        final_target_margin /= 100
    if final_promotion_rate >= 1:
        final_promotion_rate /= 100
    if final_commission_rate >= 1:
        final_commission_rate /= 100
    if final_withdrawal_rate >= 1:
        final_withdrawal_rate /= 100
    if final_payment_rate >= 1:
        final_payment_rate /= 100
    if final_return_rate >= 1:
        final_return_rate /= 100
    if final_vat_rate >= 1:
        final_vat_rate /= 100
    return (
        final_target_margin,
        final_promotion_rate,
        final_commission_rate,
        final_withdrawal_rate,
        final_payment_rate,
        final_return_rate,
        final_vat_rate,
    )


def _append_final_price_debug(
    debug_list,
    actual_commission,
    final_price,
    final_price_rub,
    final_actual_commission,
    base_cost_calc,
    commission_in_num,
    final_actual_payment_rub,
    final_fixed_payment,
    final_target_margin,
    final_promotion_rate,
    final_commission_rate,
    final_withdrawal_rate,
    final_payment_rate,
    final_return_rate,
    final_vat_rate,
    denominator,
    pricing_mode,
):
    debug_list.append(f"代理费判断: actual_commission={actual_commission:.15f}")
    debug_list.append(f"  四舍五入后: {round(actual_commission, 2)}")
    debug_list.append(f"  原值 >= 200? {actual_commission >= 200}")
    debug_list.append(f"  四舍五入后 >= 200? {round(actual_commission, 2) >= 200}")
    debug_list.append(f"迭代计算代理费: {actual_commission:.2f} RUB")
    debug_list.append(f"最终售价: {final_price:.2f} CNY")
    debug_list.append(f"最终售价(卢布): {final_price_rub:.2f} RUB")
    debug_list.append(f"最终浮动代理费: {final_actual_commission:.2f} RUB")


def _append_final_price_debug2(
    debug_list,
    final_actual_commission,
    rate,
    final_actual_payment_rub,
    final_fixed_payment,
    pricing_mode,
    base_cost_calc,
    commission_in_num,
    final_target_margin,
    final_promotion_rate,
    final_commission_rate,
    final_withdrawal_rate,
    final_payment_rate,
    final_return_rate,
    final_vat_rate,
    denominator,
    final_price,
):
    debug_list.append(f"最终代理费(CNY): {final_actual_commission * rate:.2f}")
    debug_list.append(
        f"最终收单费: {final_actual_payment_rub:.2f} RUB"
        f"{' (固定下限)' if final_fixed_payment else ' (按比例)'}"
    )
    debug_list.append(f"定价模式: {pricing_mode}")
    debug_list.append("定价公式详细参数:")
    debug_list.append(f"  基础成本: {base_cost_calc:.2f}")
    if commission_in_num:
        total_cost_display = base_cost_calc + final_actual_commission * rate
        if final_fixed_payment:
            total_cost_display += final_actual_payment_rub * rate
        debug_list.append(f"  总成本: {total_cost_display:.2f}")
    else:
        debug_list.append(f"  总成本: {base_cost_calc:.2f} (代理费在分母)")
    debug_list.append(f"  目标利润率: -{final_target_margin * 100:.2f}%")
    debug_list.append(f"  推广费率: -{final_promotion_rate * 100:.2f}%")
    debug_list.append(f"  佣金率: -{final_commission_rate * 100:.2f}%")
    debug_list.append(f"  提现费率: -{final_withdrawal_rate * 100:.2f}%")
    if final_fixed_payment:
        debug_list.append(
            f"  收单费: {final_actual_payment_rub:.2f} RUB (固定下限，在分子中)"
        )
    else:
        debug_list.append(f"  收单费率: -{final_payment_rate * 100:.2f}%")
    debug_list.append(f"  退货率: -{final_return_rate * 100:.2f}%")
    debug_list.append(f"  增值税率: -{final_vat_rate * 100:.2f}%")
    if 15 < final_actual_commission < 200:
        debug_list.append("  代理费率: -2.00%")
    debug_list.append(f"  定价分母: {denominator:.4f}")
    debug_list.append(f"  计算售价: {final_price:.2f}")


def _calc_numerator_denom(
    base_cost_calc,
    actual_commission,
    final_payment_rub,
    final_fixed_payment,
    final_target_margin,
    final_promotion_rate,
    final_commission_rate,
    final_withdrawal_rate,
    final_payment_rate,
    final_return_rate,
    final_vat_rate,
    rate,
):
    actual_commission_rounded = round(actual_commission, 2)
    commission_in_num = (
        actual_commission_rounded <= 15 or actual_commission_rounded >= 200
    )
    payment_in_num = final_fixed_payment
    numerator = base_cost_calc
    denom_deductions = (
        final_target_margin
        + final_promotion_rate
        + final_commission_rate
        + final_withdrawal_rate
        + final_return_rate
        + final_vat_rate
    )
    if commission_in_num:
        numerator += actual_commission * rate
    else:
        denom_deductions += 0.02
    if payment_in_num:
        numerator += final_payment_rub * rate
    else:
        denom_deductions += final_payment_rate
    denominator = 1 - denom_deductions
    return numerator, denominator, commission_in_num, payment_in_num


def _calc_final_payment(final_price_rub, final_payment_rate):
    if final_payment_rate > 0:
        final_payment_by_rate = final_price_rub * final_payment_rate
        if final_payment_by_rate < 10:
            return 10.0, True
        return final_payment_by_rate, False
    return 0.0, False


def _emit_debug(
    debug_list,
    actual_commission,
    final_price,
    final_price_rub,
    final_actual_commission,
    base_cost_calc,
    commission_in_num,
    final_actual_payment_rub,
    final_fixed_payment,
    rates_tuple,
    denominator,
    pricing_mode,
    rate,
):
    (
        final_target_margin,
        final_promotion_rate,
        final_commission_rate,
        final_withdrawal_rate,
        final_payment_rate,
        final_return_rate,
        final_vat_rate,
    ) = rates_tuple
    _append_final_price_debug(
        debug_list,
        actual_commission,
        final_price,
        final_price_rub,
        final_actual_commission,
        base_cost_calc,
        commission_in_num,
        final_actual_payment_rub,
        final_fixed_payment,
        final_target_margin,
        final_promotion_rate,
        final_commission_rate,
        final_withdrawal_rate,
        final_payment_rate,
        final_return_rate,
        final_vat_rate,
        denominator,
        pricing_mode,
    )
    _append_final_price_debug2(
        debug_list,
        final_actual_commission,
        rate,
        final_actual_payment_rub,
        final_fixed_payment,
        pricing_mode,
        base_cost_calc,
        commission_in_num,
        final_target_margin,
        final_promotion_rate,
        final_commission_rate,
        final_withdrawal_rate,
        final_payment_rate,
        final_return_rate,
        final_vat_rate,
        denominator,
        final_price,
    )


def compute_final_price(
    cost, product, unit_price, labeling_fee, shipping_fee, rate, debug_list=None
):
    rates = _get_final_rates(product)
    (
        final_target_margin,
        final_promotion_rate,
        final_commission_rate,
        final_withdrawal_rate,
        final_payment_rate,
        final_return_rate,
        final_vat_rate,
    ) = rates
    base_cost_calc = unit_price + labeling_fee + shipping_fee + cost
    (_, actual_commission, final_payment_rub, final_fixed_payment) = (
        calc_final_commission(
            base_cost_calc,
            final_target_margin,
            final_promotion_rate,
            final_commission_rate,
            final_withdrawal_rate,
            final_payment_rate,
            final_return_rate,
            final_vat_rate,
            rate,
        )
    )
    numerator, denominator, commission_in_num, payment_in_num = _calc_numerator_denom(
        base_cost_calc,
        actual_commission,
        final_payment_rub,
        final_fixed_payment,
        final_target_margin,
        final_promotion_rate,
        final_commission_rate,
        final_withdrawal_rate,
        final_payment_rate,
        final_return_rate,
        final_vat_rate,
        rate,
    )
    final_price = numerator / denominator
    pricing_mode = ", ".join(
        [
            "代理费在分子中" if commission_in_num else "代理费在分母中",
            "收单费在分子中" if payment_in_num else "收单费在分母中",
        ]
    )
    final_price_rub = final_price / rate
    final_actual_commission = max(15, min(200, final_price_rub * 0.02))
    final_actual_payment_rub, final_fixed_payment = _calc_final_payment(
        final_price_rub, final_payment_rate
    )
    if debug_list is not None:
        _emit_debug(
            debug_list,
            actual_commission,
            final_price,
            final_price_rub,
            final_actual_commission,
            base_cost_calc,
            commission_in_num,
            final_actual_payment_rub,
            final_fixed_payment,
            rates,
            denominator,
            pricing_mode,
            rate,
        )
    return (
        final_price,
        final_actual_commission,
        pricing_mode,
        final_actual_payment_rub,
        final_fixed_payment,
    )
