from unittest.mock import patch, MagicMock

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
    base_fee=100,
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
        "base_fee": base_fee,
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


def _make_cost_and_filter_side_effect(logs, costs=None):
    # cost_and_filter called 4x: 2 from _stage1_filter + 2 from _group_fbp_cis
    default_cost = 10.0
    cost_map = {}
    if costs is not None:
        for lg, c in costs:
            cost_map[lg["name"]] = c
    else:
        for lg in logs:
            cost_map[lg["name"]] = default_cost

    def side_effect(
        logistics,
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
        result = []
        for _, lg in enumerate(logistics):
            d = lg if isinstance(lg, dict) else dict(lg)
            name = d.get("name", "")
            if name in cost_map:
                result.append((dict(d), cost_map[name]))
        return result

    return side_effect


def _run_grouped(
    logistics,
    cost_side_effect=None,
    pricing_side_effect=None,
):
    if pricing_side_effect is None:

        def _default_pricing_side_effect(
            product, land_logistics, air_logistics, mode="fast", priority="低价优先"
        ):
            return _pricing_result(land_logistics, air_logistics)

        pricing_side_effect = _default_pricing_side_effect

    if cost_side_effect is None:
        cost_side_effect = _make_cost_and_filter_side_effect(logistics)

    with (
        patch(
            "pricing.calculate_pricing.calculate_pricing",
            side_effect=pricing_side_effect,
        ),
        patch(
            "pricing.grouped_pricing.cost_and_filter",
            side_effect=cost_side_effect,
        ),
        patch(
            "pricing.grouped_pricing._get_exchange_rates",
            return_value=(0.09, 7.2),
        ),
    ):
        return calculate_pricing_grouped(_product(), logistics, mode="precise")


def test_stage2_filters_by_group():
    logs = [
        _log("cel-100", company="CEL", base_fee=100, destination="KZ"),
        _log("cel-50", company="CEL", base_fee=50, destination="KZ"),
    ]
    seen_non_empty = {"called": False}

    def pricing_side_effect(
        product, land_logistics, air_logistics, mode="fast", priority="低价优先"
    ):
        if land_logistics or air_logistics:
            seen_non_empty["called"] = True
            assert len(land_logistics) == 1
            assert land_logistics[0]["base_fee"] == 100
        return _pricing_result(land_logistics, air_logistics)

    result = _run_grouped(logs, pricing_side_effect=pricing_side_effect)

    assert seen_non_empty["called"] is True
    assert result["fbp_cis"]["filtered_logistics"]["land"] == [
        {"name": "cel-50", "reason": "该物流无法覆盖更高成本"}
    ]


def test_stage2_eliminated_reason():
    logs = [
        _log("cel-100", company="CEL", base_fee=100, destination="KZ"),
        _log("cel-50", company="CEL", base_fee=50, destination="KZ"),
    ]
    result = _run_grouped(logs)

    assert (
        result["fbp_cis"]["filtered_logistics"]["land"][0]["reason"]
        == "该物流无法覆盖更高成本"
    )


def test_stage3_price_picks_lowest_cost():
    logs = [
        _log(
            "a-15", company="A", base_fee=10, destination="KZ", min_days=2, max_days=5
        ),
        _log("b-9", company="B", base_fee=10, destination="KZ", min_days=2, max_days=4),
        _log(
            "c-12", company="C", base_fee=10, destination="KZ", min_days=3, max_days=6
        ),
    ]
    cost_se = _make_cost_and_filter_side_effect(
        logs,
        costs=[
            _candidate(logs[0], 15),
            _candidate(logs[1], 9),
            _candidate(logs[2], 12),
        ],
    )

    result = _run_grouped(logs, cost_side_effect=cost_se)

    assert result["fbp_cis"]["price_priority"]["best_land"]["name"] == "b-9"
    assert result["fbp_cis"]["price_priority"]["land_cost"] == 9


def test_stage3_speed_uses_temp_abcde():
    logs = [
        _log(
            "speed-a",
            company="A",
            base_fee=10,
            destination="KZ",
            min_days=1,
            max_days=1,
        ),
        _log(
            "speed-b",
            company="B",
            base_fee=10,
            destination="KZ",
            min_days=5,
            max_days=8,
        ),
        _log(
            "speed-c",
            company="C",
            base_fee=10,
            destination="KZ",
            min_days=9,
            max_days=12,
        ),
    ]
    cost_se = _make_cost_and_filter_side_effect(
        logs,
        costs=[
            _candidate(logs[0], 15),
            _candidate(logs[1], 9),
            _candidate(logs[2], 12),
        ],
    )

    result = _run_grouped(logs, cost_side_effect=cost_se)

    assert result["fbp_cis"]["speed_priority"]["best_land"]["name"] == "speed-a"
    assert result["fbp_cis"]["speed_priority"]["land_cost"] == 15


def test_stage3_speed_ignores_priority_group_field():
    logs = [
        _log(
            "wrong-e-a",
            company="A",
            base_fee=10,
            destination="KZ",
            min_days=1,
            max_days=1,
            priority_group="E",
        ),
        _log(
            "wrong-e-b",
            company="B",
            base_fee=10,
            destination="KZ",
            min_days=4,
            max_days=6,
            priority_group="E",
        ),
        _log(
            "wrong-e-c",
            company="C",
            base_fee=10,
            destination="KZ",
            min_days=8,
            max_days=10,
            priority_group="E",
        ),
    ]
    cost_se = _make_cost_and_filter_side_effect(
        logs,
        costs=[
            _candidate(logs[0], 20),
            _candidate(logs[1], 5),
            _candidate(logs[2], 12),
        ],
    )

    result = _run_grouped(logs, cost_side_effect=cost_se)

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

    result = _run_grouped(logs)

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
            base_fee=100,
            min_days=2,
            max_days=3,
        ),
    ]
    cost_se = _make_cost_and_filter_side_effect(logs, costs=[_candidate(logs[0], 11)])

    result = _run_grouped(logs, cost_side_effect=cost_se)

    assert result["fbp_cis"]["filtered_logistics"]["land"] == []
    assert result["fbp_cis"]["price_priority"]["best_land"]["name"] == "solo-cis"
    assert result["fbp_cis"]["speed_priority"]["best_land"]["name"] == "solo-cis"


def test_single_logistics():
    logs = [
        _log(
            "single-cis",
            company="CEL",
            destination="KZ",
            base_fee=100,
            min_days=1,
            max_days=2,
        ),
    ]
    cost_se = _make_cost_and_filter_side_effect(logs, costs=[_candidate(logs[0], 7)])

    result = _run_grouped(logs, cost_side_effect=cost_se)

    assert result["fbp_cis"]["price_priority"]["best_land"]["name"] == "single-cis"
    assert result["fbp_cis"]["speed_priority"]["best_land"]["name"] == "single-cis"


def test_filtered_logistics_has_all_eliminated():
    logs = [
        _log(
            "keep-120",
            company="CEL",
            destination="KZ",
            base_fee=120,
            min_days=1,
            max_days=1,
        ),
        _log(
            "drop-60",
            company="CEL",
            destination="KZ",
            base_fee=60,
            min_days=1,
            max_days=1,
        ),
        _log(
            "stage3-a",
            company="A",
            destination="KZ",
            base_fee=80,
            min_days=1,
            max_days=1,
        ),
        _log(
            "stage3-b",
            company="B",
            destination="KZ",
            base_fee=90,
            min_days=6,
            max_days=8,
        ),
    ]
    result = _run_grouped(logs)
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


def test_stage2_groups_by_priority_group():
    logs = [
        _log(
            "xs-high",
            company="CEL",
            base_fee=50,
            destination="KZ",
            priority_group="Extra Small",
        ),
        _log(
            "xs-low",
            company="CEL",
            base_fee=20,
            destination="KZ",
            priority_group="Extra Small",
        ),
        _log(
            "big-high",
            company="CEL",
            base_fee=200,
            destination="KZ",
            priority_group="Big",
        ),
        _log(
            "big-low",
            company="CEL",
            base_fee=80,
            destination="KZ",
            priority_group="Big",
        ),
    ]
    kept_names = {"called": set()}

    def pricing_side_effect(
        product, land_logistics, air_logistics, mode="fast", priority="低价优先"
    ):
        for lg in land_logistics:
            kept_names["called"].add(lg["name"])
        return _pricing_result(land_logistics, air_logistics)

    _run_grouped(logs, pricing_side_effect=pricing_side_effect)

    assert "xs-high" in kept_names["called"]
    assert "big-high" in kept_names["called"]
    assert "xs-low" not in kept_names["called"]
    assert "big-low" not in kept_names["called"]


def test_stage1_runs_before_stage2():
    stage1_fail = _log(
        "too-heavy",
        company="CEL",
        base_fee=999,
        destination="KZ",
        priority_group="Big",
    )
    stage1_pass = _log(
        "ok-small",
        company="CEL",
        base_fee=10,
        destination="KZ",
        priority_group="Big",
    )
    logs = [stage1_fail, stage1_pass]

    def cost_side_effect(
        logistics,
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
        result = []
        for lg in logistics:
            d = lg if isinstance(lg, dict) else dict(lg)
            if d.get("name") == "ok-small":
                result.append((dict(d), 5.0))
            else:
                filtered_logistics["land"].append(
                    {"name": d["name"], "reason": "重量超限"}
                )
        return result

    kept_names = {"called": set()}

    def pricing_side_effect(
        product, land_logistics, air_logistics, mode="fast", priority="低价优先"
    ):
        for lg in land_logistics:
            kept_names["called"].add(lg["name"])
        return _pricing_result(land_logistics, air_logistics)

    result = _run_grouped(
        logs,
        cost_side_effect=cost_side_effect,
        pricing_side_effect=pricing_side_effect,
    )

    assert "ok-small" in kept_names["called"]
    assert "too-heavy" not in kept_names["called"]
