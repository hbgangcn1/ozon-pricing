def _normalize_rate(value):
    if value >= 1:
        return value / 100
    return value


def calc_floating_price(
    cost_input,
    target_margin_input,
    promotion_rate_input,
    commission_rate_input,
    withdrawal_rate_input,
    payment_rate_input,
    vat_rate_input,
    rate_input,
    max_iter=3,
):
    commission_fee = 15 * rate_input
    payment_fee_fixed = 10 * rate_input
    use_fixed_payment = payment_rate_input > 0
    price = 0
    price_rub = 0.0

    for _ in range(max_iter):
        if use_fixed_payment:
            calc_total_cost = cost_input + commission_fee + payment_fee_fixed
            price_denominator = (
                1
                - target_margin_input
                - promotion_rate_input
                - commission_rate_input
                - withdrawal_rate_input
                - vat_rate_input
            )
        else:
            calc_total_cost = cost_input + commission_fee
            price_denominator = (
                1
                - target_margin_input
                - promotion_rate_input
                - commission_rate_input
                - withdrawal_rate_input
                - payment_rate_input
                - vat_rate_input
            )
        price = calc_total_cost / price_denominator
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
        if abs(new_commission_fee - commission_fee) < 0.001:
            break
        commission_fee = new_commission_fee

    actual_payment_rub = 10.0 if use_fixed_payment else price_rub * payment_rate_input
    return (
        price,
        commission_fee / rate_input,
        actual_payment_rub,
        use_fixed_payment,
    )


def _get_filter_rates(product_dict):
    target_margin = product_dict.get("target_profit_margin", 0.2)
    promotion_rate = product_dict.get("promotion_cost_rate", 0)
    commission_rate = product_dict.get("commission_rate", 0.08)
    withdrawal_rate = product_dict.get("withdrawal_fee_rate", 0.02)
    payment_rate = product_dict.get("payment_processing_fee", 0)
    return_rate = product_dict.get("return_rate", 0)
    vat_rate = product_dict.get("vat_rate", 0)
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
    if vat_rate >= 1:
        vat_rate /= 100
    return (
        target_margin,
        promotion_rate,
        commission_rate,
        withdrawal_rate,
        payment_rate,
        return_rate,
        vat_rate,
    )
