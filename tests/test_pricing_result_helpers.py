from unittest.mock import patch

from pricing._result_helpers import _build_result, _compute_profits, _pick_suggested  # pyright: ignore[reportPrivateUsage]


def test_pick_suggested_prefers_land_price():
    assert _pick_suggested(100, 12, 0.12, 80, 9, 0.09) == (100, 12, 0.12)


def test_pick_suggested_prefers_air_when_land_missing():
    assert _pick_suggested(None, 0, 0, 80, 9, 0.09) == (80, 9, 0.09)


def test_pick_suggested_returns_none_when_both_missing():
    assert _pick_suggested(None, 0, 0, None, 0, 0) == (None, 0, 0)


def test_build_result_returns_expected_dict():
    with patch("pricing._result_helpers._pick_suggested", return_value=(88, 7, 0.08)):
        result = _build_result(
            land_log="land-log",
            land_cost=11,
            land_price=100,
            land_commission_info={"land": True},
            land_pricing_mode="land-mode",
            land_payment_info={"pay": "land"},
            land_payment_fixed=True,
            land_debug=["land-debug"],
            land_stats={"land": 1},
            air_log="air-log",
            air_cost=22,
            air_price=80,
            air_commission_info={"air": True},
            air_pricing_mode="air-mode",
            air_payment_info={"pay": "air"},
            air_payment_fixed=False,
            air_debug=["air-debug"],
            air_stats={"air": 2},
            land_expected_profit=12,
            land_profit_margin=0.12,
            air_expected_profit=9,
            air_profit_margin=0.09,
            product={"sku": "P-001"},
            all_costs_debug={"debug": True},
            filtered_logistics=["f1"],
            avg_land_cost=10,
            avg_land_days=3,
            saved_land_cost=2,
            saved_land_days=1,
            avg_air_cost=20,
            avg_air_days=4,
            saved_air_cost=3,
            saved_air_days=2,
        )

    expected_keys = {
        "land_price",
        "air_price",
        "land_cost",
        "air_cost",
        "best_land",
        "best_air",
        "suggested_price",
        "expected_profit",
        "land_expected_profit",
        "air_expected_profit",
        "profit_margin",
        "land_profit_margin",
        "air_profit_margin",
        "land_stats",
        "air_stats",
        "all_costs_debug",
        "land_debug",
        "air_debug",
        "land_pricing_mode",
        "air_pricing_mode",
        "land_commission_info",
        "air_commission_info",
        "land_payment_info",
        "air_payment_info",
        "land_payment_fixed",
        "air_payment_fixed",
        "product_info",
        "avg_land_cost",
        "avg_land_days",
        "avg_air_cost",
        "avg_air_days",
        "saved_land_cost",
        "saved_land_days",
        "saved_air_cost",
        "saved_air_days",
        "filtered_logistics",
    }

    assert set(result) == expected_keys
    assert result["land_price"] == 100
    assert result["air_price"] == 80
    assert result["best_land"] == "land-log"
    assert result["best_air"] == "air-log"
    assert result["suggested_price"] == 88
    assert result["expected_profit"] == 7
    assert result["profit_margin"] == 0.08
    assert result["product_info"] == {"sku": "P-001"}
    assert result["filtered_logistics"] == ["f1"]


@patch("pricing._result_helpers.calc_profit")
def test_compute_profits_calls_calc_profit_for_both_modes(mock_calc_profit):
    mock_calc_profit.side_effect = [(12, 0.12), (9, 0.09)]

    result = _compute_profits(
        land_price=100,
        land_cost=11,
        land_commission_info={"land": True},
        land_payment_info={"pay": "land"},
        land_payment_fixed=True,
        land_pricing_mode="land-mode",
        land_debug=["land-debug"],
        air_price=80,
        air_cost=22,
        air_commission_info={"air": True},
        air_payment_info={"pay": "air"},
        air_payment_fixed=False,
        air_pricing_mode="air-mode",
        air_debug=["air-debug"],
        unit_price=50,
        labeling_fee=2,
        shipping_fee=3,
        rate=1.2,
        product={"sku": "P-001"},
    )

    assert result == (12, 0.12, 9, 0.09)
    assert mock_calc_profit.call_count == 2
    assert mock_calc_profit.call_args_list[0].args[10] == {"sku": "P-001"}
    assert mock_calc_profit.call_args_list[0].args[11] == "陆运"
    assert mock_calc_profit.call_args_list[0].args[12] == ["land-debug"]
    assert mock_calc_profit.call_args_list[1].args[11] == "空运"


@patch("pricing._result_helpers.calc_profit")
def test_compute_profits_skips_calc_profit_when_prices_missing(mock_calc_profit):
    result = _compute_profits(
        land_price=None,
        land_cost=11,
        land_commission_info={"land": True},
        land_payment_info={"pay": "land"},
        land_payment_fixed=True,
        land_pricing_mode="land-mode",
        land_debug=["land-debug"],
        air_price=None,
        air_cost=22,
        air_commission_info={"air": True},
        air_payment_info={"pay": "air"},
        air_payment_fixed=False,
        air_pricing_mode="air-mode",
        air_debug=["air-debug"],
        unit_price=50,
        labeling_fee=2,
        shipping_fee=3,
        rate=1.2,
        product={"sku": "P-001"},
    )

    assert result == (0, 0, 0, 0)
    mock_calc_profit.assert_not_called()
