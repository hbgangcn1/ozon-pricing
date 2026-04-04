from logic import calculate_logistic_cost


def test_longest_side_threshold_boundary():
    # 等于阈值时不启用体积重量计费
    logistic = {
        "min_weight": 0,
        "max_weight": 10**9,
        "volume_mode": "longest_side",
        "longest_side_threshold": 30,
        "volume_coefficient": 5000,
        "fee_mode": "base_plus_continue",
        "continue_unit": 100,
        "continue_fee": 0.0,
        "base_fee": 0.0,
        "max_sum_of_sides": 10**9,
        "max_longest_side": 10**9,
    }
    product = {"weight_g": 100, "length_cm": 30, "width_cm": 10, "height_cm": 5}
    cost, debug = calculate_logistic_cost(logistic, product, debug=True)
    assert cost is not None
    # 调试信息应包含“未超过阈值，使用实际重量”提示
    assert any("未超过阈值" in s or "使用实际重量" in s for s in debug)


def test_cylinder_limits_equal_boundary():
    # 等于上限/下限应视为通过
    logistic = {
        "min_weight": 0,
        "max_weight": 10**9,
        "max_cylinder_sum": 40,
        "min_cylinder_sum": 40,
        "max_cylinder_length": 20,
        "min_cylinder_length": 20,
        "fee_mode": "base_plus_continue",
        "continue_unit": 100,
        "continue_fee": 0.0,
        "base_fee": 0.0,
    }
    product = {
        "weight_g": 100,
        "is_cylinder": True,
        "cylinder_diameter": 10,
        "cylinder_length": 20,
    }
    cost = calculate_logistic_cost(logistic, product, debug=False)
    assert cost is not None


def test_flammable_and_battery_skip_when_unknown():
    # has_liquid 不允许应淘汰
    logistic1 = {
        "min_weight": 0,
        "max_weight": 10**9,
        "allow_liquid": 0,
        "fee_mode": "base_plus_continue",
        "continue_unit": 100,
        "continue_fee": 0.0,
        "base_fee": 0.0,
        "max_sum_of_sides": 10**9,
        "max_longest_side": 10**9,
    }
    product1 = {
        "weight_g": 100,
        "length_cm": 10,
        "width_cm": 10,
        "height_cm": 10,
        "has_liquid": 1,
    }
    assert calculate_logistic_cost(logistic1, product1, debug=False) is None

    # 电池未知 (Wh=0 且 mAh=0,V=0) 应跳过容量限制判断，不被淘汰
    logistic2 = {
        **logistic1,
        "allow_liquid": 1,
        "battery_capacity_limit_wh": 1.0,
        "require_msds": 0,
        "allow_battery": 1,
    }
    product2 = {
        "weight_g": 100,
        "length_cm": 10,
        "width_cm": 10,
        "height_cm": 10,
        "has_battery": 1,
        "battery_capacity_wh": 0,
        "battery_capacity_mah": 0,
        "battery_voltage": 0,
    }
    cost2 = calculate_logistic_cost(logistic2, product2, debug=False)
    assert cost2 is not None




