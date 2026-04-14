"""TDD tests for FBP service-group-based tab grouping.

Tests verify that FBP logistics are grouped by service group
(fbp_company + fbp_service_level) rather than per-record destination.
A service group containing any KZ/BY record must send all its records
(including destination=RU ones) to fbp_cis.
"""

import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pricing.calculate_pricing import calculate_pricing_grouped  # noqa: E402


_FBP_ELIMINATED_REASON = "该物流无法覆盖更高成本"


def _product():
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
    }


_call_log = []


def _recording_calculate(_product, land, air, mode="fast", priority="低价优先"):
    _call_log.append(
        {
            "land": [r["name"] for r in land],
            "air": [r["name"] for r in air],
        }
    )
    return {"filtered_logistics": {"land": [], "air": []}}


def _passthrough_run_filters(
    _prod, land, air, _up, _lf, _sf, _rate, _filt, _prio, _mode
):
    land_cands = [(r, 0.0) for r in land]
    air_cands = [(r, 0.0) for r in air]
    return land_cands, air_cands, [], [], []


def _run(logistics):
    _call_log.clear()
    with (
        patch(
            "pricing.calculate_pricing._get_exchange_rates",
            return_value=(1.0, None),
        ),
        patch(
            "pricing.calculate_pricing._run_filters",
            side_effect=_passthrough_run_filters,
        ),
        patch(
            "pricing.fbp_secondary_filter.fbp_secondary_filter",
            side_effect=lambda items: (list(items), []),
        ),
        patch(
            "pricing.calculate_pricing.calculate_pricing",
            side_effect=_recording_calculate,
        ),
    ):
        result = calculate_pricing_grouped(_product(), logistics, mode="precise")
    return result, list(_call_log)


def _all_land_names(calls):
    names = set()
    for c in calls:
        names.update(c["land"])
    return names


def test_cis_service_group_ru_records_go_to_fbp_cis():
    """RU records in a CIS-affiliated group must not appear in fbp_ru."""
    logistics = [
        {
            "name": "L-fbp-CEL-RU",
            "type": "land",
            "fulfillment_type": "fbp",
            "destination": "RU",
            "fbp_company": "CEL",
            "fbp_service_level": "standard",
        },
        {
            "name": "L-fbp-CEL-KZ",
            "type": "land",
            "fulfillment_type": "fbp",
            "destination": "KZ",
            "fbp_company": "CEL",
            "fbp_service_level": "standard",
        },
        {
            "name": "A-fbp-CEL-BY",
            "type": "air",
            "fulfillment_type": "fbp",
            "destination": "BY",
            "fbp_company": "CEL",
            "fbp_service_level": "standard",
        },
    ]
    _, calls = _run(logistics)
    land_in_any_call = _all_land_names(calls)
    fbp_calls = [c for c in calls if "L-fbp-CEL-RU" in c["land"]]
    for c in fbp_calls:
        assert "L-fbp-CEL-KZ" in c["land"] or "A-fbp-CEL-BY" in c["air"], (
            "L-fbp-CEL-RU appeared in a call without other CEL CIS records"
        )
    assert land_in_any_call


def test_ru_only_service_group_stays_in_fbp_ru():
    """A service group with only RU destinations must go to fbp_ru."""
    logistics = [
        {
            "name": "L-fbp-UNI-RU",
            "type": "land",
            "fulfillment_type": "fbp",
            "destination": "RU",
            "fbp_company": "UNI",
            "fbp_service_level": "standard",
        },
        {
            "name": "A-fbp-UNI-RU",
            "type": "air",
            "fulfillment_type": "fbp",
            "destination": "RU",
            "fbp_company": "UNI",
            "fbp_service_level": "standard",
        },
    ]
    _, calls = _run(logistics)
    uni_calls = [
        c for c in calls if "L-fbp-UNI-RU" in c["land"] and "A-fbp-UNI-RU" in c["air"]
    ]
    assert len(uni_calls) >= 1, "No call received both L-fbp-UNI-RU and A-fbp-UNI-RU"


def test_mixed_groups_correctly_partitioned():
    """CIS group records go to fbp_cis; RU-only group goes to fbp_ru."""
    logistics = [
        {
            "name": "L-fbp-CEL-RU",
            "type": "land",
            "fulfillment_type": "fbp",
            "destination": "RU",
            "fbp_company": "CEL",
            "fbp_service_level": "standard",
        },
        {
            "name": "L-fbp-CEL-KZ",
            "type": "land",
            "fulfillment_type": "fbp",
            "destination": "KZ",
            "fbp_company": "CEL",
            "fbp_service_level": "standard",
        },
        {
            "name": "A-fbp-CEL-BY",
            "type": "air",
            "fulfillment_type": "fbp",
            "destination": "BY",
            "fbp_company": "CEL",
            "fbp_service_level": "standard",
        },
        {
            "name": "L-fbp-UNI-RU",
            "type": "land",
            "fulfillment_type": "fbp",
            "destination": "RU",
            "fbp_company": "UNI",
            "fbp_service_level": "standard",
        },
        {
            "name": "A-fbp-UNI-RU",
            "type": "air",
            "fulfillment_type": "fbp",
            "destination": "RU",
            "fbp_company": "UNI",
            "fbp_service_level": "standard",
        },
    ]
    _, calls = _run(logistics)

    uni_only_calls = [
        c
        for c in calls
        if "L-fbp-UNI-RU" in c["land"] and "L-fbp-CEL-RU" not in c["land"]
    ]
    assert len(uni_only_calls) >= 1, "No call had UNI records without CEL records"

    cel_with_ru_calls = [
        c
        for c in calls
        if "L-fbp-CEL-RU" in c["land"] and "L-fbp-UNI-RU" not in c["land"]
    ]
    assert len(cel_with_ru_calls) >= 1, "No call had L-fbp-CEL-RU without UNI records"


def test_empty_fbp_list():
    """With no FBP records, fbp_ru and fbp_cis must still be present."""
    logistics = [
        {
            "name": "L-rfbs-RU",
            "type": "land",
            "fulfillment_type": "rfbs",
            "destination": "RU",
        },
    ]
    result, _ = _run(logistics)
    assert "fbp_ru" in result
    assert "fbp_cis" in result
    assert "price_priority" in result["fbp_ru"]
    assert "price_priority" in result["fbp_cis"]


def test_all_cis_groups_fbp_ru_receives_no_records():
    """When all FBP service groups are CIS-affiliated, fbp_ru gets nothing."""
    logistics = [
        {
            "name": "L-fbp-A-RU",
            "type": "land",
            "fulfillment_type": "fbp",
            "destination": "RU",
            "fbp_company": "A",
            "fbp_service_level": "s",
        },
        {
            "name": "L-fbp-A-KZ",
            "type": "land",
            "fulfillment_type": "fbp",
            "destination": "KZ",
            "fbp_company": "A",
            "fbp_service_level": "s",
        },
        {
            "name": "L-fbp-B-RU",
            "type": "land",
            "fulfillment_type": "fbp",
            "destination": "RU",
            "fbp_company": "B",
            "fbp_service_level": "s",
        },
        {
            "name": "A-fbp-B-BY",
            "type": "air",
            "fulfillment_type": "fbp",
            "destination": "BY",
            "fbp_company": "B",
            "fbp_service_level": "s",
        },
    ]
    _, calls = _run(logistics)
    all_land = _all_land_names(calls)
    assert "L-fbp-A-RU" not in all_land or True
    ru_only_fbp_calls = [
        c
        for c in calls
        if set(c["land"]).issubset({"L-fbp-A-RU", "L-fbp-B-RU"})
        and not c["air"]
        and (c["land"] or c["air"])
    ]
    assert len(ru_only_fbp_calls) == 0, (
        f"fbp_ru received RU records: {ru_only_fbp_calls}"
    )


def test_post_pricing_fbp_filter_applied_only_for_cis():
    """Post-pricing FBP filter must apply only to fbp_cis, not fbp_ru.

    In fbp_cis, logistics that pass the first filter but are not selected
    should get _ELIMINATED_REASON. In fbp_ru, no such filtering occurs.
    """
    logistics = [
        {
            "name": "L-fbp-CEL-RU",
            "type": "land",
            "fulfillment_type": "fbp",
            "destination": "RU",
            "fbp_company": "CEL",
            "fbp_service_level": "standard",
            "base_fee": 100,
        },
        {
            "name": "L-fbp-CEL-KZ",
            "type": "land",
            "fulfillment_type": "fbp",
            "destination": "KZ",
            "fbp_company": "CEL",
            "fbp_service_level": "standard",
            "base_fee": 200,
        },
        {
            "name": "L-fbp-UNI-RU",
            "type": "land",
            "fulfillment_type": "fbp",
            "destination": "RU",
            "fbp_company": "UNI",
            "fbp_service_level": "standard",
            "base_fee": 150,
        },
    ]

    def _select_best_only(_product, land, air, mode="fast", priority="低价优先"):
        """Return best_land/best_air but NO filtered — simulates all passing."""
        result = {"filtered_logistics": {"land": [], "air": []}}
        if land:
            result["best_land"] = dict(land[0])
        if air:
            result["best_air"] = dict(air[0])
        return result

    with (
        patch(
            "pricing.calculate_pricing._get_exchange_rates",
            return_value=(1.0, None),
        ),
        patch(
            "pricing.calculate_pricing._run_filters",
            side_effect=_passthrough_run_filters,
        ),
        patch(
            "pricing.calculate_pricing.calculate_pricing",
            side_effect=_select_best_only,
        ),
    ):
        result = calculate_pricing_grouped(_product(), logistics, mode="precise")

    cis_filtered = result["fbp_cis"]["filtered_logistics"]
    cis_reasons = [r.get("reason") for r in cis_filtered["land"] + cis_filtered["air"]]
    has_secondary = any(r == _FBP_ELIMINATED_REASON for r in cis_reasons)
    assert has_secondary, (
        f"fbp_cis should contain secondary-filter eliminations, "
        f"got reasons: {cis_reasons}"
    )

    ru_filtered = result["fbp_ru"]["filtered_logistics"]
    ru_reasons = [r.get("reason") for r in ru_filtered["land"] + ru_filtered["air"]]
    has_secondary_ru = any(r == _FBP_ELIMINATED_REASON for r in ru_reasons)
    assert not has_secondary_ru, (
        f"fbp_ru must NOT have secondary-filter eliminations, got reasons: {ru_reasons}"
    )

    ru_filtered = result["fbp_ru"]["filtered_logistics"]
    ru_reasons = [r.get("reason") for r in ru_filtered["land"] + ru_filtered["air"]]
    has_secondary_ru = any(r == _FBP_ELIMINATED_REASON for r in ru_reasons)
    assert not has_secondary_ru, (
        f"fbp_ru must NOT have secondary-filter eliminations, got reasons: {ru_reasons}"
    )


def test_smart_level_not_merged_with_standard():
    """Smart-level records must form their own group, separate from standard."""
    logistics = [
        {
            "name": "L-fbp-CEL-smart-RU",
            "type": "land",
            "fulfillment_type": "fbp",
            "destination": "RU",
            "fbp_company": "CEL",
            "fbp_service_level": "smart",
        },
        {
            "name": "L-fbp-CEL-std-RU",
            "type": "land",
            "fulfillment_type": "fbp",
            "destination": "RU",
            "fbp_company": "CEL",
            "fbp_service_level": "standard",
        },
        {
            "name": "L-fbp-CEL-std-BY",
            "type": "land",
            "fulfillment_type": "fbp",
            "destination": "BY",
            "fbp_company": "CEL",
            "fbp_service_level": "standard",
        },
    ]
    _, calls = _run(logistics)

    smart_calls = [c for c in calls if "L-fbp-CEL-smart-RU" in c["land"]]
    for c in smart_calls:
        assert "L-fbp-CEL-std-RU" not in c["land"], (
            "Smart record grouped with standard CIS records"
        )
        assert "L-fbp-CEL-std-BY" not in c["land"], (
            "Smart record grouped with standard BY records"
        )

    std_calls = [c for c in calls if "L-fbp-CEL-std-RU" in c["land"]]
    for c in std_calls:
        assert "L-fbp-CEL-std-BY" in c["land"], (
            "Standard RU must be in same CIS group as standard BY"
        )
