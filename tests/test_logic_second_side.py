from logic import calculate_logistic_cost


def test_second_side_limits():
    # 超第二边上限被淘汰
    logistic = {
        "min_weight": 0,
        "max_weight": 10**9,
        "max_sum_of_sides": 10**9,
        "max_longest_side": 10**9,
        "max_second_side": 20,
        "fee_mode": "base_plus_continue",
        "continue_unit": 100,
        "continue_fee": 0.1,
        "base_fee": 1.0,
    }
    product = {
        "weight_g": 100,
        "length_cm": 50,
        "width_cm": 30,
        "height_cm": 10,
    }
    cost, _ = calculate_logistic_cost(logistic, product)
    assert cost is None

    # 第二边下限不满足被淘汰
    logistic2 = {
        **logistic,
        "max_second_side": 0,
        "min_second_side": 25,
    }
    product2 = {
        "weight_g": 100,
        "length_cm": 40,
        "width_cm": 20,
        "height_cm": 10,
    }
    cost2, _ = calculate_logistic_cost(logistic2, product2)
    assert cost2 is None
