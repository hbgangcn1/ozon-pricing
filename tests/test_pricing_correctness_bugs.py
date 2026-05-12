from decimal import Decimal

import pytest

from pricing import logistic_cost
from pricing.final_price import calc_final_commission
from pricing.grouped_pricing import _estimate_price_rub  # pyright: ignore[reportPrivateUsage]


def test_grouped_estimate_price_rejects_non_positive_denominator(monkeypatch):
    monkeypatch.setattr(
        "pricing.grouped_pricing._get_exchange_rates",
        lambda: (Decimal("0.09"), Decimal("7.2")),
    )
    product = {
        "unit_price": Decimal("100"),
        "labeling_fee": Decimal("0"),
        "shipping_fee": Decimal("0"),
        "target_profit_margin": Decimal("0.95"),
    }

    with pytest.raises(ValueError, match="定价分母不合法"):
        _estimate_price_rub(product)


def test_final_commission_rub_is_quantized_to_cents():
    _price, commission_rub, _payment_rub, _fixed = calc_final_commission(
        cost_input=Decimal("500.123456789"),
        target_margin_input=Decimal("0"),
        promotion_rate_input=Decimal("0"),
        commission_rate_input=Decimal("0"),
        withdrawal_rate_input=Decimal("0"),
        payment_rate_input=Decimal("0"),
        return_rate_input=Decimal("0"),
        vat_rate_input=Decimal("0"),
        rate_input=Decimal("0.09"),
        max_iter=5,
    )

    assert commission_rub.as_tuple().exponent == -2


def test_cylinder_sides_from_limit_check_are_reused(monkeypatch):
    def fake_check(_logistic, _product, debug_info, _is_fast_mode):
        debug_info.append("fake cylinder sides")
        return [Decimal("5"), Decimal("6"), Decimal("7")]

    monkeypatch.setattr(logistic_cost, "_check_cylinder_limits", fake_check)
    logistic = {
        "min_weight": 0,
        "max_weight": 10000,
        "max_sum_of_sides": Decimal("100"),
        "max_longest_side": Decimal("100"),
        "fee_mode": "base_plus_continue",
        "continue_unit": 100,
        "continue_fee": Decimal("1"),
        "base_fee": Decimal("2"),
        "volume_mode": "none",
        "allow_battery": True,
        "allow_liquid": True,
    }
    product = {
        "weight_g": Decimal("100"),
        "is_cylinder": True,
        "cylinder_diameter": Decimal("999"),
        "cylinder_length": Decimal("999"),
    }

    cost, debug = logistic_cost.calculate_logistic_cost(logistic, product)

    assert cost == Decimal("3")
    assert any("三边: [Decimal('5'), Decimal('6'), Decimal('7')]" in line for line in debug)
