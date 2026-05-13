from decimal import Decimal

import pytest

from pricing.profit import calc_profit


def _profit_case(cost: str, revenue: str):
    debug = []
    profit, margin = calc_profit(
        price=Decimal(revenue),
        cost=Decimal(cost),
        commission_info=Decimal("0"),
        payment_info=Decimal("0"),
        payment_fixed=False,
        pricing_mode="代理费在分母中,收单费在分母中",
        unit_price=Decimal("0"),
        labeling_fee=Decimal("0"),
        shipping_fee=Decimal("0"),
        rate=Decimal("1"),
        product={
            "target_profit_margin": Decimal("0.2"),
            "promotion_cost_rate": Decimal("0"),
            "commission_rate": Decimal("0"),
            "withdrawal_fee_rate": Decimal("0"),
            "payment_processing_fee": Decimal("0"),
            "return_rate": Decimal("0"),
            "vat_rate": Decimal("0"),
        },
        label="zero-division-guard",
        debug_list=debug,
    )
    return profit, margin


def test_zero_cost_normal_revenue_calculates_margin():
    profit, margin = _profit_case(cost="0", revenue="100")

    assert profit == Decimal("98.00")
    assert margin == Decimal("98.00")


def test_zero_revenue_returns_zero_margin_without_division_error():
    profit, margin = _profit_case(cost="10", revenue="0")

    assert profit == Decimal("-10.00")
    assert margin == Decimal("0")


def test_zero_cost_and_zero_revenue_returns_zero_margin():
    profit, margin = _profit_case(cost="0", revenue="0")

    assert profit == Decimal("0")
    assert margin == Decimal("0")
