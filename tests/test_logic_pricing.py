from decimal import Decimal

import pytest
from unittest.mock import patch

from pricing import calculate_logistic_cost, calculate_pricing
from pricing.filter import _filter_check_weight  # pyright: ignore[reportPrivateUsage]


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
    assert any("三边和超过阈值" in s for s in debug)


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
    assert any("三边和未超过阈值" in s for s in debug)


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
