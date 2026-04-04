from unittest.mock import patch

from logic import calculate_logistic_cost, calculate_pricing


def test_calculate_logistic_cost_standard_package_volume_mode():
    logistic = {
        "min_weight": 0,
        "max_weight": 10**9,
        "max_sum_of_sides": 200,
        "max_longest_side": 150,
        "fee_mode": "base_plus_continue",
        "continue_unit": 100,
        "continue_fee": 0.5,
        "base_fee": 2.0,
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


def test_calculate_logistic_cost_cylinder_rules_reject():
    logistic = {
        "min_weight": 0,
        "max_weight": 10**9,
        "max_cylinder_sum": 30,
        "volume_mode": "none",
        "fee_mode": "base_plus_continue",
        "continue_unit": 100,
        "continue_fee": 1,
        "base_fee": 0,
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
    return_value=(0.0904, 7.2),
)
def test_pricing_with_rub_limits(_mock_rates):
    product = {
        "unit_price": 10.0,
        "labeling_fee": 1.0,
        "shipping_fee": 2.0,
        "promotion_cost_rate": 0.1,
        "commission_rate": 0.1,
        "withdrawal_fee_rate": 0.02,
        "payment_processing_fee": 0.0,
        "target_profit_margin": 0.2,
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
            "continue_fee": 0.5,
            "base_fee": 2.0,
            "max_sum_of_sides": 500,
            "max_longest_side": 300,
            "price_limit_currency": "RUB",
            "price_limit_rub": 10**9,
            "price_min_currency": "RUB",
            "price_min_rub": 0,
        }
    ]
    air = []
    res = calculate_pricing(product, land, air, "低价优先")
    assert res["best_land"] is not None
    assert res["land_cost"] is not None
    assert res["suggested_price"] is not None
