from unittest.mock import patch

from pricing.calculate_pricing import calculate_pricing_grouped


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


def _log(
    name,
    *,
    company,
    service_level="std",
    destination="KZ",
    base_rate=100,
    min_days=1,
    max_days=3,
    fulfillment_type="fbp",
    kind="land",
    priority_group=None,
):
    item = {
        "name": name,
        "type": kind,
        "fulfillment_type": fulfillment_type,
        "destination": destination,
        "fbp_company": company,
        "fbp_service_level": service_level,
        "base_rate": base_rate,
        "min_days": min_days,
        "max_days": max_days,
    }
    if priority_group is not None:
        item["priority_group"] = priority_group
    return item


def _candidate(log, cost):
    return log, cost


def _pricing_result(
    land_logistics, air_logistics, *, land_filtered=None, air_filtered=None
):
    return {
        "best_land": land_logistics[0] if land_logistics else None,
        "best_air": air_logistics[0] if air_logistics else None,
        "land_price": None,
        "air_price": None,
        "land_cost": 0 if land_logistics else None,
        "air_cost": 0 if air_logistics else None,
        "filtered_logistics": {
            "land": list(land_filtered or []),
            "air": list(air_filtered or []),
        },
    }


def _run_grouped(logistics, run_filters_result, pricing_side_effect=None):
    if pricing_side_effect is None:

        def _default_pricing_side_effect(
            product, land_logistics, air_logistics, mode="fast", priority="低价优先"
        ):
            return _pricing_result(land_logistics, air_logistics)

        pricing_side_effect = _default_pricing_side_effect

    with (
        patch(
            "pricing.calculate_pricing.calculate_pricing",
            side_effect=pricing_side_effect,
        ),
        patch(
            "pricing.calculate_pricing._run_filters", return_value=run_filters_result
        ),
        patch(
            "pricing.calculate_pricing._get_exchange_rates", return_value=(0.09, 7.2)
        ),
    ):
        return calculate_pricing_grouped(_product(), logistics, mode="precise")


def test_stage2_filters_by_group():
    logs = [
        _log("cel-100", company="CEL", base_rate=100, destination="KZ"),
        _log("cel-50", company="CEL", base_rate=50, destination="KZ"),
    ]
    seen_non_empty = {"called": False}

    def pricing_side_effect(
        product, land_logistics, air_logistics, mode="fast", priority="低价优先"
    ):
        if land_logistics or air_logistics:
            seen_non_empty["called"] = True
            assert len(land_logistics) == 1
            assert land_logistics[0]["base_rate"] == 100
        return _pricing_result(land_logistics, air_logistics)

    result = _run_grouped(
        logs, ([], [], None, None, []), pricing_side_effect=pricing_side_effect
    )

    assert seen_non_empty["called"] is True
    assert result["fbp_cis"]["filtered_logistics"]["land"] == [
        {"name": "cel-50", "reason": "该物流无法覆盖更高成本"}
    ]


def test_stage2_eliminated_reason():
    logs = [
        _log("cel-100", company="CEL", base_rate=100, destination="KZ"),
        _log("cel-50", company="CEL", base_rate=50, destination="KZ"),
    ]

    result = _run_grouped(logs, ([], [], None, None, []))

    assert (
        result["fbp_cis"]["filtered_logistics"]["land"][0]["reason"]
        == "该物流无法覆盖更高成本"
    )


def test_stage3_price_picks_lowest_cost():
    logs = [
        _log(
            "a-15", company="A", base_rate=10, destination="KZ", min_days=2, max_days=5
        ),
        _log(
            "b-9", company="B", base_rate=10, destination="KZ", min_days=2, max_days=4
        ),
        _log(
            "c-12", company="C", base_rate=10, destination="KZ", min_days=3, max_days=6
        ),
    ]
    candidates = [
        _candidate(logs[0], 15),
        _candidate(logs[1], 9),
        _candidate(logs[2], 12),
    ]

    result = _run_grouped(logs, (candidates, [], None, None, []))

    assert result["fbp_cis"]["price_priority"]["best_land"]["name"] == "b-9"
    assert result["fbp_cis"]["price_priority"]["land_cost"] == 9


def test_stage3_speed_uses_temp_abcde():
    logs = [
        _log(
            "speed-a",
            company="A",
            base_rate=10,
            destination="KZ",
            min_days=1,
            max_days=1,
        ),
        _log(
            "speed-b",
            company="B",
            base_rate=10,
            destination="KZ",
            min_days=5,
            max_days=8,
        ),
        _log(
            "speed-c",
            company="C",
            base_rate=10,
            destination="KZ",
            min_days=9,
            max_days=12,
        ),
    ]
    candidates = [
        _candidate(logs[0], 15),
        _candidate(logs[1], 9),
        _candidate(logs[2], 12),
    ]

    result = _run_grouped(logs, (candidates, [], None, None, []))

    assert result["fbp_cis"]["speed_priority"]["best_land"]["name"] == "speed-a"
    assert result["fbp_cis"]["speed_priority"]["land_cost"] == 15


def test_stage3_speed_ignores_priority_group_field():
    logs = [
        _log(
            "wrong-e-a",
            company="A",
            base_rate=10,
            destination="KZ",
            min_days=1,
            max_days=1,
            priority_group="E",
        ),
        _log(
            "wrong-e-b",
            company="B",
            base_rate=10,
            destination="KZ",
            min_days=4,
            max_days=6,
            priority_group="E",
        ),
        _log(
            "wrong-e-c",
            company="C",
            base_rate=10,
            destination="KZ",
            min_days=8,
            max_days=10,
            priority_group="E",
        ),
    ]
    candidates = [
        _candidate(logs[0], 20),
        _candidate(logs[1], 5),
        _candidate(logs[2], 12),
    ]

    result = _run_grouped(logs, (candidates, [], None, None, []))

    assert result["fbp_cis"]["speed_priority"]["best_land"]["name"] == "wrong-e-a"


def test_non_fbp_cis_unchanged():
    logs = [
        _log(
            "rfbs-ru",
            company="R",
            fulfillment_type="rfbs",
            destination="RU",
            kind="land",
        ),
        _log("fbp-cis", company="CEL", destination="KZ", kind="land"),
    ]

    result = _run_grouped(logs, ([], [], None, None, []))

    assert result["rfbs_ru"]["filtered_logistics"]["land"] == []
    assert all(
        item["reason"] != "该物流无法覆盖更高成本"
        for item in result["rfbs_ru"]["filtered_logistics"]["land"]
    )


def test_fbp_cis_empty_after_stage2():
    logs = [
        _log(
            "solo-cis",
            company="CEL",
            destination="KZ",
            base_rate=100,
            min_days=2,
            max_days=3,
        ),
    ]
    candidates = [_candidate(logs[0], 11)]

    result = _run_grouped(logs, (candidates, [], None, None, []))

    assert result["fbp_cis"]["filtered_logistics"]["land"] == []
    assert result["fbp_cis"]["price_priority"]["best_land"]["name"] == "solo-cis"
    assert result["fbp_cis"]["speed_priority"]["best_land"]["name"] == "solo-cis"


def test_single_logistics():
    logs = [
        _log(
            "single-cis",
            company="CEL",
            destination="KZ",
            base_rate=100,
            min_days=1,
            max_days=2,
        ),
    ]
    candidates = [_candidate(logs[0], 7)]

    result = _run_grouped(logs, (candidates, [], None, None, []))

    assert result["fbp_cis"]["price_priority"]["best_land"]["name"] == "single-cis"
    assert result["fbp_cis"]["speed_priority"]["best_land"]["name"] == "single-cis"


def test_filtered_logistics_has_all_eliminated():
    logs = [
        _log(
            "keep-120",
            company="CEL",
            destination="KZ",
            base_rate=120,
            min_days=1,
            max_days=1,
        ),
        _log(
            "drop-60",
            company="CEL",
            destination="KZ",
            base_rate=60,
            min_days=1,
            max_days=1,
        ),
        _log(
            "stage3-a",
            company="A",
            destination="KZ",
            base_rate=80,
            min_days=1,
            max_days=1,
        ),
        _log(
            "stage3-b",
            company="B",
            destination="KZ",
            base_rate=90,
            min_days=6,
            max_days=8,
        ),
    ]
    candidates = [
        _candidate(logs[0], 1),
        _candidate(logs[2], 9),
        _candidate(logs[3], 15),
    ]

    result = _run_grouped(logs, (candidates, [], None, None, []))
    filtered_names = {
        item["name"] for item in result["fbp_cis"]["filtered_logistics"]["land"]
    }

    assert "drop-60" in filtered_names
    assert "stage3-a" in filtered_names
    assert "stage3-b" in filtered_names
    assert "keep-120" not in filtered_names
    assert any(
        item["reason"] == "该物流无法覆盖更高成本"
        for item in result["fbp_cis"]["filtered_logistics"]["land"]
    )
