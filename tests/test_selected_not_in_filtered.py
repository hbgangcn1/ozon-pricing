"""
Tests: selected (winner) logistics must NOT appear in filtered_logistics.

Bug: In grouped pricing, a logistics selected under one priority
(e.g. low-price) could appear in filtered_logistics from the other
priority (e.g. speed), because _group() merged filtered lists without
excluding selected names.
"""

import importlib
from decimal import Decimal
from unittest.mock import patch

calc_module = importlib.import_module("pricing.calculate_pricing")


def _product():
    return {
        "unit_price": Decimal("10.0"),
        "labeling_fee": Decimal("1.0"),
        "shipping_fee": Decimal("2.0"),
        "promotion_cost_rate": Decimal("0.1"),
        "commission_rate": Decimal("0.1"),
        "withdrawal_fee_rate": Decimal("0.02"),
        "payment_processing_fee": Decimal("0.0"),
        "target_profit_margin": Decimal("0.2"),
        "weight_g": 500,
        "length_cm": 20,
        "width_cm": 15,
        "height_cm": 10,
    }


def _logistics(name, ltype="land", **overrides):
    base = {
        "name": name,
        "type": ltype,
        "delivery_method": "pickup",
        "min_days": 5,
        "max_days": 8,
        "fee_mode": "base_plus_continue",
        "continue_unit": 100,
        "continue_fee": Decimal("0.5"),
        "base_fee": Decimal("8.0"),
        "min_weight": 0,
        "max_weight": 5000,
        "max_sum_of_sides": 500,
        "max_longest_side": 300,
        "price_limit_cny": Decimal("1000000"),
        "price_min_cny": Decimal("0"),
        "priority_group": "A",
        "volume_mode": "none",
        "fulfillment_type": "rfbs",
        "destination": "RU",
    }
    base.update(overrides)
    return base


def _selected_names(group_result):
    """Collect all selected logistics names from a group result."""
    names = set()
    for pkey in ("price_priority", "speed_priority"):
        r = group_result.get(pkey, {})
        for bkey in ("best_land", "best_air"):
            val = r.get(bkey)
            if isinstance(val, dict):
                n = val.get("name")
                if n:
                    names.add(n)
            elif isinstance(val, str) and val:
                names.add(val)
    return names


def _filtered_names(group_result):
    """Collect all filtered logistics names from merged filtered list."""
    fl = group_result.get("filtered_logistics", {"land": [], "air": []})
    return {item["name"] for items in fl.values() for item in items}


@patch.object(
    calc_module,
    "_get_exchange_rates",
    return_value=(Decimal("0.0904"), Decimal("7.2")),
)
def test_selected_land_not_in_filtered(_mock_rate):
    """Winner from one priority must not appear in filtered list."""
    cheap = _logistics("Cheap-Land", base_fee=Decimal("5.0"), min_days=10, max_days=15)
    fast = _logistics("Fast-Land", base_fee=Decimal("15.0"), min_days=2, max_days=4)
    result = calc_module.calculate_pricing_grouped(
        _product(),
        [cheap, fast],
        mode="precise",
    )
    group = result.get("rfbs_ru", {})
    selected = _selected_names(group)
    filtered = _filtered_names(group)
    overlap = selected & filtered
    assert not overlap, f"Selected logistics found in filtered list: {overlap}"


@patch.object(
    calc_module,
    "_get_exchange_rates",
    return_value=(Decimal("0.0904"), Decimal("7.2")),
)
def test_selected_air_not_in_filtered(_mock_rate):
    """Air winner from one priority must not appear in filtered list."""
    cheap = _logistics(
        "Cheap-Air",
        ltype="air",
        base_fee=Decimal("5.0"),
        min_days=10,
        max_days=15,
    )
    fast = _logistics(
        "Fast-Air",
        ltype="air",
        base_fee=Decimal("15.0"),
        min_days=2,
        max_days=4,
    )
    result = calc_module.calculate_pricing_grouped(
        _product(),
        [cheap, fast],
        mode="precise",
    )
    group = result.get("rfbs_ru", {})
    selected = _selected_names(group)
    filtered = _filtered_names(group)
    overlap = selected & filtered
    assert not overlap, f"Selected air logistics in filtered list: {overlap}"


@patch.object(
    calc_module,
    "_get_exchange_rates",
    return_value=(Decimal("0.0904"), Decimal("7.2")),
)
def test_three_logistics_winner_excluded_from_filtered(_mock_rate):
    """With 3 options, both priority winners excluded from filtered."""
    cheap = _logistics("Budget", base_fee=Decimal("4.0"), min_days=12, max_days=18)
    mid = _logistics("Standard", base_fee=Decimal("9.0"), min_days=6, max_days=9)
    fast = _logistics("Express", base_fee=Decimal("18.0"), min_days=2, max_days=3)
    result = calc_module.calculate_pricing_grouped(
        _product(),
        [cheap, mid, fast],
        mode="precise",
    )
    group = result.get("rfbs_ru", {})
    selected = _selected_names(group)
    filtered = _filtered_names(group)
    overlap = selected & filtered
    assert not overlap, f"Selected logistics in filtered list: {overlap}"
    assert len(selected) >= 1, "Should have at least one selected"


@patch.object(
    calc_module,
    "_get_exchange_rates",
    return_value=(Decimal("0.0904"), Decimal("7.2")),
)
def test_cis_group_winner_not_in_filtered(_mock_rate):
    """CIS group winners also excluded from filtered list."""
    cheap = _logistics(
        "CIS-Cheap",
        base_fee=Decimal("5.0"),
        min_days=10,
        max_days=15,
        fulfillment_type="fbp",
        destination="KZ",
    )
    fast = _logistics(
        "CIS-Fast",
        base_fee=Decimal("15.0"),
        min_days=2,
        max_days=4,
        fulfillment_type="fbp",
        destination="KZ",
    )
    result = calc_module.calculate_pricing_grouped(
        _product(),
        [cheap, fast],
        mode="precise",
    )
    group = result.get("fbp_cis", {})
    if group:
        selected = _selected_names(group)
        filtered = _filtered_names(group)
        overlap = selected & filtered
        assert not overlap, f"CIS selected logistics in filtered: {overlap}"


@patch.object(
    calc_module,
    "_get_exchange_rates",
    return_value=(Decimal("0.0904"), Decimal("7.2")),
)
def test_non_selected_still_in_filtered(_mock_rate):
    """Non-winner logistics should still appear in filtered list."""
    cheap = _logistics("Budget", base_fee=Decimal("4.0"), min_days=12, max_days=18)
    mid = _logistics("Standard", base_fee=Decimal("9.0"), min_days=6, max_days=9)
    fast = _logistics("Express", base_fee=Decimal("18.0"), min_days=2, max_days=3)
    result = calc_module.calculate_pricing_grouped(
        _product(),
        [cheap, mid, fast],
        mode="precise",
    )
    group = result.get("rfbs_ru", {})
    selected = _selected_names(group)
    filtered = _filtered_names(group)
    non_selected = {"Budget", "Standard", "Express"} - selected
    for name in non_selected:
        assert name in filtered, f"Non-winner '{name}' should be in filtered list"
