# tests/test_logic_coverage_part2.py
from decimal import Decimal
import sys
import os
import pytest
import pricing

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

calculate_pricing = pricing.calculate_pricing
_debug_filter_reason = getattr(pricing, "_debug_filter_reason")

PRODUCT_DECIMAL_FIELDS = {
    "unit_price",
    "shipping_fee",
    "labeling_fee",
    "promotion_discount",
    "promotion_cost_rate",
    "target_profit_margin",
    "commission_rate",
    "withdrawal_fee_rate",
    "payment_processing_fee",
    "return_rate",
    "vat_rate",
}

LOGISTICS_DECIMAL_FIELDS = {
    "price_limit",
    "price_limit_rub",
    "price_min",
    "price_min_rub",
    "price_limit_cny",
    "price_min_cny",
    "base_fee",
    "first_fee",
    "continue_fee",
}


def _decimalize_fields(data, decimal_fields):
    for field in decimal_fields:
        value = data.get(field)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            data[field] = Decimal(str(value))
    return data


def mk_log(**kw):
    d = {
        "name": "L",
        "fee_mode": "base_plus_continue",
        "base_fee": Decimal("5.0"),
        "continue_unit": 100,
        "continue_fee": Decimal("1.0"),
        "min_weight": 0,
        "max_weight": 0,
        "volume_mode": "none",
        "volume_coefficient": 5000,
    }
    d.update(kw)
    return _decimalize_fields(d, LOGISTICS_DECIMAL_FIELDS)


def mk_prod(**kw):
    d = {
        "weight_g": 500,
        "length_cm": 10,
        "width_cm": 10,
        "height_cm": 5,
        "unit_price": Decimal("20.0"),
        "labeling_fee": Decimal("0.0"),
        "shipping_fee": Decimal("0.0"),
        "promotion_discount": Decimal("0.0"),
        "target_profit_margin": Decimal("0.2"),
        "commission_rate": Decimal("0.08"),
        "withdrawal_fee_rate": Decimal("0.02"),
        "promotion_cost_rate": Decimal("0.0"),
        "payment_processing_fee": Decimal("0.0"),
        "return_rate": Decimal("0.0"),
        "vat_rate": Decimal("0.0"),
    }
    d.update(kw)
    return _decimalize_fields(d, PRODUCT_DECIMAL_FIELDS)


def dfr_log(**kw):
    d = {
        "min_weight": 0,
        "max_weight": 10**9,
        "volume_mode": "none",
        "fee_mode": "base_weight",
        "base_fee": Decimal("5"),
        "continue_fee": Decimal("1"),
        "continue_unit": 100,
    }
    d.update(kw)
    return _decimalize_fields(d, LOGISTICS_DECIMAL_FIELDS)


def dfr_prod(**kw):
    d = {
        "weight_g": 100,
        "length_cm": 5,
        "width_cm": 5,
        "height_cm": 5,
        "unit_price": Decimal("10"),
        "labeling_fee": Decimal("0"),
        "shipping_fee": Decimal("0"),
        "promotion_discount": Decimal("0"),
        "target_profit_margin": Decimal("0"),
        "commission_rate": Decimal("0"),
        "withdrawal_fee_rate": Decimal("0"),
        "promotion_cost_rate": Decimal("0"),
        "payment_processing_fee": Decimal("0"),
        "return_rate": Decimal("0"),
        "vat_rate": Decimal("0"),
    }
    d.update(kw)
    return _decimalize_fields(d, PRODUCT_DECIMAL_FIELDS)


def test_dfr_max_sum():
    assert "三边之和" in _debug_filter_reason(
        {
            "min_weight": 0,
            "max_weight": 10**9,
            "volume_mode": "none",
            "max_sum_of_sides": 20,
        },
        {"weight_g": 100, "length_cm": 10, "width_cm": 10, "height_cm": 10},
    )


def test_dfr_max_long():
    assert "最长边" in _debug_filter_reason(
        {
            "min_weight": 0,
            "max_weight": 10**9,
            "volume_mode": "none",
            "max_longest_side": 5,
        },
        {"weight_g": 100, "length_cm": 10, "width_cm": 5, "height_cm": 3},
    )


def test_dfr_max_2nd():
    assert "第二边长" in _debug_filter_reason(
        {
            "min_weight": 0,
            "max_weight": 10**9,
            "volume_mode": "none",
            "max_second_side": 4,
        },
        {"weight_g": 100, "length_cm": 10, "width_cm": 8, "height_cm": 3},
    )


def test_dfr_min_2nd():
    assert "低于下限" in _debug_filter_reason(
        {
            "min_weight": 0,
            "max_weight": 10**9,
            "volume_mode": "none",
            "min_second_side": 10,
        },
        {"weight_g": 100, "length_cm": 10, "width_cm": 8, "height_cm": 3},
    )


def test_dfr_min_len():
    assert "低于下限" in _debug_filter_reason(
        {"min_weight": 0, "max_weight": 10**9, "volume_mode": "none", "min_length": 50},
        {"weight_g": 100, "length_cm": 10, "width_cm": 8, "height_cm": 3},
    )


def test_dfr_batt_no():
    assert "电池" in _debug_filter_reason(
        {
            "min_weight": 0,
            "max_weight": 10**9,
            "volume_mode": "none",
            "allow_battery": False,
        },
        {
            "weight_g": 100,
            "length_cm": 5,
            "width_cm": 5,
            "height_cm": 5,
            "has_battery": True,
        },
    )


def test_dfr_liq_no():
    assert "易燃液体" in _debug_filter_reason(
        {
            "min_weight": 0,
            "max_weight": 10**9,
            "volume_mode": "none",
            "allow_liquid": False,
        },
        {
            "weight_g": 100,
            "length_cm": 5,
            "width_cm": 5,
            "height_cm": 5,
            "has_liquid": True,
        },
    )


def test_dfr_batt_wh():
    assert "超过" in _debug_filter_reason(
        {
            "min_weight": 0,
            "max_weight": 10**9,
            "volume_mode": "none",
            "allow_battery": True,
            "battery_capacity_limit_wh": 50,
        },
        {
            "weight_g": 100,
            "length_cm": 5,
            "width_cm": 5,
            "height_cm": 5,
            "has_battery": True,
            "battery_capacity_wh": 100,
        },
    )


def test_dfr_batt_mah():
    assert "电池容量" in _debug_filter_reason(
        {
            "min_weight": 0,
            "max_weight": 10**9,
            "volume_mode": "none",
            "allow_battery": True,
            "battery_capacity_limit_wh": 10,
        },
        {
            "weight_g": 100,
            "length_cm": 5,
            "width_cm": 5,
            "height_cm": 5,
            "has_battery": True,
            "battery_capacity_wh": 0,
            "battery_capacity_mah": 5000,
            "battery_voltage": 5,
        },
    )


def test_dfr_batt_mah_zero():
    assert (
        _debug_filter_reason(dfr_log(allow_battery=True, battery_capacity_limit_wh=10),
        dfr_prod(
            has_battery=True,
            battery_capacity_wh=0,
            battery_capacity_mah=0,
            battery_voltage=0,
        ),) == "未识别的淘汰原因"
    )


def test_dfr_batt_wh_zero():
    assert (
        _debug_filter_reason(dfr_log(allow_battery=True, battery_capacity_limit_wh=10),
        dfr_prod(has_battery=True, battery_capacity_wh=0),) == "未识别的淘汰原因"
    )


def test_dfr_msds_miss():
    assert "MSDS" in _debug_filter_reason(
        {
            "min_weight": 0,
            "max_weight": 10**9,
            "volume_mode": "none",
            "allow_battery": True,
            "require_msds": True,
        },
        {
            "weight_g": 100,
            "length_cm": 5,
            "width_cm": 5,
            "height_cm": 5,
            "has_battery": True,
            "has_msds": False,
        },
    )


def test_dfr_cny_over():
    reason = _debug_filter_reason(
        dfr_log(price_limit_cny=1), dfr_prod(unit_price=100.0)
    )
    assert "超" in reason and "价格上限" in reason


def test_dfr_cny_ok():
    assert _debug_filter_reason(dfr_log(price_limit_cny=10**9), dfr_prod()) == "未识别的淘汰原因"


def test_dfr_cny_over_low_limit():
    reason = _debug_filter_reason(
        dfr_log(price_limit_cny=0.01),
        dfr_prod(unit_price=100.0),
    )
    assert "超" in reason and "价格上限" in reason


def test_dfr_cny_ok_high_limit():
    assert _debug_filter_reason(dfr_log(price_limit_cny=10**9), dfr_prod()) == "未识别的淘汰原因"


def test_dfr_cny_min():
    assert "低于价格下限" in _debug_filter_reason(
        dfr_log(price_min_cny=10**9), dfr_prod()
    )


def test_dfr_cny_min_high_threshold():
    assert "低于价格下限" in _debug_filter_reason(
        dfr_log(price_min_cny=10**9), dfr_prod()
    )


def test_dfr_denom_zero():
    assert isinstance(
        _debug_filter_reason(dfr_log(), dfr_prod(target_profit_margin=Decimal("1.0"))),
        str,
    )


def test_dfr_exc():
    assert isinstance(_debug_filter_reason(dfr_log(base_fee="BAD"), dfr_prod()), str)


@pytest.mark.parametrize("u", ["kg", "g", "50g", "1kg", "xyz"])
def test_dfr_cu(u):
    assert _debug_filter_reason(dfr_log(continue_unit=u), dfr_prod()) == "未识别的淘汰原因"


def test_dfr_fpc_within():
    assert (
        _debug_filter_reason(dfr_log(
            fee_mode="first_plus_continue",
            first_weight_g=500,
            first_fee=10.0,
            continue_fee=1.0,
            continue_unit=100,
        ),
        dfr_prod(weight_g=300),) == "未识别的淘汰原因"
    )


def test_dfr_fpc_over():
    assert (
        _debug_filter_reason(dfr_log(
            fee_mode="first_plus_continue",
            first_weight_g=50,
            first_fee=10.0,
            continue_fee=1.0,
            continue_unit=100,
        ),
        dfr_prod(weight_g=200),) == "未识别的淘汰原因"
    )


def test_pr_none_prod():
    assert calculate_pricing(None, [], [])["best_land"] is None  # type: ignore[arg-type]


def test_pr_none_land():
    assert calculate_pricing(mk_prod(), None, [])["best_land"] is None  # type: ignore[arg-type]


def test_pr_none_air():
    assert calculate_pricing(mk_prod(), [], None)["best_land"] is None  # type: ignore[arg-type]


def test_pr_empty():
    assert calculate_pricing(mk_prod(), [], [])["best_land"] is None


def test_pr_bad_prod_raises():
    with pytest.raises(AttributeError):
        calculate_pricing("x", [], [])  # type: ignore[arg-type]


def test_pr_land():
    r = calculate_pricing(mk_prod(), [mk_log(name="L1", min_days=3, max_days=7)], [])
    assert r["best_land"] is not None and r["land_price"] > 0


def test_pr_air():
    r = calculate_pricing(mk_prod(), [], [mk_log(name="A1", min_days=1, max_days=3)])
    assert r["best_air"] is not None and r["air_price"] > 0


def test_pr_both():
    r = calculate_pricing(
        mk_prod(),
        [mk_log(name="L1", min_days=3, max_days=7)],
        [mk_log(name="A1", min_days=1, max_days=3)],
    )
    assert r["land_price"] is not None and r["air_price"] is not None


def test_pr_speed():
    land = [
        mk_log(
            name="Slow", priority_group="D", min_days=10, max_days=20, continue_fee=0.1
        ),
        mk_log(
            name="Fast", priority_group="A", min_days=1, max_days=2, continue_fee=2.0
        ),
    ]
    assert (
        calculate_pricing(mk_prod(), land, [], priority="速度优先")["best_land"]["name"]
        == "Fast"
    )


def test_pr_cheap():
    land = [
        mk_log(
            name="Cheap", priority_group="D", min_days=10, max_days=20, continue_fee=0.1
        ),
        mk_log(
            name="Exp", priority_group="A", min_days=1, max_days=2, continue_fee=5.0
        ),
    ]
    assert (
        calculate_pricing(mk_prod(), land, [], priority="低价优先")["best_land"]["name"]
        == "Cheap"
    )


def test_pr_filtered():
    r = calculate_pricing(
        mk_prod(weight_g=500),
        [mk_log(name="TL", max_weight=100), mk_log(name="OK")],
        [],
    )
    assert "TL" in [x["name"] for x in r["filtered_logistics"]["land"]]


def test_pr_unselected():
    land = [
        mk_log(name="C", continue_fee=0.5, delivery_method="x"),
        mk_log(name="E", continue_fee=5.0, delivery_method="x"),
    ]
    r = calculate_pricing(mk_prod(), land, [])
    assert "E" in [x["name"] for x in r["filtered_logistics"]["land"]]


def test_pr_stats():
    land = [
        mk_log(name="L1", min_days=3, max_days=7, continue_fee=1.0),
        mk_log(name="L2", min_days=5, max_days=10, continue_fee=2.0),
    ]
    r = calculate_pricing(mk_prod(), land, [])
    assert r["land_stats"] is not None and r["land_stats"]["avg_cost"] > 0


def test_pr_fast():
    assert (
        calculate_pricing(mk_prod(), [mk_log(min_days=3, max_days=7)], [], mode="fast")[
            "land_price"
        ]
        is not None
    )


def test_pr_std():
    assert (
        calculate_pricing(
            mk_prod(), [mk_log(min_days=3, max_days=7)], [], mode="standard"
        )["land_price"]
        is not None
    )


def test_pr_pct():
    r = calculate_pricing(
        mk_prod(target_profit_margin=20, commission_rate=8, withdrawal_fee_rate=2),
        [mk_log(min_days=3, max_days=7)],
        [],
    )
    assert r["land_price"] is not None and r["land_price"] > 0


def test_pr_rates_pct():
    r = calculate_pricing(
        mk_prod(
            target_profit_margin=20,
            commission_rate=8,
            withdrawal_fee_rate=2,
            promotion_cost_rate=5,
            return_rate=3,
            vat_rate=10,
        ),
        [mk_log(name="Lx", min_days=3, max_days=7)],
        [],
    )
    assert r["land_price"] is not None and r["land_price"] > 0


def test_pr_payment_rate():
    assert (
        calculate_pricing(
            mk_prod(payment_processing_fee=0.015),
            [mk_log(name="Lp", min_days=3, max_days=7)],
            [],
        )["land_price"]
        is not None
    )


def test_pr_filter_cny_over_tiny_limit():
    r = calculate_pricing(
        mk_prod(),
        [
            mk_log(
                name="UsdOver",
                price_limit_cny=0.001,
                min_days=3,
                max_days=7,
            )
        ],
        [],
    )
    assert "UsdOver" in [x["name"] for x in r["filtered_logistics"]["land"]]


def test_pr_filter_cny_over():
    r = calculate_pricing(
        mk_prod(),
        [
            mk_log(
                name="RubOver",
                price_limit_cny=1,
                min_days=3,
                max_days=7,
            )
        ],
        [],
    )
    assert "RubOver" in [x["name"] for x in r["filtered_logistics"]["land"]]


def test_pr_filter_cny_min():
    r = calculate_pricing(
        mk_prod(),
        [
            mk_log(
                name="UsdMin",
                price_min_cny=999999,
                min_days=3,
                max_days=7,
            )
        ],
        [],
    )
    assert "UsdMin" in [x["name"] for x in r["filtered_logistics"]["land"]]


def test_pr_filter_cny_min_huge_threshold():
    r = calculate_pricing(
        mk_prod(),
        [
            mk_log(
                name="RubMin",
                price_min_cny=10**9,
                min_days=3,
                max_days=7,
            )
        ],
        [],
    )
    assert "RubMin" in [x["name"] for x in r["filtered_logistics"]["land"]]


def test_pr_filter_cny_ok():
    assert (
        calculate_pricing(
            mk_prod(),
            [
                mk_log(
                    name="UsdOk",
                    price_limit_cny=9999,
                    min_days=3,
                    max_days=7,
                )
            ],
            [],
        )["best_land"]
        is not None
    )


def test_pr_filter_cny_ok_high_limit():
    assert (
        calculate_pricing(
            mk_prod(),
            [
                mk_log(
                    name="RubOk",
                    price_limit_cny=10**9,
                    min_days=3,
                    max_days=7,
                )
            ],
            [],
        )["best_land"]
        is not None
    )


def test_pr_air_filtered_cny_over():
    r = calculate_pricing(
        mk_prod(),
        [],
        [
            mk_log(
                name="AirUsdOver",
                price_limit_cny=0.001,
                min_days=1,
                max_days=3,
            )
        ],
    )
    assert "AirUsdOver" in [x["name"] for x in r["filtered_logistics"]["air"]]


def test_pr_air_filtered_cny_min():
    r = calculate_pricing(
        mk_prod(),
        [],
        [
            mk_log(
                name="AirRubMin",
                price_min_cny=10**9,
                min_days=1,
                max_days=3,
            )
        ],
    )
    assert "AirRubMin" in [x["name"] for x in r["filtered_logistics"]["air"]]


def test_pr_commission_in_numerator():
    assert (
        calculate_pricing(
            mk_prod(unit_price=0.1, weight_g=10),
            [
                mk_log(
                    name="Lc", base_fee=0.1, continue_fee=0.01, min_days=3, max_days=7
                )
            ],
            [],
        )["land_price"]
        is not None
    )


def test_pr_both_land_air_profit():
    r = calculate_pricing(
        mk_prod(),
        [mk_log(name="L1", min_days=5, max_days=10)],
        [mk_log(name="A1", min_days=1, max_days=3, continue_fee=3.0)],
    )
    assert r["expected_profit"] != 0 or r["land_price"] is not None


def test_pr_profit_margin_pct():
    r = calculate_pricing(
        mk_prod(
            target_profit_margin=20,
            commission_rate=8,
            withdrawal_fee_rate=2,
            promotion_cost_rate=5,
            return_rate=1,
            vat_rate=0,
        ),
        [mk_log(name="Lm", min_days=3, max_days=7)],
        [],
    )
    assert r["land_price"] is not None and r["profit_margin"] != 0


def test_pr_payment_fixed_profit():
    assert (
        calculate_pricing(
            mk_prod(payment_processing_fee=0.02, unit_price=5.0, weight_g=50),
            [
                mk_log(
                    name="Lpf", base_fee=0.1, continue_fee=0.01, min_days=3, max_days=7
                )
            ],
            [],
        )["land_price"]
        is not None
    )
