import importlib
from unittest.mock import patch


calc_module = importlib.import_module("pricing.calculate_pricing")


def _product():
    return {
        "unit_price": 10.0,
        "labeling_fee": 1.0,
        "shipping_fee": 2.0,
        "promotion_cost_rate": 0.1,
        "commission_rate": 0.1,
        "withdrawal_fee_rate": 0.02,
        "payment_processing_fee": 0.0,
        "target_profit_margin": 0.2,
        "weight_g": 1000,
        "length_cm": 20,
        "width_cm": 15,
        "height_cm": 10,
    }


def _land_logistics(name: str, **overrides):
    base = {
        "name": name,
        "type": "land",
        "delivery_method": "pickup",
        "min_days": 5,
        "max_days": 8,
        "fee_mode": "base_plus_continue",
        "continue_unit": 100,
        "continue_fee": 0.5,
        "base_fee": 8.0,
        "min_weight": 0,
        "max_weight": 5000,
        "max_sum_of_sides": 500,
        "max_longest_side": 300,
        "price_limit_cny": 1000000,
        "price_min_cny": 0,
        "priority_group": "A",
        "volume_mode": "none",
    }
    base.update(overrides)
    return base


def _filtered_names(result):
    filtered = result.get("filtered_logistics", {"land": [], "air": []})
    return {item["name"] for items in filtered.values() for item in items}


def test_filtered_logistics_names_stay_within_input_names(monkeypatch):
    original_add_unselected = calc_module.add_unselected

    def fake_add_unselected(
        candidates, filtered_list, global_best=None, priority_type="低价优先"
    ):
        original_add_unselected(candidates, filtered_list, global_best, priority_type)
        filtered_list.append({"name": "Tanais Standard Small", "reason": "phantom"})

    monkeypatch.setattr(calc_module, "add_unselected", fake_add_unselected)

    with patch.object(calc_module, "_get_exchange_rates", return_value=(0.0904, 7.2)):
        input_logistics = [_land_logistics("用户陆运")]
        result = calc_module.calculate_pricing(_product(), input_logistics, [])

    assert _filtered_names(result) <= {log["name"] for log in input_logistics}


def test_filtered_logistics_keeps_filtered_input_logistic_name():
    with patch.object(calc_module, "_get_exchange_rates", return_value=(0.0904, 7.2)):
        result = calc_module.calculate_pricing(
            _product(),
            [_land_logistics("用户被淘汰陆运", max_weight=500)],
            [],
        )

    assert result["filtered_logistics"]["land"] == [
        {
            "name": "用户被淘汰陆运",
            "reason": "实重 1000.00g 超过上限 500g",
        }
    ]


def test_filtered_logistics_is_empty_when_input_logistics_is_empty():
    result = calc_module.calculate_pricing(_product(), [], [])

    assert result["filtered_logistics"] == {"land": [], "air": []}
