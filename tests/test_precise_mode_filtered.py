import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pricing.calculate_pricing import calculate_pricing_grouped  # noqa: E402


EXPECTED_GROUP_KEYS = [
    "rfbs_ru",
    "fbp_ru",
    "fbp_cis",
    "rfbs_KZ",
    "rfbs_BY",
    "rfbs_KGZ",
    "rfbs_UZ",
    "rfbs_GE",
    "rfbs_AZ",
]

EXPECTED_GROUP_KEY_SET = set(EXPECTED_GROUP_KEYS)


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


def _all_logistics():
    return [
        {
            "name": "Land-RFBS-RU",
            "type": "land",
            "fulfillment_type": "rfbs",
            "destination": "RU",
        },
        {
            "name": "Air-RFBS-RU-1",
            "type": "air",
            "fulfillment_type": "rfbs",
            "destination": "RU",
        },
        {
            "name": "Air-RFBS-RU-2",
            "type": "air",
            "fulfillment_type": "rfbs",
            "destination": "RU",
        },
        {
            "name": "Land-FBP-RU",
            "type": "land",
            "fulfillment_type": "fbp",
            "destination": "RU",
            "fbp_company": "UNI",
            "fbp_service_level": "standard",
        },
        {
            "name": "Air-FBP-RU",
            "type": "air",
            "fulfillment_type": "fbp",
            "destination": "RU",
            "fbp_company": "UNI",
            "fbp_service_level": "standard",
        },
        {
            "name": "Land-FBP-KZ",
            "type": "land",
            "fulfillment_type": "fbp",
            "destination": "KZ",
            "fbp_company": "CEL",
            "fbp_service_level": "standard",
        },
        {
            "name": "Air-FBP-BY",
            "type": "air",
            "fulfillment_type": "fbp",
            "destination": "BY",
            "fbp_company": "CEL",
            "fbp_service_level": "standard",
        },
        {
            "name": "Land-RFBS-KZ",
            "type": "land",
            "fulfillment_type": "rfbs",
            "destination": "KZ",
        },
        {
            "name": "Land-RFBS-BY",
            "type": "land",
            "fulfillment_type": "rfbs",
            "destination": "BY",
        },
        {
            "name": "Air-RFBS-KGZ",
            "type": "air",
            "fulfillment_type": "rfbs",
            "destination": "KGZ",
        },
        {
            "name": "Land-RFBS-UZ",
            "type": "land",
            "fulfillment_type": "rfbs",
            "destination": "UZ",
        },
        {
            "name": "Air-RFBS-GE",
            "type": "air",
            "fulfillment_type": "rfbs",
            "destination": "GE",
        },
        {
            "name": "Land-RFBS-AZ",
            "type": "land",
            "fulfillment_type": "rfbs",
            "destination": "AZ",
        },
    ]


def _names(items):
    return [item["name"] for item in items]


def _empty_filtered(*_args, **_kwargs):
    return {"filtered_logistics": {"land": [], "air": []}}


def _echo_filtered(_product, land, air, mode="fast", priority="低价优先"):
    assert mode == "precise"
    assert priority in {"低价优先", "速度优先"}
    return {
        "filtered_logistics": {
            "land": [dict(item) for item in land],
            "air": [dict(item) for item in air],
        }
    }


def test_returns_expected_group_keys_in_precise_mode():
    with patch(
        "pricing.calculate_pricing.calculate_pricing",
        side_effect=_empty_filtered,
    ):
        result = calculate_pricing_grouped(_product(), _all_logistics(), mode="precise")

    assert set(result.keys()) == EXPECTED_GROUP_KEY_SET


def test_each_group_contains_filtered_logistics_land_and_air_lists():
    with patch(
        "pricing.calculate_pricing.calculate_pricing",
        return_value={},
    ):
        result = calculate_pricing_grouped(_product(), _all_logistics(), mode="precise")

    for group in result.values():
        filtered = group["filtered_logistics"]
        assert set(filtered.keys()) == {"land", "air"}
        assert isinstance(filtered["land"], list)
        assert isinstance(filtered["air"], list)


def test_filtered_logistics_merges_both_priorities_without_duplicates():
    def side_effect(_product, land, air, mode="fast", priority="低价优先"):
        assert mode == "precise"
        if not land and not air:
            return {"filtered_logistics": {"land": [], "air": []}}
        if _names(land) != ["Land-RFBS-RU"]:
            return {"filtered_logistics": {"land": [], "air": []}}
        if priority == "低价优先":
            return {
                "filtered_logistics": {
                    "land": [dict(land[0])],
                    "air": [dict(air[0])],
                }
            }
        return {
            "filtered_logistics": {
                "land": [dict(land[0])],
                "air": [dict(air[0]), dict(air[1])] if len(air) > 1 else [],
            }
        }

    with patch(
        "pricing.calculate_pricing.calculate_pricing",
        side_effect=side_effect,
    ):
        result = calculate_pricing_grouped(_product(), _all_logistics(), mode="precise")

    merged = result["rfbs_ru"]["filtered_logistics"]
    assert _names(merged["land"]) == ["Land-RFBS-RU"]
    assert _names(merged["air"]) == ["Air-RFBS-RU-1", "Air-RFBS-RU-2"]


def test_filtered_logistics_stays_within_each_groups_input_logistics():
    with patch(
        "pricing.calculate_pricing.calculate_pricing",
        side_effect=_echo_filtered,
    ):
        result = calculate_pricing_grouped(_product(), _all_logistics(), mode="precise")

    assert _names(result["rfbs_ru"]["filtered_logistics"]["land"]) == ["Land-RFBS-RU"]
    assert _names(result["rfbs_ru"]["filtered_logistics"]["air"]) == [
        "Air-RFBS-RU-1",
        "Air-RFBS-RU-2",
    ]
    assert _names(result["fbp_ru"]["filtered_logistics"]["land"]) == ["Land-FBP-RU"]
    assert _names(result["fbp_ru"]["filtered_logistics"]["air"]) == ["Air-FBP-RU"]
    assert _names(result["fbp_cis"]["filtered_logistics"]["land"]) == ["Land-FBP-KZ"]
    assert _names(result["fbp_cis"]["filtered_logistics"]["air"]) == ["Air-FBP-BY"]
    assert _names(result["rfbs_KZ"]["filtered_logistics"]["land"]) == ["Land-RFBS-KZ"]
    assert result["rfbs_KZ"]["filtered_logistics"]["air"] == []


def test_returns_empty_filtered_logistics_when_no_items_are_filtered():
    with patch(
        "pricing.calculate_pricing.calculate_pricing",
        side_effect=_empty_filtered,
    ):
        result = calculate_pricing_grouped(_product(), _all_logistics(), mode="precise")

    for group in result.values():
        assert group["filtered_logistics"] == {"land": [], "air": []}


def test_post_pricing_fbp_filter_applied_only_for_fbp_cis():
    """fbp_cis applies post-pricing secondary filter; fbp_ru does not.

    The secondary filter marks unselected logistics within the same
    (company, service_level) group as eliminated.  We need ≥2 logistics
    sharing a group key so that one is selected (best) and the other is
    eliminated.
    """
    from pricing.fbp_secondary_filter import _ELIMINATED_REASON

    logistics_with_extra_cis = _all_logistics() + [
        {
            "name": "Land-FBP-KZ-Extra",
            "type": "land",
            "fulfillment_type": "fbp",
            "destination": "KZ",
            "fbp_company": "CEL",
            "fbp_service_level": "standard",
        },
    ]

    def _select_best_only(_product, land, air, mode="fast", priority="低价优先"):
        result = {"filtered_logistics": {"land": [], "air": []}}
        if land:
            result["best_land"] = dict(land[0])
        if air:
            result["best_air"] = dict(air[0])
        return result

    with patch(
        "pricing.calculate_pricing.calculate_pricing",
        side_effect=_select_best_only,
    ):
        result = calculate_pricing_grouped(
            _product(),
            logistics_with_extra_cis,
            mode="precise",
        )

    cis_filtered = result["fbp_cis"]["filtered_logistics"]
    cis_reasons = [r.get("reason") for r in cis_filtered["land"] + cis_filtered["air"]]
    assert any(r == _ELIMINATED_REASON for r in cis_reasons), (
        f"fbp_cis should have secondary-filter eliminations, got: {cis_reasons}"
    )

    ru_filtered = result["fbp_ru"]["filtered_logistics"]
    ru_reasons = [r.get("reason") for r in ru_filtered["land"] + ru_filtered["air"]]
    assert not any(r == _ELIMINATED_REASON for r in ru_reasons), (
        f"fbp_ru must NOT have secondary-filter eliminations, got: {ru_reasons}"
    )


def test_each_group_invokes_price_and_speed_priority_in_precise_mode():
    with patch(
        "pricing.calculate_pricing.calculate_pricing",
        side_effect=_empty_filtered,
    ) as mock_calculate:
        calculate_pricing_grouped(_product(), _all_logistics(), mode="precise")

    assert mock_calculate.call_count == len(EXPECTED_GROUP_KEYS) * 2
    priorities = [call.kwargs["priority"] for call in mock_calculate.call_args_list]
    modes = [call.kwargs["mode"] for call in mock_calculate.call_args_list]
    assert priorities.count("低价优先") == len(EXPECTED_GROUP_KEYS)
    assert priorities.count("速度优先") == len(EXPECTED_GROUP_KEYS)
    assert set(modes) == {"precise"}
