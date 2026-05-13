from decimal import Decimal

import pytest

from pricing.final_price import compute_final_price
from pricing.profit import calc_profit
from pricing.vat_utils import normalize_vat_to_fraction


def test_normalize_vat_percent_int_to_fraction():
    assert normalize_vat_to_fraction(20) == Decimal("0.20")


def test_normalize_vat_fraction_decimal_stays_fraction():
    assert normalize_vat_to_fraction(Decimal("0.20")) == Decimal("0.20")


def test_normalize_vat_percent_string_strips_percent_sign():
    assert normalize_vat_to_fraction("20%") == Decimal("0.20")


def test_normalize_vat_none_is_zero():
    assert normalize_vat_to_fraction(None) == Decimal("0")


@pytest.mark.parametrize("bad", [Decimal("-1"), 150])
def test_normalize_vat_rejects_out_of_range_values(bad):
    with pytest.raises(ValueError):
        normalize_vat_to_fraction(bad)


def _base_product(vat_rate):
    return {
        "target_profit_margin": Decimal("0.20"),
        "promotion_cost_rate": Decimal("0.03"),
        "commission_rate": Decimal("0.08"),
        "withdrawal_fee_rate": Decimal("0.01"),
        "payment_processing_fee": Decimal("0.02"),
        "return_rate": Decimal("0"),
        "vat_rate": vat_rate,
    }


def _compute_profit_for_vat(vat_rate):
    debug = []
    product = _base_product(vat_rate)
    price, commission_rub, pricing_mode, payment_rub, payment_fixed = (
        compute_final_price(
            cost=Decimal("5"),
            product=product,
            unit_price=Decimal("100"),
            labeling_fee=Decimal("2"),
            shipping_fee=Decimal("3"),
            rate=Decimal("0.1"),
        )
    )
    profit, _margin = calc_profit(
        price=price,
        cost=Decimal("5"),
        commission_info=commission_rub,
        payment_info=payment_rub,
        payment_fixed=payment_fixed,
        pricing_mode=pricing_mode,
        unit_price=Decimal("100"),
        labeling_fee=Decimal("2"),
        shipping_fee=Decimal("3"),
        rate=Decimal("0.1"),
        product=product,
        label="VAT一致性",
        debug_list=debug,
    )
    return profit.quantize(Decimal("0.0001"))


def test_final_price_and_profit_paths_treat_vat_20_and_fraction_identically():
    # [PRC-W12R2-01]
    assert _compute_profit_for_vat(20) == _compute_profit_for_vat(Decimal("0.20"))
