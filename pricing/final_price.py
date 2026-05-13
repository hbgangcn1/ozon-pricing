from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Tuple

from ._constants import CONVERGENCE_THRESHOLD, RUB_CENT
from .vat_utils import normalize_vat_to_fraction


def calc_final_commission(
    cost_input: Decimal,
    target_margin_input: Decimal,
    promotion_rate_input: Decimal,
    commission_rate_input: Decimal,
    withdrawal_rate_input: Decimal,
    payment_rate_input: Decimal,
    return_rate_input: Decimal,
    vat_rate_input: Decimal,
    rate_input: Decimal,
    max_iter: int = 5,
) -> Tuple[Decimal, Decimal, Decimal, bool]:
    commission_fee = Decimal("15") * rate_input
    payment_fee_fixed = Decimal("10") * rate_input
    use_fixed_payment = payment_rate_input > 0
    price = Decimal("0")
    price_rub = Decimal("0")

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
        if final_price_denominator <= 0:
            raise ValueError(
                f"定价分母不合法 ({final_price_denominator:.4f})，"
                "请检查费率配置（各费率之和不得 >= 1）"
            )
        if rate_input <= 0:
            raise ValueError("汇率不合法，rate_input 必须大于 0")
        price = iter_total_cost / final_price_denominator
        price_rub = price / rate_input
        new_commission_rub = max(
            Decimal("15"),
            min(Decimal("200"), price_rub * Decimal("0.02")),
        ).quantize(
            RUB_CENT,
            rounding=ROUND_HALF_UP,
        )
        new_commission_fee = new_commission_rub * rate_input
        if payment_rate_input > 0:
            payment_by_rate = price_rub * payment_rate_input
            if payment_by_rate < Decimal("10"):
                use_fixed_payment = True
                payment_fee_fixed = Decimal("10") * rate_input
            else:
                use_fixed_payment = False
        if abs(new_commission_fee - commission_fee) < CONVERGENCE_THRESHOLD:
            break
        commission_fee = new_commission_fee

    actual_payment_rub = (
        Decimal("10") if use_fixed_payment else price_rub * payment_rate_input
    )
    if rate_input > 0:
        commission_rub = (commission_fee / rate_input).quantize(
            RUB_CENT, rounding=ROUND_HALF_UP
        )
    else:
        commission_rub = Decimal("0")
    if isinstance(actual_payment_rub, Decimal):
        actual_payment_rub = actual_payment_rub.quantize(
            RUB_CENT, rounding=ROUND_HALF_UP
        )
    return (
        price,
        commission_rub,
        actual_payment_rub,
        use_fixed_payment,
    )


def _get_final_rates(product):
    final_target_margin = _to_decimal(
        product.get("target_profit_margin", Decimal("0.2"))
    )
    final_promotion_rate = _to_decimal(
        product.get("promotion_cost_rate", Decimal("0"))
    )
    final_commission_rate = _to_decimal(
        product.get("commission_rate", Decimal("0.08"))
    )
    final_withdrawal_rate = _to_decimal(
        product.get("withdrawal_fee_rate", Decimal("0.02"))
    )
    final_payment_rate = _to_decimal(
        product.get("payment_processing_fee", Decimal("0"))
    )
    final_return_rate = _to_decimal(product.get("return_rate", Decimal("0")))
    # [PRC-W12R2-01] VAT is normalized through the canonical helper only.
    final_vat_rate = normalize_vat_to_fraction(product.get("vat_rate", Decimal("0")))
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
    return (
        final_target_margin,
        final_promotion_rate,
        final_commission_rate,
        final_withdrawal_rate,
        final_payment_rate,
        final_return_rate,
        final_vat_rate,
    )


def _to_decimal(value):
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


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
    rounded_commission = actual_commission.quantize(
        RUB_CENT,
        rounding=ROUND_HALF_UP,
    )
    debug_list.append(f"  四舍五入后: {rounded_commission}")
    debug_list.append(f"  原值 >= 200? {actual_commission >= Decimal('200')}")
    debug_list.append(f"  四舍五入后 >= 200? {rounded_commission >= Decimal('200')}")
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
    actual_commission_rounded = actual_commission.quantize(
        RUB_CENT,
        rounding=ROUND_HALF_UP,
    )
    commission_in_num = actual_commission_rounded <= Decimal(
        "15"
    ) or actual_commission_rounded >= Decimal("200")
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
        numerator += actual_commission_rounded * rate
    else:
        denom_deductions += Decimal("0.02")
    if payment_in_num:
        numerator += final_payment_rub * rate
    else:
        denom_deductions += final_payment_rate
    denominator = 1 - denom_deductions
    return numerator, denominator, commission_in_num, payment_in_num


def _calc_final_payment(final_price_rub, final_payment_rate):
    if final_payment_rate > 0:
        final_payment_by_rate = final_price_rub * final_payment_rate
        if final_payment_by_rate < Decimal("10"):
            return Decimal("10"), True
        return final_payment_by_rate, False
    return Decimal("0"), False


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
    cost: Decimal,
    product: dict,
    unit_price: Decimal,
    labeling_fee: Decimal,
    shipping_fee: Decimal,
    rate: Decimal,
    debug_list: Optional[list] = None,
) -> Tuple[Decimal, Decimal, str, Decimal, bool]:
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
    if denominator <= 0:
        raise ValueError(
            f"最终定价分母不合法 ({denominator:.4f})，"
            "请检查费率配置（各费率之和不得 >= 1）"
        )
    final_price = numerator / denominator
    pricing_mode = ", ".join(
        [
            "代理费在分子中" if commission_in_num else "代理费在分母中",
            "收单费在分子中" if payment_in_num else "收单费在分母中",
        ]
    )
    if rate <= 0:
        raise ValueError("汇率不合法，rate 必须大于 0")
    final_price_rub = final_price / rate
    final_actual_commission = max(
        Decimal("15"),
        min(Decimal("200"), final_price_rub * Decimal("0.02")),
    ).quantize(
        RUB_CENT,
        rounding=ROUND_HALF_UP,
    )
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
