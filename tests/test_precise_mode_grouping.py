"""Tests for grouping independence in precise pricing mode.

Verifies that each group in calculate_pricing_grouped() receives ONLY
logistics matching its fulfillment_type + destination, and that groups
are completely isolated from each other.
"""

import os
import sys
from decimal import Decimal
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pricing.calculate_pricing import calculate_pricing_grouped  # noqa: E402


def _product():
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
    }


def _all_logistics():
    """Build logistics covering all 9 groups with distinguishable names."""
    return [
        {
            "name": "L-rfbs-RU",
            "type": "land",
            "fulfillment_type": "rfbs",
            "destination": "RU",
        },
        {
            "name": "A-rfbs-RU",
            "type": "air",
            "fulfillment_type": "rfbs",
            "destination": "RU",
        },
        {
            "name": "L-fbp-RU",
            "type": "land",
            "fulfillment_type": "fbp",
            "destination": "RU",
            "fbp_company": "UNI",
            "fbp_service_level": "standard",
        },
        {
            "name": "A-fbp-RU",
            "type": "air",
            "fulfillment_type": "fbp",
            "destination": "RU",
            "fbp_company": "UNI",
            "fbp_service_level": "standard",
        },
        {
            "name": "L-fbp-KZ",
            "type": "land",
            "fulfillment_type": "fbp",
            "destination": "KZ",
            "fbp_company": "CEL",
            "fbp_service_level": "standard",
        },
        {
            "name": "A-fbp-BY",
            "type": "air",
            "fulfillment_type": "fbp",
            "destination": "BY",
            "fbp_company": "CEL",
            "fbp_service_level": "standard",
        },
        {
            "name": "L-rfbs-KZ",
            "type": "land",
            "fulfillment_type": "rfbs",
            "destination": "KZ",
        },
        {
            "name": "A-rfbs-KZ",
            "type": "air",
            "fulfillment_type": "rfbs",
            "destination": "KZ",
        },
        {
            "name": "L-rfbs-BY",
            "type": "land",
            "fulfillment_type": "rfbs",
            "destination": "BY",
        },
        {
            "name": "L-rfbs-KGZ",
            "type": "land",
            "fulfillment_type": "rfbs",
            "destination": "KGZ",
        },
        {
            "name": "A-rfbs-UZ",
            "type": "air",
            "fulfillment_type": "rfbs",
            "destination": "UZ",
        },
        {
            "name": "L-rfbs-GE",
            "type": "land",
            "fulfillment_type": "rfbs",
            "destination": "GE",
        },
        {
            "name": "A-rfbs-AZ",
            "type": "air",
            "fulfillment_type": "rfbs",
            "destination": "AZ",
        },
        {
            "name": "A-rfbs-AM",
            "type": "air",
            "fulfillment_type": "rfbs",
            "destination": "AM",
        },
    ]


_call_log = []


def _recording_calculate(_product, land, air, mode="fast", priority="低价优先"):
    """Record land/air inputs per call, return empty result."""
    _call_log.append(
        {
            "land": [r["name"] for r in land],
            "air": [r["name"] for r in air],
            "mode": mode,
            "priority": priority,
        }
    )
    return {"filtered_logistics": {"land": [], "air": []}}


def _run_grouped():
    """Run calculate_pricing_grouped and return (result, call_log)."""
    _call_log.clear()
    with (
        patch(
            "pricing.calculate_pricing.calculate_pricing",
            side_effect=_recording_calculate,
        ),
        patch(
            "pricing.fbp_secondary_filter.fbp_secondary_filter",
            side_effect=lambda rows: (list(rows), []),
        ),
    ):
        result = calculate_pricing_grouped(_product(), _all_logistics(), mode="precise")
    return result, list(_call_log)


def _calls_for_group(call_log, expected_land, expected_air):
    """Find the pair of calls (price+speed priority) matching expected inputs."""
    matches = []
    for c in call_log:
        if sorted(c["land"]) == sorted(expected_land) and sorted(c["air"]) == sorted(
            expected_air
        ):
            matches.append(c)
    return matches


def test_rfbs_ru_only_receives_rfbs_ru_logistics():
    _, calls = _run_grouped()
    matches = _calls_for_group(calls, ["L-rfbs-RU"], ["A-rfbs-RU"])
    assert len(matches) == 2
    priorities = {m["priority"] for m in matches}
    assert priorities == {"低价优先", "速度优先"}


def test_fbp_ru_only_receives_fbp_ru_logistics():
    _, calls = _run_grouped()
    matches = _calls_for_group(calls, ["L-fbp-RU"], ["A-fbp-RU"])
    assert len(matches) == 2


def test_fbp_cis_only_receives_fbp_kz_by_logistics():
    _, calls = _run_grouped()
    matches = _calls_for_group(calls, ["L-fbp-KZ"], ["A-fbp-BY"])
    assert len(matches) == 2


def test_rfbs_kz_only_receives_rfbs_kz_logistics():
    _, calls = _run_grouped()
    matches = _calls_for_group(calls, ["L-rfbs-KZ"], ["A-rfbs-KZ"])
    assert len(matches) == 2


def test_rfbs_by_only_receives_rfbs_by_logistics():
    _, calls = _run_grouped()
    matches = _calls_for_group(calls, ["L-rfbs-BY"], [])
    assert len(matches) == 2


def test_rfbs_kgz_only_receives_rfbs_kgz_logistics():
    _, calls = _run_grouped()
    matches = _calls_for_group(calls, ["L-rfbs-KGZ"], [])
    assert len(matches) == 2


def test_rfbs_uz_only_receives_rfbs_uz_logistics():
    _, calls = _run_grouped()
    matches = _calls_for_group(calls, [], ["A-rfbs-UZ"])
    assert len(matches) == 2


def test_rfbs_ge_only_receives_rfbs_ge_logistics():
    _, calls = _run_grouped()
    matches = _calls_for_group(calls, ["L-rfbs-GE"], [])
    assert len(matches) == 2


def test_rfbs_az_only_receives_rfbs_az_logistics():
    _, calls = _run_grouped()
    matches = _calls_for_group(calls, [], ["A-rfbs-AZ"])
    assert len(matches) == 2


def test_total_call_count_is_2x_groups():
    """Each of 10 groups calls calculate_pricing twice (price + speed)."""
    _, calls = _run_grouped()
    assert len(calls) == 20


def test_all_calls_use_precise_mode():
    _, calls = _run_grouped()
    for c in calls:
        assert c["mode"] == "precise"


def test_no_logistics_leak_between_groups():
    """Verify no logistics name appears in a group it doesn't belong to."""
    _, calls = _run_grouped()

    group_expectations = {
        "rfbs_RU": ({"L-rfbs-RU"}, {"A-rfbs-RU"}),
        "fbp_RU": ({"L-fbp-RU"}, {"A-fbp-RU"}),
        "fbp_CIS": ({"L-fbp-KZ"}, {"A-fbp-BY"}),
        "rfbs_KZ": ({"L-rfbs-KZ"}, {"A-rfbs-KZ"}),
        "rfbs_BY": ({"L-rfbs-BY"}, set()),
        "rfbs_KGZ": ({"L-rfbs-KGZ"}, set()),
        "rfbs_UZ": (set(), {"A-rfbs-UZ"}),
        "rfbs_GE": ({"L-rfbs-GE"}, set()),
        "rfbs_AZ": (set(), {"A-rfbs-AZ"}),
        "rfbs_AM": (set(), {"A-rfbs-AM"}),
    }

    all_expected = []
    for exp_land, exp_air in group_expectations.values():
        all_expected.append((sorted(exp_land), sorted(exp_air)))

    for call in calls:
        land_set = sorted(call["land"])
        air_set = sorted(call["air"])
        assert (land_set, air_set) in all_expected, (
            f"Unexpected call with land={land_set}, air={air_set}"
        )


def test_commission_applied_per_group_fulfillment_type():
    """When commission_category is provided, _apply_commission uses
    the group's fulfillment_type."""
    products_seen = []

    def _capture_product(product, land, air, mode="fast", priority="低价优先"):
        products_seen.append(dict(product))
        return {"filtered_logistics": {"land": [], "air": []}}

    commission_cat = {
        "rfbs_tier1_rate": Decimal("0.12"),
        "rfbs_tier2_rate": Decimal("0.18"),
        "rfbs_tier3_rate": Decimal("0.18"),
        "fbp_tier1_rate": Decimal("0.11"),
        "fbp_tier2_rate": Decimal("0.17"),
        "fbp_tier3_rate": Decimal("0.17"),
    }

    with (
        patch(
            "pricing.calculate_pricing.calculate_pricing",
            side_effect=_capture_product,
        ),
        patch(
            "pricing.fbp_secondary_filter.fbp_secondary_filter",
            side_effect=lambda rows: (list(rows), []),
        ),
    ):
        calculate_pricing_grouped(
            _product(),
            _all_logistics(),
            mode="precise",
            commission_category=commission_cat,
        )

    assert len(products_seen) == 20

    for i, p in enumerate(products_seen):
        rate = p["commission_rate"]
        if rate != Decimal("0.08"):
            if i < 4:
                pass

    rates = {p["commission_rate"] for p in products_seen}
    assert len(rates) >= 2, (
        f"Expected at least 2 distinct rates (rfbs vs fbp), got {rates}"
    )
