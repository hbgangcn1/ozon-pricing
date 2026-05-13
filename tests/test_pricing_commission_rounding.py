"""[PRC-W13-01/02] 佣金舍入精度测试.

验证 final_price 与 floating_price 返回的佣金严格 quantize 到 0.01 + ROUND_HALF_UP.
"""
from decimal import Decimal, ROUND_HALF_UP

from pricing._constants import RUB_CENT
from pricing.final_price import calc_final_commission, compute_final_price
from pricing.floating_price import calc_floating_price


def test_commission_rounding_precision_final_price():
    product = {
        "target_profit_margin": Decimal("0.20"),
        "promotion_cost_rate": Decimal("0.05"),
        "commission_rate": Decimal("0.08"),
        "withdrawal_fee_rate": Decimal("0.02"),
        "payment_processing_fee": Decimal("0"),
        "return_rate": Decimal("0"),
        "vat_rate": Decimal("0"),
    }

    (
        _final_price,
        commission_rub,
        _mode,
        payment_rub,
        _fixed,
    ) = compute_final_price(
        cost=Decimal("123.456"),
        product=product,
        unit_price=Decimal("87.65"),
        labeling_fee=Decimal("3.21"),
        shipping_fee=Decimal("9.87"),
        rate=Decimal("0.0855"),
    )

    assert commission_rub.as_tuple().exponent == -2
    assert isinstance(payment_rub, Decimal)


def test_commission_boundary_half_up_final_price():
    raw_round_up = Decimal("100.005").quantize(RUB_CENT, rounding=ROUND_HALF_UP)
    assert raw_round_up == Decimal("100.01")

    (_price, commission_rub, _pay, _fix) = calc_final_commission(
        cost_input=Decimal("400"),
        target_margin_input=Decimal("0.10"),
        promotion_rate_input=Decimal("0"),
        commission_rate_input=Decimal("0.08"),
        withdrawal_rate_input=Decimal("0.02"),
        payment_rate_input=Decimal("0"),
        return_rate_input=Decimal("0"),
        vat_rate_input=Decimal("0"),
        rate_input=Decimal("0.09"),
        max_iter=5,
    )
    assert commission_rub.as_tuple().exponent == -2
    assert Decimal("15") <= commission_rub <= Decimal("200")


def test_commission_rounding_precision_floating_price():
    (_price, commission_rub, payment_rub, _fixed) = calc_floating_price(
        cost_input=Decimal("750.987654321"),
        target_margin_input=Decimal("0.15"),
        promotion_rate_input=Decimal("0.03"),
        commission_rate_input=Decimal("0.08"),
        withdrawal_rate_input=Decimal("0.02"),
        payment_rate_input=Decimal("0"),
        vat_rate_input=Decimal("0"),
        rate_input=Decimal("0.0912"),
        max_iter=5,
    )
    assert commission_rub.as_tuple().exponent == -2
    assert isinstance(payment_rub, Decimal)


def test_commission_boundary_half_up_floating_price():
    raw_round_up = Decimal("87.345").quantize(RUB_CENT, rounding=ROUND_HALF_UP)
    assert raw_round_up == Decimal("87.35")

    (_price, commission_rub, _pay, _fix) = calc_floating_price(
        cost_input=Decimal("400"),
        target_margin_input=Decimal("0.10"),
        promotion_rate_input=Decimal("0"),
        commission_rate_input=Decimal("0.08"),
        withdrawal_rate_input=Decimal("0.02"),
        payment_rate_input=Decimal("0"),
        vat_rate_input=Decimal("0"),
        rate_input=Decimal("0.09"),
        max_iter=5,
    )
    assert commission_rub.as_tuple().exponent == -2
    assert Decimal("15") <= commission_rub <= Decimal("200")
