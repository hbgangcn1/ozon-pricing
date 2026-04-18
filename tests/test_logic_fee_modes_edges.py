from decimal import Decimal
from logic import calculate_logistic_cost


def test_first_plus_continue_threshold_and_units():
    logistic = {
        "min_weight": 0,
        "max_weight": 10**9,
        "fee_mode": "first_plus_continue",
        "first_weight_g": 200,
        "first_fee": 3.0,
        "continue_unit": 100,
        "continue_fee": 0.5,
        "max_sum_of_sides": 10**9,
        "max_longest_side": 10**9,
    }
    product_eq = {"weight_g": 200, "length_cm": 1, "width_cm": 1, "height_cm": 1}
    product_plus = {"weight_g": 201, "length_cm": 1, "width_cm": 1, "height_cm": 1}

    c_eq, _ = calculate_logistic_cost(logistic, product_eq)
    c_plus, _ = calculate_logistic_cost(logistic, product_plus)
    # 等于阈值收取首重费用
    assert abs(c_eq - Decimal("3.0")) < Decimal("1e-9")
    # 超过 1g -> 续重 ceil((201-200)/100)=1 单位
    assert abs(c_plus - Decimal("3.5")) < Decimal("1e-9")


def test_volume_mode_ties():
    # 体积重量≈实际重量两侧各 ±epsilon
    logistic = {
        "min_weight": 0,
        "max_weight": 10**9,
        "fee_mode": "base_plus_continue",
        "base_fee": 1.0,
        "continue_unit": 100,
        "continue_fee": 1.0,
        "volume_mode": "max_actual_vs_volume",
        "volume_coefficient": 1000,
        "max_sum_of_sides": 10**9,
        "max_longest_side": 10**9,
    }
    # 体积重量(g)= (10*10*10/1000)*1000=1000g
    product_lt = {"weight_g": 999, "length_cm": 10, "width_cm": 10, "height_cm": 10}
    product_gt = {"weight_g": 1001, "length_cm": 10, "width_cm": 10, "height_cm": 10}

    c_lt, _ = calculate_logistic_cost(logistic, product_lt)
    c_gt, _ = calculate_logistic_cost(logistic, product_gt)
    # 计费重量单位 100g
    # 对于 999g，体积重量更大 -> 1000g => units=10 -> cost=1+1*10
    assert abs(c_lt - Decimal("11.0")) < Decimal("1e-9")
    # 对于 1001g，实际重量更大 -> 1001g => units=11 -> cost=1+1*11
    assert abs(c_gt - Decimal("12.0")) < Decimal("1e-9")
