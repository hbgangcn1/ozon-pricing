# tests/test_logic_coverage.py
import sys
import os
import pytest
import pricing

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

calculate_logistic_cost = pricing.calculate_logistic_cost
calculate_pricing = pricing.calculate_pricing
_debug_filter_reason = getattr(pricing, "_debug_filter_reason")


def mk_log(**kw):
    d = {
        "name": "L",
        "fee_mode": "base_plus_continue",
        "base_fee": 5.0,
        "continue_unit": 100,
        "continue_fee": 1.0,
        "min_weight": 0,
        "max_weight": 0,
        "volume_mode": "none",
        "volume_coefficient": 5000,
    }
    d.update(kw)
    return d


def mk_prod(**kw):
    d = {
        "weight_g": 500,
        "length_cm": 10,
        "width_cm": 10,
        "height_cm": 5,
        "unit_price": 20.0,
        "labeling_fee": 0.0,
        "shipping_fee": 0.0,
        "target_profit_margin": 0.2,
        "commission_rate": 0.08,
        "withdrawal_fee_rate": 0.02,
        "promotion_cost_rate": 0.0,
        "payment_processing_fee": 0.0,
        "return_rate": 0.0,
        "vat_rate": 0.0,
    }
    d.update(kw)
    return d


def dfr_log(**kw):
    d = {
        "min_weight": 0,
        "max_weight": 10**9,
        "volume_mode": "none",
        "fee_mode": "base_weight",
        "base_fee": 5,
        "continue_fee": 1,
        "continue_unit": 100,
    }
    d.update(kw)
    return d


def dfr_prod(**kw):
    d = {
        "weight_g": 100,
        "length_cm": 5,
        "width_cm": 5,
        "height_cm": 5,
        "unit_price": 10,
        "labeling_fee": 0,
        "shipping_fee": 0,
        "target_profit_margin": 0,
        "commission_rate": 0,
        "withdrawal_fee_rate": 0,
        "payment_processing_fee": 0,
    }
    d.update(kw)
    return d


def cc(log, prod, **kw):
    return calculate_logistic_cost(log, prod, **kw)[0]


def test_cost_none_log():
    assert cc(None, mk_prod()) is None


def test_cost_none_prod():
    assert cc(mk_log(), None) is None


def test_cost_none_debug():
    r, i = calculate_logistic_cost(None, None)
    assert r is None and any("无效" in s for s in i)


def test_cost_non_dict_log_raises():
    with pytest.raises(AttributeError):
        cc("x", mk_prod())


def test_cost_non_dict_prod_raises():
    with pytest.raises(AttributeError):
        cc(mk_log(), "x")


def test_cost_neg_weight():
    assert cc(mk_log(), mk_prod(weight_g=-1)) is None


def test_cost_zero_weight():
    assert cc(mk_log(base_fee=42.0), mk_prod(weight_g=0)) == 42.0


def test_cost_zero_weight_dbg():
    c, i = calculate_logistic_cost(mk_log(base_fee=9.0), mk_prod(weight_g=0))
    assert c == 9.0 and any("重量为0" in s for s in i)


def test_cost_below_min():
    assert cc(mk_log(min_weight=1000), mk_prod(weight_g=100)) is None


def test_cost_above_max():
    assert cc(mk_log(max_weight=200), mk_prod(weight_g=500)) is None


def test_cost_exc_debug():
    r, info = calculate_logistic_cost(
        mk_log(volume_mode="max_actual_vs_volume", volume_coefficient=0), mk_prod()
    )
    assert r is None and any("出错" in s for s in info)


def test_cost_exc_nodebug():
    assert (
        cc(mk_log(volume_mode="max_actual_vs_volume", volume_coefficient=0), mk_prod())
        is None
    )


def test_cyl_max_sum_fail():
    assert (
        cc(
            mk_log(max_cylinder_sum=30),
            mk_prod(is_cylinder=True, cylinder_diameter=10, cylinder_length=20),
        )
        is None
    )


def test_cyl_max_sum_ok():
    assert (
        cc(
            mk_log(max_cylinder_sum=50),
            mk_prod(is_cylinder=True, cylinder_diameter=10, cylinder_length=20),
        )
        is not None
    )


def test_cyl_min_sum_fail():
    assert (
        cc(
            mk_log(min_cylinder_sum=50),
            mk_prod(is_cylinder=True, cylinder_diameter=5, cylinder_length=10),
        )
        is None
    )


def test_cyl_max_len_fail():
    assert (
        cc(
            mk_log(max_cylinder_length=15),
            mk_prod(is_cylinder=True, cylinder_diameter=5, cylinder_length=20),
        )
        is None
    )


def test_cyl_min_len_fail():
    assert (
        cc(
            mk_log(min_cylinder_length=25),
            mk_prod(is_cylinder=True, cylinder_diameter=5, cylinder_length=10),
        )
        is None
    )


def test_cyl_no_limits():
    assert (
        cc(
            mk_log(max_sum_of_sides=200),
            mk_prod(is_cylinder=True, cylinder_diameter=10, cylinder_length=20),
        )
        is not None
    )


def test_cyl_fast_mode():
    assert (
        cc(
            mk_log(max_cylinder_sum=5),
            mk_prod(
                name="极速模式产品",
                is_cylinder=True,
                cylinder_diameter=10,
                cylinder_length=20,
            ),
            is_fast_mode=True,
        )
        is not None
    )


def test_max_sum_fail():
    assert cc(mk_log(max_sum_of_sides=20), mk_prod()) is None


def test_max_long_fail():
    assert (
        cc(mk_log(max_longest_side=5), mk_prod(length_cm=10, width_cm=5, height_cm=3))
        is None
    )


def test_max_2nd_fail():
    assert (
        cc(mk_log(max_second_side=4), mk_prod(length_cm=10, width_cm=8, height_cm=3))
        is None
    )


def test_max_2nd_ok():
    assert (
        cc(mk_log(max_second_side=10), mk_prod(length_cm=10, width_cm=8, height_cm=3))
        is not None
    )


def test_min_2nd_fail():
    assert (
        cc(mk_log(min_second_side=9), mk_prod(length_cm=10, width_cm=8, height_cm=3))
        is None
    )


def test_max_3rd_fail():
    assert (
        cc(mk_log(max_third_side=2), mk_prod(length_cm=10, width_cm=8, height_cm=3))
        is None
    )


def test_max_3rd_ok():
    assert (
        cc(mk_log(max_third_side=5), mk_prod(length_cm=10, width_cm=8, height_cm=3))
        is not None
    )


def test_max_3rd_zero_means_no_limit():
    assert (
        cc(mk_log(max_third_side=0), mk_prod(length_cm=10, width_cm=8, height_cm=3))
        is not None
    )


def test_min_len_fail():
    assert cc(mk_log(min_length=50), mk_prod()) is None


def test_min_len_ok():
    assert cc(mk_log(min_length=5), mk_prod()) is not None


def test_batt_not_allowed():
    assert cc(mk_log(allow_battery=False), mk_prod(has_battery=True)) is None


def test_batt_allowed():
    assert cc(mk_log(allow_battery=True), mk_prod(has_battery=True)) is not None


def test_liq_not_allowed():
    assert cc(mk_log(allow_liquid=False), mk_prod(has_liquid=True)) is None


def test_batt_wh_over():
    assert (
        cc(
            mk_log(allow_battery=True, battery_capacity_limit_wh=50),
            mk_prod(has_battery=True, battery_capacity_wh=100),
        )
        is None
    )


def test_batt_wh_ok():
    assert (
        cc(
            mk_log(allow_battery=True, battery_capacity_limit_wh=200),
            mk_prod(has_battery=True, battery_capacity_wh=100),
        )
        is not None
    )


def test_batt_mah_over():
    assert (
        cc(
            mk_log(allow_battery=True, battery_capacity_limit_wh=10),
            mk_prod(
                has_battery=True,
                battery_capacity_wh=0,
                battery_capacity_mah=5000,
                battery_voltage=5,
            ),
        )
        is None
    )


def test_batt_mah_zero():
    assert (
        cc(
            mk_log(allow_battery=True, battery_capacity_limit_wh=10),
            mk_prod(
                has_battery=True,
                battery_capacity_wh=0,
                battery_capacity_mah=0,
                battery_voltage=0,
            ),
        )
        is not None
    )


def test_batt_wh_zero():
    assert (
        cc(
            mk_log(allow_battery=True, battery_capacity_limit_wh=10),
            mk_prod(has_battery=True, battery_capacity_wh=0),
        )
        is not None
    )


def test_msds_missing():
    assert (
        cc(
            mk_log(allow_battery=True, require_msds=True),
            mk_prod(has_battery=True, has_msds=False),
        )
        is None
    )


def test_msds_present():
    assert (
        cc(
            mk_log(allow_battery=True, require_msds=True),
            mk_prod(has_battery=True, has_msds=True),
        )
        is not None
    )


def test_vol_max_actual():
    c, d = calculate_logistic_cost(
        mk_log(volume_mode="max_actual_vs_volume"), mk_prod()
    )
    assert c is not None and any("体积重量" in s for s in d)


def test_vol_longest_above():
    c, d = calculate_logistic_cost(
        mk_log(volume_mode="longest_side", longest_side_threshold=8),
        mk_prod(length_cm=10, width_cm=5, height_cm=3),
    )
    assert c is not None and any("体积重量" in s for s in d)


def test_vol_longest_below():
    c, d = calculate_logistic_cost(
        mk_log(volume_mode="longest_side", longest_side_threshold=20),
        mk_prod(length_cm=10, width_cm=5, height_cm=3),
    )
    assert c is not None and any("实际重量" in s for s in d)


@pytest.mark.parametrize("u", ["kg", "g", "50g", "500g", "1kg", "0.5kg", "invalid"])
def test_cu_string(u):
    from decimal import Decimal
    assert isinstance(
        cc(mk_log(continue_unit=u, base_fee=0.0), mk_prod()), Decimal
    )


def test_cu_numeric():
    assert cc(
        mk_log(continue_unit=200, continue_fee=2.0, base_fee=0.0), mk_prod(weight_g=200)
    ) == pytest.approx(2.0)


def test_cu_zero():
    assert cc(mk_log(continue_unit=0), mk_prod()) is not None


def test_fee_base():
    assert cc(
        mk_log(
            fee_mode="base_weight", base_fee=10.0, continue_fee=2.0, continue_unit=100
        ),
        mk_prod(weight_g=200),
    ) == pytest.approx(14.0)


def test_fee_first_within():
    assert cc(
        mk_log(
            fee_mode="first_plus_continue",
            first_weight_g=500,
            first_fee=20.0,
            continue_fee=5.0,
            continue_unit=100,
        ),
        mk_prod(weight_g=300),
    ) == pytest.approx(20.0)


def test_fee_first_over():
    assert cc(
        mk_log(
            fee_mode="first_plus_continue",
            first_weight_g=500,
            first_fee=20.0,
            continue_fee=5.0,
            continue_unit=100,
        ),
        mk_prod(weight_g=700),
    ) == pytest.approx(30.0)


def test_dfr_below_min():
    assert "低于下限" in _debug_filter_reason(
        {"min_weight": 1000, "max_weight": 10**9, "volume_mode": "none"},
        {"weight_g": 100, "length_cm": 5, "width_cm": 5, "height_cm": 5},
    )


def test_dfr_above_max():
    assert "高于上限" in _debug_filter_reason(
        {"min_weight": 0, "max_weight": 100, "volume_mode": "none"},
        {"weight_g": 500, "length_cm": 5, "width_cm": 5, "height_cm": 5},
    )


def test_dfr_ok():
    assert _debug_filter_reason(dfr_log(), dfr_prod()) == ""


def test_dfr_vol_max():
    assert (
        _debug_filter_reason(
            dfr_log(volume_mode="max_actual_vs_volume", volume_coefficient=5000),
            dfr_prod(length_cm=20, width_cm=20, height_cm=20),
        )
        == ""
    )


def test_dfr_vol_long_above():
    assert (
        _debug_filter_reason(
            dfr_log(volume_mode="longest_side", longest_side_threshold=5),
            dfr_prod(length_cm=10),
        )
        == ""
    )


def test_dfr_vol_long_below():
    assert (
        _debug_filter_reason(
            dfr_log(volume_mode="longest_side", longest_side_threshold=50), dfr_prod()
        )
        == ""
    )


def test_dfr_cyl_max_sum():
    assert "超过" in _debug_filter_reason(
        {
            "min_weight": 0,
            "max_weight": 10**9,
            "volume_mode": "none",
            "max_cylinder_sum": 25,
        },
        {
            "weight_g": 100,
            "is_cylinder": True,
            "cylinder_diameter": 10,
            "cylinder_length": 20,
        },
    )


def test_dfr_cyl_min_sum():
    assert "低于下限" in _debug_filter_reason(
        {
            "min_weight": 0,
            "max_weight": 10**9,
            "volume_mode": "none",
            "min_cylinder_sum": 60,
        },
        {
            "weight_g": 100,
            "is_cylinder": True,
            "cylinder_diameter": 5,
            "cylinder_length": 10,
        },
    )


def test_dfr_cyl_max_len():
    assert "超过" in _debug_filter_reason(
        {
            "min_weight": 0,
            "max_weight": 10**9,
            "volume_mode": "none",
            "max_cylinder_length": 10,
        },
        {
            "weight_g": 100,
            "is_cylinder": True,
            "cylinder_diameter": 5,
            "cylinder_length": 20,
        },
    )


def test_dfr_cyl_min_len():
    assert "低于下限" in _debug_filter_reason(
        {
            "min_weight": 0,
            "max_weight": 10**9,
            "volume_mode": "none",
            "min_cylinder_length": 30,
        },
        {
            "weight_g": 100,
            "is_cylinder": True,
            "cylinder_diameter": 5,
            "cylinder_length": 10,
        },
    )


def test_dfr_cyl_no_limits():
    assert (
        _debug_filter_reason(
            dfr_log(),
            dfr_prod(is_cylinder=True, cylinder_diameter=5, cylinder_length=10),
        )
        == ""
    )
