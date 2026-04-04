import logic as lg


def test_double_currency_limits_filtering(monkeypatch):
    # 固定汇率：1 CNY = 5 RUB；1 USD = 10 CNY
    monkeypatch.setattr(lg, "ExchangeRateService", lambda: type("S", (), {"get_exchange_rate": lambda self: 5.0})())
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
            # USD 上限 + RUB 下限 同时存在
            "price_limit_currency": "USD",
            "price_limit": 1.0,    # CNY 存储，换回 USD 很小
            "price_min_currency": "RUB",
            "price_min_rub": 1.0,  # 很低
        }
    ]

    res = lg.calculate_pricing(product, land, [], "低价优先")
    # 因 USD 上限极低，应被过滤
    assert res["best_land"] is None



