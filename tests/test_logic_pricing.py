from decimal import Decimal

import pytest
from unittest.mock import patch

from pricing import calculate_logistic_cost, calculate_pricing
from pricing.filter import _filter_check_weight  # pyright: ignore[reportPrivateUsage]
from pricing._weight import _compute_billable_weight  # pyright: ignore[reportPrivateUsage]


def test_calculate_logistic_cost_standard_package_volume_mode():
    logistic = {
        "min_weight": 0,
        "max_weight": 10**9,
        "max_sum_of_sides": 200,
        "max_longest_side": 150,
        "fee_mode": "base_plus_continue",
        "continue_unit": 100,
        "continue_fee": Decimal("0.5"),
        "base_fee": Decimal("2.0"),
        "volume_mode": "max_actual_vs_volume",
        "volume_coefficient": 5000,
    }
    product = {
        "weight_g": 100,
        "length_cm": 20,
        "width_cm": 10,
        "height_cm": 5,
    }
    cost, debug = calculate_logistic_cost(logistic, product)
    assert cost is not None
    assert any("体积重量" in s for s in debug)


def test_calculate_logistic_cost_sum_of_sides_exceeds_threshold():
    logistic = {
        "min_weight": 0,
        "max_weight": 10**9,
        "max_sum_of_sides": 500,
        "max_longest_side": 300,
        "fee_mode": "base_plus_continue",
        "continue_unit": 100,
        "continue_fee": Decimal("0.5"),
        "base_fee": Decimal("2.0"),
        "volume_mode": "sum_of_sides",
        "sum_of_sides_threshold": 60,
        "volume_coefficient": 6000,
    }
    product = {
        "weight_g": 500,
        "length_cm": 30,
        "width_cm": 20,
        "height_cm": 15,
    }

    cost, debug = calculate_logistic_cost(logistic, product)

    assert cost is not None
    assert any("计费重量：1500.00g" in s for s in debug)


def test_calculate_logistic_cost_sum_of_sides_below_threshold():
    logistic = {
        "min_weight": 0,
        "max_weight": 10**9,
        "max_sum_of_sides": 500,
        "max_longest_side": 300,
        "fee_mode": "base_plus_continue",
        "continue_unit": 100,
        "continue_fee": Decimal("0.5"),
        "base_fee": Decimal("2.0"),
        "volume_mode": "sum_of_sides",
        "sum_of_sides_threshold": 90,
        "volume_coefficient": 6000,
    }
    product = {
        "weight_g": 500,
        "length_cm": 30,
        "width_cm": 20,
        "height_cm": 15,
    }

    cost, debug = calculate_logistic_cost(logistic, product)

    assert cost is not None
    assert any("计费重量：500.00g" in s for s in debug)


def test_filter_check_weight_sum_of_sides_exceeds_threshold():
    logistic = {
        "min_weight": 0,
        "max_weight": 10**9,
        "volume_mode": "sum_of_sides",
        "sum_of_sides_threshold": 60,
        "volume_coefficient": 6000,
    }
    product = {
        "weight_g": 500,
        "length_cm": 30,
        "width_cm": 20,
        "height_cm": 15,
    }

    weight, err = _filter_check_weight(logistic, product)

    assert err is None
    assert weight == pytest.approx(1500.0)


def test_filter_check_weight_sum_of_sides_below_threshold():
    logistic = {
        "min_weight": 0,
        "max_weight": 10**9,
        "volume_mode": "sum_of_sides",
        "sum_of_sides_threshold": 90,
        "volume_coefficient": 6000,
    }
    product = {
        "weight_g": 500,
        "length_cm": 30,
        "width_cm": 20,
        "height_cm": 15,
    }

    weight, err = _filter_check_weight(logistic, product)

    assert err is None
    assert weight == 500


def test_calculate_logistic_cost_cylinder_rules_reject():
    logistic = {
        "min_weight": 0,
        "max_weight": 10**9,
        "max_cylinder_sum": 30,
        "volume_mode": "none",
        "fee_mode": "base_plus_continue",
        "continue_unit": 100,
        "continue_fee": Decimal("1"),
        "base_fee": Decimal("0"),
    }
    product = {
        "weight_g": 500,
        "is_cylinder": True,
        "cylinder_diameter": 10,
        "cylinder_length": 20,
    }
    cost, debug = calculate_logistic_cost(logistic, product)
    assert cost is None
    assert any("返回 None" in s for s in debug)


@patch(
    "pricing.calculate_pricing._get_exchange_rates",
    return_value=(Decimal("0.0904"), Decimal("7.2")),
)
def test_pricing_with_cny_limits(_mock_rates):
    product = {
        "unit_price": Decimal("10.0"),
        "labeling_fee": Decimal("1.0"),
        "shipping_fee": Decimal("2.0"),
        "promotion_cost_rate": Decimal("0.1"),
        "commission_rate": Decimal("0.1"),
        "withdrawal_fee_rate": Decimal("0.02"),
        "payment_processing_fee": Decimal("0.0"),
        "target_profit_margin": Decimal("0.2"),
        "weight_g": 200,
        "length_cm": 10,
        "width_cm": 10,
        "height_cm": 10,
    }
    land = [
        {
            "name": "L1",
            "type": "land",
            "min_days": 3,
            "max_days": 7,
            "fee_mode": "base_plus_continue",
            "continue_unit": 100,
            "continue_fee": Decimal("0.5"),
            "base_fee": Decimal("2.0"),
            "max_sum_of_sides": 500,
            "max_longest_side": 300,
            "price_limit_cny": Decimal("1000000000"),
            "price_min_cny": Decimal("0"),
        }
    ]
    air = []
    res = calculate_pricing(product, land, air, "低价优先")
    assert res["best_land"] is not None
    assert res["land_cost"] is not None
    assert res["suggested_price"] is not None


@patch(
    "pricing.calculate_pricing._get_exchange_rates",
    return_value=(Decimal("0.0904"), Decimal("7.2")),
)
def test_air_profit_margin_not_zero_when_air_only(_mock_rates):
    """当只有空运方案时，空运的 profit_margin 不应为 0。"""
    product = {
        "unit_price": Decimal("10.0"),
        "labeling_fee": Decimal("1.0"),
        "shipping_fee": Decimal("2.0"),
        "promotion_cost_rate": Decimal("0.1"),
        "commission_rate": Decimal("0.1"),
        "withdrawal_fee_rate": Decimal("0.02"),
        "payment_processing_fee": Decimal("0.0"),
        "target_profit_margin": Decimal("0.2"),
        "weight_g": 200,
        "length_cm": 10,
        "width_cm": 10,
        "height_cm": 10,
    }
    land = []
    air = [
        {
            "name": "A1",
            "type": "air",
            "min_days": 1,
            "max_days": 3,
            "fee_mode": "base_plus_continue",
            "continue_unit": 100,
            "continue_fee": Decimal("0.5"),
            "base_fee": Decimal("5.0"),
            "max_sum_of_sides": 500,
            "max_longest_side": 300,
            "price_limit_cny": Decimal("1000000000"),
            "price_min_cny": Decimal("0"),
        }
    ]
    res = calculate_pricing(product, land, air, mode="precise", priority="低价优先")
    assert res["best_air"] is not None
    assert res["air_price"] is not None
    assert res["air_expected_profit"] != 0
    assert res["air_profit_margin"] != 0, "air_profit_margin 不应为 0，当只有空运方案时"
    # suggested 也应该用空运的值
    assert res["suggested_price"] == res["air_price"]
    assert res["profit_margin"] == res["air_profit_margin"]


@patch(
    "pricing.calculate_pricing._get_exchange_rates",
    return_value=(Decimal("0.0904"), Decimal("7.2")),
)
def test_air_profit_margin_correct_when_both_land_and_air(_mock_rates):
    """当陆运和空运都有方案时，两者都应有正确的 profit_margin。"""
    product = {
        "unit_price": Decimal("10.0"),
        "labeling_fee": Decimal("1.0"),
        "shipping_fee": Decimal("2.0"),
        "promotion_cost_rate": Decimal("0.1"),
        "commission_rate": Decimal("0.1"),
        "withdrawal_fee_rate": Decimal("0.02"),
        "payment_processing_fee": Decimal("0.0"),
        "target_profit_margin": Decimal("0.2"),
        "weight_g": 200,
        "length_cm": 10,
        "width_cm": 10,
        "height_cm": 10,
    }
    land = [
        {
            "name": "L1",
            "type": "land",
            "min_days": 5,
            "max_days": 10,
            "fee_mode": "base_plus_continue",
            "continue_unit": 100,
            "continue_fee": Decimal("0.3"),
            "base_fee": Decimal("2.0"),
            "max_sum_of_sides": 500,
            "max_longest_side": 300,
            "price_limit_cny": Decimal("1000000000"),
            "price_min_cny": Decimal("0"),
        }
    ]
    air = [
        {
            "name": "A1",
            "type": "air",
            "min_days": 1,
            "max_days": 3,
            "fee_mode": "base_plus_continue",
            "continue_unit": 100,
            "continue_fee": Decimal("0.8"),
            "base_fee": Decimal("5.0"),
            "max_sum_of_sides": 500,
            "max_longest_side": 300,
            "price_limit_cny": Decimal("1000000000"),
            "price_min_cny": Decimal("0"),
        }
    ]
    res = calculate_pricing(product, land, air, mode="precise", priority="低价优先")
    assert res["best_land"] is not None
    assert res["best_air"] is not None
    assert res["land_profit_margin"] != 0
    assert res["air_profit_margin"] != 0
    # land 和 air 的 profit_margin 应该独立且不同（因为成本不同）
    assert res["land_profit_margin"] != res["air_profit_margin"]
    # suggested 应该选择陆运（因为陆运成本更低）
    assert res["suggested_price"] == res["land_price"]
    assert res["profit_margin"] == res["land_profit_margin"]


@patch(
    "pricing.calculate_pricing._get_exchange_rates",
    return_value=(Decimal("0.0904"), Decimal("7.2")),
)
def test_result_has_air_profit_margin_key(_mock_rates):
    """结果字典必须包含 air_profit_margin 和 land_profit_margin 键。"""
    product = {
        "unit_price": Decimal("10.0"),
        "labeling_fee": Decimal("1.0"),
        "shipping_fee": Decimal("2.0"),
        "promotion_cost_rate": Decimal("0.1"),
        "commission_rate": Decimal("0.1"),
        "withdrawal_fee_rate": Decimal("0.02"),
        "payment_processing_fee": Decimal("0.0"),
        "target_profit_margin": Decimal("0.2"),
        "weight_g": 200,
        "length_cm": 10,
        "width_cm": 10,
        "height_cm": 10,
    }
    land = [
        {
            "name": "L1",
            "type": "land",
            "min_days": 3,
            "max_days": 7,
            "fee_mode": "base_plus_continue",
            "continue_unit": 100,
            "continue_fee": Decimal("0.5"),
            "base_fee": Decimal("2.0"),
            "max_sum_of_sides": 500,
            "max_longest_side": 300,
            "price_limit_cny": Decimal("1000000000"),
            "price_min_cny": Decimal("0"),
        }
    ]
    air = [
        {
            "name": "A1",
            "type": "air",
            "min_days": 1,
            "max_days": 3,
            "fee_mode": "base_plus_continue",
            "continue_unit": 100,
            "continue_fee": Decimal("0.5"),
            "base_fee": Decimal("5.0"),
            "max_sum_of_sides": 500,
            "max_longest_side": 300,
            "price_limit_cny": Decimal("1000000000"),
            "price_min_cny": Decimal("0"),
        }
    ]
    res = calculate_pricing(product, land, air, mode="precise", priority="低价优先")
    assert "air_profit_margin" in res
    assert "land_profit_margin" in res


class TestComputeBillableWeight:
    def test_max_actual_vs_volume_volume_wins(self):
        logistic = {
            "volume_mode": "max_actual_vs_volume",
            "volume_coefficient": 12000,
        }

        weight, label, triggered = _compute_billable_weight(
            logistic,
            [60, 51, 46],
            1000,
        )

        assert weight == pytest.approx(11730, abs=0.01)
        assert label == "体积重"
        assert triggered is True

    def test_max_actual_vs_volume_actual_wins(self):
        logistic = {
            "volume_mode": "max_actual_vs_volume",
            "volume_coefficient": 12000,
        }

        weight, label, triggered = _compute_billable_weight(
            logistic,
            [10, 10, 10],
            20000,
        )

        assert weight == pytest.approx(20000, abs=0.01)
        assert label == "实重"
        assert triggered is False

    def test_longest_side_threshold_exceeded(self):
        logistic = {
            "volume_mode": "longest_side",
            "longest_side_threshold": 30,
            "volume_coefficient": 12000,
        }

        weight, label, triggered = _compute_billable_weight(
            logistic,
            [60, 10, 10],
            500,
        )

        assert weight == pytest.approx(500, abs=0.01)
        assert label == "体积重"
        assert triggered is True

    def test_longest_side_below_threshold(self):
        logistic = {
            "volume_mode": "longest_side",
            "longest_side_threshold": 100,
            "volume_coefficient": 12000,
        }

        weight, label, triggered = _compute_billable_weight(
            logistic,
            [60, 10, 10],
            500,
        )

        assert weight == pytest.approx(500, abs=0.01)
        assert label == "实重"
        assert triggered is False

    def test_sum_of_sides_threshold_exceeded(self):
        logistic = {
            "volume_mode": "sum_of_sides",
            "sum_of_sides_threshold": 80,
            "volume_coefficient": 12000,
        }

        weight, label, triggered = _compute_billable_weight(
            logistic,
            [40, 40, 40],
            300,
        )

        assert float(weight) == pytest.approx(5333.333333, abs=0.01)
        assert label == "体积重"
        assert triggered is True

    def test_sum_of_sides_below_threshold(self):
        logistic = {
            "volume_mode": "sum_of_sides",
            "sum_of_sides_threshold": 200,
            "volume_coefficient": 12000,
        }

        weight, label, triggered = _compute_billable_weight(
            logistic,
            [40, 40, 40],
            300,
        )

        assert weight == pytest.approx(300, abs=0.01)
        assert label == "实重"
        assert triggered is False

    def test_volume_mode_none(self):
        logistic = {"volume_mode": "none"}

        weight, label, triggered = _compute_billable_weight(
            logistic,
            [40, 40, 40],
            999,
        )

        assert weight == pytest.approx(999, abs=0.01)
        assert label == "实重"
        assert triggered is False

    def test_zero_coefficient_defensive(self):
        logistic = {
            "volume_mode": "max_actual_vs_volume",
            "volume_coefficient": 0,
        }

        weight, label, triggered = _compute_billable_weight(
            logistic,
            [60, 51, 46],
            500,
        )

        assert weight == pytest.approx(500, abs=0.01)
        assert label == "实重"
        assert triggered is False


def _billable_test_logistic(**overrides):
    logistic = {
        "min_weight": 0,
        "max_weight": 20000,
        "max_sum_of_sides": 10**9,
        "max_longest_side": 10**9,
        "fee_mode": "base_plus_continue",
        "continue_unit": 100,
        "continue_fee": Decimal("0.5"),
        "base_fee": Decimal("2.0"),
        "volume_mode": "max_actual_vs_volume",
        "volume_coefficient": 12000,
        "allow_battery": True,
        "allow_liquid": True,
        "price_limit_cny": Decimal("1000000000"),
        "price_min_cny": Decimal("0"),
    }
    logistic.update(overrides)
    return logistic


def _billable_test_product(**overrides):
    product = {
        "weight_g": 2000,
        "length_cm": 60,
        "width_cm": 51,
        "height_cm": 46,
        "unit_price": Decimal("10"),
        "labeling_fee": Decimal("0"),
        "shipping_fee": Decimal("0"),
        "target_profit_margin": Decimal("0"),
        "promotion_cost_rate": Decimal("0"),
        "commission_rate": Decimal("0"),
        "withdrawal_fee_rate": Decimal("0"),
        "payment_processing_fee": Decimal("0"),
    }
    product.update(overrides)
    return product


def test_filter_and_cost_billable_weight_consistent():
    from pricing.logistic_cost import calculate_logistic_cost

    logistic = _billable_test_logistic()
    product = _billable_test_product()
    expected_weight, _label, _triggered = _compute_billable_weight(
        logistic,
        [60, 51, 46],
        2000,
    )

    w_filter, err = _filter_check_weight(logistic, product)
    cost, debug_info = calculate_logistic_cost(logistic, product)

    assert err is None
    assert w_filter == pytest.approx(expected_weight, abs=0.01)
    assert cost is not None
    assert any(f"{expected_weight:.2f}" in line for line in debug_info)


def test_volume_weight_passes_min_weight_check():
    from pricing.logistic_cost import calculate_logistic_cost

    logistic = _billable_test_logistic(min_weight=2001, max_weight=20000)
    product = _billable_test_product()

    cost, _debug_info = calculate_logistic_cost(logistic, product)
    w_filter, err = _filter_check_weight(logistic, product)

    assert cost is not None
    assert err is None
    assert w_filter is not None


def test_filter_reason_never_empty():
    from pricing.filter import _debug_filter_reason  # pyright: ignore[reportPrivateUsage]

    cases = [
        (
            _billable_test_logistic(max_weight=10000),
            _billable_test_product(),
        ),
        (
            _billable_test_logistic(min_weight=20000),
            _billable_test_product(),
        ),
        (
            _billable_test_logistic(allow_battery=False),
            _billable_test_product(has_battery=True),
        ),
        (
            _billable_test_logistic(price_limit_cny=Decimal("1")),
            _billable_test_product(unit_price=Decimal("1000")),
        ),
        (
            _billable_test_logistic(),
            _billable_test_product(),
        ),
    ]

    reasons = [_debug_filter_reason(logistic, product) for logistic, product in cases]

    assert reasons[-1] == "未识别的淘汰原因"
    assert all(isinstance(reason, str) and len(reason) > 0 for reason in reasons)


@pytest.mark.parametrize(
    ("logistic", "product", "expected"),
    [
        (
            _billable_test_logistic(
                volume_mode="sum_of_sides",
                volume_coefficient=5000,
                sum_of_sides_threshold=10,
                max_weight=10000,
            ),
            _billable_test_product(weight_g=500),
            "体积重 28152.00g 超过上限 10000g",
        ),
        (
            _billable_test_logistic(
                volume_mode="max_actual_vs_volume",
                volume_coefficient=5000,
                max_weight=30000,
            ),
            _billable_test_product(
                weight_g=50000,
                length_cm=10,
                width_cm=10,
                height_cm=10,
            ),
            "实重 50000.00g 超过上限 30000g",
        ),
        (
            _billable_test_logistic(
                volume_mode="none",
                min_weight=1000,
            ),
            _billable_test_product(weight_g=500),
            "实重 500.00g 低于下限 1000g",
        ),
        (
            _billable_test_logistic(
                volume_mode="sum_of_sides",
                volume_coefficient=100000,
                sum_of_sides_threshold=10,
                min_weight=2000,
            ),
            _billable_test_product(weight_g=10000),
            "体积重 1407.60g 低于下限 2000g",
        ),
    ],
)
def test_max_weight_exceeded_reason_format(logistic, product, expected):
    weight, reason = _filter_check_weight(logistic, product)

    assert weight is None
    assert reason == expected
