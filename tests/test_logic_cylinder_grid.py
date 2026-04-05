import pytest

from logic import calculate_logistic_cost


@pytest.mark.parametrize(
    "cd,cl,mc_sum,mi_sum,mc_len,mi_len,expect_none",
    [
        (10, 20, 30, 0, 0, 0, True),  # sum=40 > max_sum -> 淘汰
        (10, 20, 0, 50, 0, 0, True),  # sum=40 < min_sum -> 淘汰
        (10, 20, 40, 40, 0, 0, False),  # 等于边界 -> 通过
        (10, 25, 0, 0, 20, 0, True),  # len=25 > max_len=20 -> 淘汰
        (10, 15, 0, 0, 0, 20, True),  # len=15 < min_len=20 -> 淘汰
        (10, 20, 0, 0, 20, 20, False),  # 等于边界 -> 通过
    ],
)
def test_cylinder_grid(cd, cl, mc_sum, mi_sum, mc_len, mi_len, expect_none):
    logistic = {
        "min_weight": 0,
        "max_weight": 10**9,
        "fee_mode": "base_plus_continue",
        "continue_unit": 100,
        "continue_fee": 0.2,
        "base_fee": 1.0,
        "max_cylinder_sum": mc_sum,
        "min_cylinder_sum": mi_sum,
        "max_cylinder_length": mc_len,
        "min_cylinder_length": mi_len,
    }
    product = {
        "weight_g": 100,
        "is_cylinder": True,
        "cylinder_diameter": cd,
        "cylinder_length": cl,
    }
    res, _ = calculate_logistic_cost(logistic, product)
    if expect_none:
        assert res is None
    else:
        assert res is not None
