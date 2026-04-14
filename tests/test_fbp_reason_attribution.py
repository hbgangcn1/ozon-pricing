"""Regression tests for FBP eliminated-logistics reason attribution.

Verifies that when the post-pricing FBP filter runs:
  - Logistics eliminated by the first filter (weight/dimension/price)
    keep their original first-filter reason.
  - Logistics that pass the first filter but belong to the same
    (company, service_level) group as a selected logistics
    are tagged with the secondary reason "该物流无法覆盖更高成本".
  - Selected logistics (best_land/best_air) are never shown
    in the eliminated list.
"""

import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pricing.calculate_pricing import calculate_pricing_grouped  # noqa: E402


_FBP_ELIMINATED_REASON = "该物流无法覆盖更高成本"


def _product(weight_g=379):
    return {
        "unit_price": 100.0,
        "labeling_fee": 0.5,
        "shipping_fee": 1.0,
        "commission_rate": 0.08,
        "target_profit_margin": 0.2,
        "promotion_cost_rate": 0.03,
        "withdrawal_fee_rate": 0.01,
        "payment_processing_fee": 0.02,
        "return_rate": 0,
        "vat_rate": 20,
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


def test_weight_fail_shows_weight_reason_not_secondary():
    """A logistic eliminated by the first filter (weight check) shows
    weight reason, not the secondary reason, even if it's in the same
    group as a selected logistic."""
    logistics = [
        {
            "name": "GUOO-FBP-Std-Small-KZ",
            "type": "land",
            "fulfillment_type": "fbp",
            "destination": "KZ",
            "fbp_company": "GUOO",
            "fbp_service_level": "standard",
            "base_rate": 100,
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
            "base_rate": 50,
            "min_weight": 5001,
            "max_weight": 999999,
        },
    ]

    def mock_calc(_product, land, air, mode="fast", priority="低价优先"):
        land_names = {r.get("name") for r in (land or [])}
        filtered_land = []
        if "GUOO-FBP-Std-Big-KZ" in land_names:
            filtered_land.append(
                {
                    "name": "GUOO-FBP-Std-Big-KZ",
                    "reason": "重量 379 g 低于下限 5001 g",
                }
            )
        best = (
            "GUOO-FBP-Std-Small-KZ" if "GUOO-FBP-Std-Small-KZ" in land_names else None
        )
        return _make_calc_result(
            best_land_name=best,
            filtered_land=filtered_land,
        )

    with (
        patch(
            "pricing.fbp_secondary_filter.fbp_secondary_filter",
            side_effect=lambda items: (list(items), []),
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
    """A logistic that passes the first filter but is in the same group
    as a selected logistic is now shown as Stage 3 unselected."""
    logistics = [
        {
            "name": "CEL-FBP-Eco-High-KZ",
            "type": "land",
            "fulfillment_type": "fbp",
            "destination": "KZ",
            "fbp_company": "CEL",
            "fbp_service_level": "economy",
            "base_rate": 100,
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
            "base_rate": 30,
            "min_weight": 0,
            "max_weight": 999999,
        },
    ]

    def mock_calc(_product, land, air, mode="fast", priority="低价优先"):
        return _make_calc_result(best_land_name="CEL-FBP-Eco-High-KZ")

    def mock_run_filters(*_args, **_kwargs):
        return (
            [(dict(logistics[0]), 1.0), (dict(logistics[1]), 2.0)],
            [],
            (None, None),
            (None, None),
            [],
        )

    with (
        patch(
            "pricing.fbp_secondary_filter.fbp_secondary_filter",
            side_effect=lambda items: (list(items), []),
        ),
        patch(
            "pricing.calculate_pricing._run_filters",
            side_effect=mock_run_filters,
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
    assert low[0]["reason"] == "未被选中，物流成本 ¥2.00"


def test_selected_logistics_not_in_eliminated():
    """Selected logistics must NOT appear in the eliminated list."""
    logistics = [
        {
            "name": "RETS-FBP-Std-Best-BY",
            "type": "air",
            "fulfillment_type": "fbp",
            "destination": "BY",
            "fbp_company": "RETS",
            "fbp_service_level": "standard",
            "base_rate": 100,
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
            "base_rate": 50,
            "min_weight": 0,
            "max_weight": 999999,
        },
    ]

    def mock_calc(_product, land, air, mode="fast", priority="低价优先"):
        return _make_calc_result(best_air_name="RETS-FBP-Std-Best-BY")

    def mock_run_filters(*_args, **_kwargs):
        return (
            [],
            [(dict(logistics[0]), 1.0), (dict(logistics[1]), 2.0)],
            (None, None),
            (None, None),
            [],
        )

    with (
        patch(
            "pricing.fbp_secondary_filter.fbp_secondary_filter",
            side_effect=lambda items: (list(items), []),
        ),
        patch(
            "pricing.calculate_pricing._run_filters",
            side_effect=mock_run_filters,
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
    assert other[0]["reason"] == "未被选中，物流成本 ¥2.00"


def test_dimension_fail_shows_dimension_reason():
    """A logistic eliminated by dimension check shows the dimension
    reason, not the secondary reason."""
    logistics = [
        {
            "name": "RETS-FBP-Std-Wide-BY",
            "type": "air",
            "fulfillment_type": "fbp",
            "destination": "BY",
            "fbp_company": "RETS",
            "fbp_service_level": "standard",
            "base_rate": 100,
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
            "base_rate": 40,
            "min_weight": 0,
            "max_weight": 999999,
            "max_longest_side": 5,
        },
    ]

    def mock_calc(_product, land, air, mode="fast", priority="低价优先"):
        air_names = {r.get("name") for r in (air or [])}
        filtered_air = []
        if "RETS-FBP-Std-Narrow-BY" in air_names:
            filtered_air.append(
                {
                    "name": "RETS-FBP-Std-Narrow-BY",
                    "reason": "最长边 10 cm 超过限制 5 cm",
                }
            )
        best = "RETS-FBP-Std-Wide-BY" if "RETS-FBP-Std-Wide-BY" in air_names else None
        return _make_calc_result(
            best_air_name=best,
            filtered_air=filtered_air,
        )

    with (
        patch(
            "pricing.fbp_secondary_filter.fbp_secondary_filter",
            side_effect=lambda items: (list(items), []),
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
