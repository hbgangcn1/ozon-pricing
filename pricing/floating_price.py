from decimal import Decimal
from typing import Tuple

__all__ = ["calc_floating_price", "_get_filter_rates"]


def _normalize_rate(value):
    if value >= 1:
        return value / 100
    return value


def calc_floating_price(
    cost_input: Decimal,
    target_margin_input: Decimal,
    promotion_rate_input: Decimal,
    commission_rate_input: Decimal,
    withdrawal_rate_input: Decimal,
    payment_rate_input: Decimal,
    vat_rate_input: Decimal,
    rate_input: Decimal,
    max_iter: int = 3,
) -> Tuple[Decimal, Decimal, Decimal, bool]:
    commission_fee = Decimal("15") * rate_input
    payment_fee_fixed = Decimal("10") * rate_input
    use_fixed_payment = payment_rate_input > 0
    price = Decimal("0")
    price_rub = Decimal("0")

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
        if price_denominator <= 0:
            raise ValueError(
                f"定价分母不合法 ({price_denominator:.4f})，"
                "请检查费率配置（各费率之和不得 >= 1）"
            )
        if rate_input <= 0:
            raise ValueError("汇率不合法，rate_input 必须大于 0")
        price = calc_total_cost / price_denominator
        price_rub = price / rate_input
        new_commission_rub = max(
            Decimal("15"),
            min(Decimal("200"), price_rub * Decimal("0.02")),
        )
        new_commission_fee = new_commission_rub * rate_input
        if payment_rate_input > 0:
            payment_by_rate = price_rub * payment_rate_input
            if payment_by_rate < Decimal("10"):
                use_fixed_payment = True
                payment_fee_fixed = Decimal("10") * rate_input
            else:
                use_fixed_payment = False
        if abs(new_commission_fee - commission_fee) < Decimal("0.001"):
            break
        commission_fee = new_commission_fee

    actual_payment_rub = (
        Decimal("10") if use_fixed_payment else price_rub * payment_rate_input
    )
    commission_rub = commission_fee / rate_input if rate_input > 0 else Decimal("0")
    return (
        price,
        commission_rub,
        actual_payment_rub,
        use_fixed_payment,
    )


def _get_filter_rates(product_dict):
    target_margin = product_dict.get("target_profit_margin", Decimal("0.2"))
    promotion_rate = product_dict.get("promotion_cost_rate", Decimal("0"))
    commission_rate = product_dict.get("commission_rate", Decimal("0.08"))
    withdrawal_rate = product_dict.get("withdrawal_fee_rate", Decimal("0.02"))
    payment_rate = product_dict.get("payment_processing_fee", Decimal("0"))
    return_rate = product_dict.get("return_rate", Decimal("0"))
    vat_rate = product_dict.get("vat_rate", Decimal("0"))
    target_margin = _normalize_rate(target_margin)
    promotion_rate = _normalize_rate(promotion_rate)
    commission_rate = _normalize_rate(commission_rate)
    withdrawal_rate = _normalize_rate(withdrawal_rate)
    payment_rate = _normalize_rate(payment_rate)
    return_rate = _normalize_rate(return_rate)
    vat_rate = _normalize_rate(vat_rate)
    return (
        target_margin,
        promotion_rate,
        commission_rate,
        withdrawal_rate,
        payment_rate,
        return_rate,
        vat_rate,
    )
