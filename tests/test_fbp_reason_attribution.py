"""Regression tests for FBP eliminated-logistics reason attribution.

Verifies that when the three-stage pipeline runs (Stage1→Stage2→Stage3):
  - Logistics eliminated by Stage 1 (weight/dimension/price)
    keep their original first-filter reason.
  - Logistics that pass Stage 1 but are eliminated by Stage 2
    are tagged with the secondary reason.
  - Selected logistics (best_land/best_air) are never shown
    in the eliminated list.
"""

import os
import sys
from decimal import Decimal
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pricing.calculate_pricing import calculate_pricing_grouped  # noqa: E402


_FBP_ELIMINATED_REASON = "该物流无法覆盖更高成本"


def _product(weight_g=379):
    return {
        "unit_price": Decimal("100.0"),
        "labeling_fee": Decimal("0.5"),
        "shipping_fee": Decimal("1.0"),
        "commission_rate": Decimal("0.08"),
        "target_profit_margin": Decimal("0.2"),
        "promotion_cost_rate": Decimal("0.03"),
        "withdrawal_fee_rate": Decimal("0.01"),
        "payment_processing_fee": Decimal("0.02"),
        "return_rate": Decimal("0"),
        "vat_rate": Decimal("20"),
        "weight_g": weight_g,
        "length_cm": 10,
        "width_cm": 5,
        "height_cm": 3,
    }


def _make_calc_result(
    best_land_name=None, best_air_name=None, filtered_land=None, filtered_air=None
):
    return {
        "best_land": {"name": best_land_name} if best_land_name else None,
        "best_air": {"name": best_air_name} if best_air_name else None,
        "filtered_logistics": {
            "land": filtered_land or [],
            "air": filtered_air or [],
        },
    }


def _make_stage1_side_effect(
    land_survivors,
    air_survivors,
    land_eliminated=None,
    air_eliminated=None,
):
    def side_effect(
        product,
        land,
        air,
        up,
        lf,
        sf,
        rate,
        filtered,
        priority,
        mode,
    ):
        for item in land_eliminated or []:
            filtered["land"].append(item)
        for item in air_eliminated or []:
            filtered["air"].append(item)
        return (land_survivors, air_survivors, None, None, [])

    return side_effect


def test_weight_fail_shows_weight_reason_not_secondary():
    logistics = [
        {
            "name": "GUOO-FBP-Std-Small-KZ",
            "type": "land",
            "fulfillment_type": "fbp",
            "destination": "KZ",
            "fbp_company": "GUOO",
            "fbp_service_level": "standard",
            "base_fee": Decimal("100"),
            "min_weight": 0,
            "max_weight": 999999,
        },
        {
            "name": "GUOO-FBP-Std-Big-KZ",
            "type": "land",
            "fulfillment_type": "fbp",
            "destination": "KZ",
            "fbp_company": "GUOO",
            "fbp_service_level": "standard",
            "base_fee": Decimal("50"),
            "min_weight": 5001,
            "max_weight": 999999,
        },
    ]

    small_only = [(dict(logistics[0]), Decimal("5.0"))]
    weight_fail = [
        {"name": "GUOO-FBP-Std-Big-KZ", "reason": "重量 379 g 低于下限 5001 g"}
    ]
    stage1_se = _make_stage1_side_effect(
        small_only,
        [],
        land_eliminated=weight_fail,
    )

    def mock_calc(_product, land, air, mode="fast", priority="低价优先"):
        best = (
            "GUOO-FBP-Std-Small-KZ"
            if any(r.get("name") == "GUOO-FBP-Std-Small-KZ" for r in (land or []))
            else None
        )
        return _make_calc_result(best_land_name=best)

    with (
        patch(
            "pricing.calculate_pricing._run_filters",
            side_effect=stage1_se,
        ),
        patch(
            "pricing.grouped_pricing._get_exchange_rates",
            return_value=(Decimal("0.09"), Decimal("7.2")),
        ),
        patch(
            "pricing.calculate_pricing.calculate_pricing",
            side_effect=mock_calc,
        ),
    ):
        result = calculate_pricing_grouped(
            _product(weight_g=379), logistics, mode="precise"
        )

    filtered = result["fbp_cis"]["filtered_logistics"]
    all_items = filtered["land"] + filtered["air"]
    big_kz = [i for i in all_items if i.get("name") == "GUOO-FBP-Std-Big-KZ"]
    assert len(big_kz) == 1, f"Expected 1 entry, got {big_kz}"
    reason = big_kz[0]["reason"]
    assert "低于下限" in reason, (
        f"Expected weight reason containing '低于下限', got: {reason}"
    )
    assert reason != _FBP_ELIMINATED_REASON


def test_secondary_only_shows_secondary_reason():
    logistics = [
        {
            "name": "CEL-FBP-Eco-High-KZ",
            "type": "land",
            "fulfillment_type": "fbp",
            "destination": "KZ",
            "fbp_company": "CEL",
            "fbp_service_level": "economy",
            "base_fee": Decimal("100"),
            "min_weight": 0,
            "max_weight": 999999,
        },
        {
            "name": "CEL-FBP-Eco-Low-KZ",
            "type": "land",
            "fulfillment_type": "fbp",
            "destination": "KZ",
            "fbp_company": "CEL",
            "fbp_service_level": "economy",
            "base_fee": Decimal("30"),
            "min_weight": 0,
            "max_weight": 999999,
        },
    ]

    def mock_calc(_product, land, air, mode="fast", priority="低价优先"):
        return _make_calc_result(best_land_name="CEL-FBP-Eco-High-KZ")

    def mock_cost_and_filter(
        logistic_list,
        product,
        land_logistics,
        cached_cost,
        unit_price,
        labeling_fee,
        shipping_fee,
        rate,
        filtered_logistics,
        all_costs_debug,
    ):
        cost_map = {
            "CEL-FBP-Eco-High-KZ": Decimal("1.0"),
            "CEL-FBP-Eco-Low-KZ": Decimal("2.0"),
        }
        result = []
        for lg in logistic_list:
            d = lg if isinstance(lg, dict) else dict(lg)
            name = d.get("name", "")
            if name in cost_map:
                result.append((dict(d), cost_map[name]))
        return result

    with (
        patch(
            "pricing.fbp_secondary_filter.fbp_secondary_filter",
            side_effect=lambda items: (list(items), []),
        ),
        patch(
            "pricing.grouped_pricing.cost_and_filter",
            side_effect=mock_cost_and_filter,
        ),
        patch(
            "pricing.grouped_pricing._get_exchange_rates",
            return_value=(Decimal("0.09"), Decimal("7.2")),
        ),
        patch(
            "pricing.calculate_pricing.calculate_pricing",
            side_effect=mock_calc,
        ),
    ):
        result = calculate_pricing_grouped(
            _product(weight_g=500), logistics, mode="precise"
        )

    filtered = result["fbp_cis"]["filtered_logistics"]
    all_items = filtered["land"] + filtered["air"]
    low = [i for i in all_items if i.get("name") == "CEL-FBP-Eco-Low-KZ"]
    assert len(low) == 1, f"Expected 1 entry, got {low}"
    assert (
        low[0]["reason"]
        == "未被选中，物流成本 ¥2.00（已选更优方案：CEL-FBP-Eco-High-KZ ¥1.00）"
    )


def test_selected_logistics_not_in_eliminated():
    logistics = [
        {
            "name": "RETS-FBP-Std-Best-BY",
            "type": "air",
            "fulfillment_type": "fbp",
            "destination": "BY",
            "fbp_company": "RETS",
            "fbp_service_level": "standard",
            "base_fee": Decimal("100"),
            "min_weight": 0,
            "max_weight": 999999,
        },
        {
            "name": "RETS-FBP-Std-Other-BY",
            "type": "air",
            "fulfillment_type": "fbp",
            "destination": "BY",
            "fbp_company": "RETS",
            "fbp_service_level": "standard",
            "base_fee": Decimal("50"),
            "min_weight": 0,
            "max_weight": 999999,
        },
    ]

    def mock_calc(_product, land, air, mode="fast", priority="低价优先"):
        return _make_calc_result(best_air_name="RETS-FBP-Std-Best-BY")

    def mock_cost_and_filter(
        logistic_list,
        product,
        land_logistics,
        cached_cost,
        unit_price,
        labeling_fee,
        shipping_fee,
        rate,
        filtered_logistics,
        all_costs_debug,
    ):
        cost_map = {
            "RETS-FBP-Std-Best-BY": Decimal("1.0"),
            "RETS-FBP-Std-Other-BY": Decimal("2.0"),
        }
        result = []
        for lg in logistic_list:
            d = lg if isinstance(lg, dict) else dict(lg)
            name = d.get("name", "")
            if name in cost_map:
                result.append((dict(d), cost_map[name]))
        return result

    with (
        patch(
            "pricing.fbp_secondary_filter.fbp_secondary_filter",
            side_effect=lambda items: (list(items), []),
        ),
        patch(
            "pricing.grouped_pricing.cost_and_filter",
            side_effect=mock_cost_and_filter,
        ),
        patch(
            "pricing.grouped_pricing._get_exchange_rates",
            return_value=(Decimal("0.09"), Decimal("7.2")),
        ),
        patch(
            "pricing.calculate_pricing.calculate_pricing",
            side_effect=mock_calc,
        ),
    ):
        result = calculate_pricing_grouped(
            _product(weight_g=500), logistics, mode="precise"
        )

    filtered = result["fbp_cis"]["filtered_logistics"]
    all_items = filtered["land"] + filtered["air"]
    all_names = [i.get("name") for i in all_items]
    assert "RETS-FBP-Std-Best-BY" not in all_names
    other = [i for i in all_items if i.get("name") == "RETS-FBP-Std-Other-BY"]
    assert len(other) == 1
    assert (
        other[0]["reason"]
        == "未被选中，物流成本 ¥2.00（已选更优方案：RETS-FBP-Std-Best-BY ¥1.00）"
    )


def test_dimension_fail_shows_dimension_reason():
    logistics = [
        {
            "name": "RETS-FBP-Std-Wide-BY",
            "type": "air",
            "fulfillment_type": "fbp",
            "destination": "BY",
            "fbp_company": "RETS",
            "fbp_service_level": "standard",
            "base_fee": Decimal("100"),
            "min_weight": 0,
            "max_weight": 999999,
        },
        {
            "name": "RETS-FBP-Std-Narrow-BY",
            "type": "air",
            "fulfillment_type": "fbp",
            "destination": "BY",
            "fbp_company": "RETS",
            "fbp_service_level": "standard",
            "base_fee": Decimal("40"),
            "min_weight": 0,
            "max_weight": 999999,
            "max_longest_side": 5,
        },
    ]

    wide_only = [(dict(logistics[0]), Decimal("3.0"))]
    dim_fail = [
        {"name": "RETS-FBP-Std-Narrow-BY", "reason": "最长边 10 cm 超过限制 5 cm"}
    ]
    stage1_se = _make_stage1_side_effect(
        [],
        wide_only,
        air_eliminated=dim_fail,
    )

    def mock_calc(_product, land, air, mode="fast", priority="低价优先"):
        best = (
            "RETS-FBP-Std-Wide-BY"
            if any(r.get("name") == "RETS-FBP-Std-Wide-BY" for r in (air or []))
            else None
        )
        return _make_calc_result(best_air_name=best)

    with (
        patch(
            "pricing.calculate_pricing._run_filters",
            side_effect=stage1_se,
        ),
        patch(
            "pricing.grouped_pricing._get_exchange_rates",
            return_value=(Decimal("0.09"), Decimal("7.2")),
        ),
        patch(
            "pricing.calculate_pricing.calculate_pricing",
            side_effect=mock_calc,
        ),
    ):
        result = calculate_pricing_grouped(
            _product(weight_g=500), logistics, mode="precise"
        )

    filtered = result["fbp_cis"]["filtered_logistics"]
    all_items = filtered["land"] + filtered["air"]
    narrow = [i for i in all_items if i.get("name") == "RETS-FBP-Std-Narrow-BY"]
    assert len(narrow) == 1, f"Expected 1 entry, got {narrow}"
    reason = narrow[0]["reason"]
    assert "超过限制" in reason, (
        f"Expected dimension reason containing '超过限制', got: {reason}"
    )
    assert reason != _FBP_ELIMINATED_REASON
