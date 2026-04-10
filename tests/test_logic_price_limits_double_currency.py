import pricing as lg


def test_cny_limits_filtering_uses_cny_directly(monkeypatch):
    monkeypatch.setattr(
        lg,
        "ExchangeRateService",
        lambda: type("S", (), {"get_exchange_rate": lambda self: 5.0})(),
    )
    monkeypatch.setattr(lg, "get_usd_rate", lambda: 10.0)

    product = {
        "unit_price": 10.0,
        "labeling_fee": 0.0,
        "shipping_fee": 0.0,
        "promotion_cost_rate": 0.0,
        "commission_rate": 0.0,
        "withdrawal_fee_rate": 0.0,
        "payment_processing_fee": 0.0,
        "target_profit_margin": 0.2,
        "weight_g": 100,
        "length_cm": 10,
        "width_cm": 10,
        "height_cm": 10,
    }

    land = [
        {
            "name": "L",
            "type": "land",
            "min_days": 1,
            "max_days": 1,
            "fee_mode": "base_plus_continue",
            "continue_unit": 100,
            "continue_fee": 0.0,
            "base_fee": 0.0,
            "max_sum_of_sides": 1000,
            "max_longest_side": 1000,
            "price_limit_cny": 14.0,
            "price_min_cny": 1.0,
        }
    ]

    res = lg.calculate_pricing(product, land, [], "低价优先")
    assert res["best_land"] is None
