"""Tests for commission category integration in precise pricing mode."""

# pyright: reportPrivateUsage=false

import os
import sys
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pricing.commission import (  # noqa: E402
    fetch_commission_category,
    select_commission_rate_from_category,
)
from pricing.calculate_pricing import (  # noqa: E402
    _estimate_and_select_rate,
    _estimate_price_rub,
    calculate_pricing_grouped,
)


def _execute_result(category):
    """Build a mocked SQLAlchemy scalar result."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = category
    return result


def _sample_category():
    """Return a representative commission category payload."""
    return {
        "rfbs_tier1_rate": Decimal("0.12"),
        "rfbs_tier2_rate": Decimal("0.18"),
        "rfbs_tier3_rate": Decimal("0.18"),
        "fbp_tier1_rate": Decimal("0.11"),
        "fbp_tier2_rate": Decimal("0.17"),
        "fbp_tier3_rate": Decimal("0.17"),
    }


def _sample_product():
    """Return a representative product for pricing tests."""
    return {
        "unit_price": Decimal("100.0"),
        "labeling_fee": Decimal("0.5"),
        "shipping_fee": Decimal("1.0"),
        "commission_rate": Decimal("0.08"),
        "target_profit_margin": Decimal("0.2"),
        "promotion_cost_rate": Decimal("0.03"),
        "withdrawal_fee_rate": Decimal("0.01"),
        "payment_processing_fee": Decimal("0.02"),
        "return_rate": Decimal("0"),
        "vat_rate": Decimal("20"),
    }


def test_select_commission_rate_from_category_uses_rates_by_fulfillment_type():
    """RFBS and FBP should use their own rate prefixes."""
    category = _sample_category()

    rfbs_rate = select_commission_rate_from_category(category, "rfbs", Decimal("1000"))
    fbp_rate = select_commission_rate_from_category(category, "fbp", Decimal("1000"))

    assert rfbs_rate == Decimal("0.12")
    assert fbp_rate == Decimal("0.11")


@pytest.mark.parametrize(
    ("price_rub", "expected_rate"),
    [
        (Decimal("1500"), Decimal("0.11")),
        (Decimal("5000"), Decimal("0.17")),
        (Decimal("5000.01"), Decimal("0.17")),
    ],
)
def test_select_commission_rate_from_category_uses_correct_price_tier(
    price_rub,
    expected_rate,
):
    """Tier boundaries should map to tier1/tier2/tier3 correctly."""
    category = _sample_category()

    result = select_commission_rate_from_category(category, "fbp", price_rub)

    assert result == expected_rate


def test_select_commission_rate_from_category_returns_zero_for_missing_key():
    """Missing rate keys should fall back to zero."""
    result = select_commission_rate_from_category({}, "rfbs", Decimal("9999"))

    assert result == Decimal("0")


def test_estimate_price_rub_returns_reasonable_positive_value():
    """Estimated RUB price should be positive and match formula output."""
    product = _sample_product()

    with patch(
        "pricing.grouped_pricing._get_exchange_rates",
        return_value=(Decimal("0.1"), Decimal("7.2")),
    ):
        result = _estimate_price_rub(product)

    assert result > 0
    assert result == Decimal("1450.0")


def test_estimate_and_select_rate_passes_expected_args_to_select_fn():
    """Rate selector should receive category, fulfillment type, and RUB estimate."""
    product = _sample_product()
    category = _sample_category()
    select_fn = MagicMock(return_value=Decimal("0.17"))

    with patch(
        "pricing.grouped_pricing._estimate_price_rub",
        return_value=Decimal("2345.67"),
    ):
        result = _estimate_and_select_rate(product, category, "fbp", select_fn)

    assert result == Decimal("0.17")
    select_fn.assert_called_once_with(category, "fbp", Decimal("2345.67"))


def test_calculate_pricing_grouped_precise_mode_uses_commission_category_rate():
    """Precise mode should override product commission_rate from category."""
    product = _sample_product()
    category = _sample_category()

    with patch(
        "pricing.calculate_pricing.calculate_pricing",
        return_value={"filtered_logistics": {"land": [], "air": []}},
    ) as mock_calculate_pricing:
        calculate_pricing_grouped(
            product,
            [],
            mode="precise",
            commission_category=category,
        )

    commission_rates = [
        call.args[0]["commission_rate"]
        for call in mock_calculate_pricing.call_args_list
    ]

    assert commission_rates
    assert set(commission_rates) == {Decimal("0.17"), Decimal("0.18")}
    assert product["commission_rate"] == Decimal("0.08")


def test_calculate_pricing_grouped_fast_mode_ignores_commission_category():
    """Fast mode should keep the original product commission_rate."""
    product = _sample_product()
    category = _sample_category()

    with patch(
        "pricing.calculate_pricing.calculate_pricing",
        return_value={"filtered_logistics": {"land": [], "air": []}},
    ) as mock_calculate_pricing:
        calculate_pricing_grouped(
            product,
            [],
            mode="fast",
            commission_category=category,
        )

    commission_rates = [
        call.args[0]["commission_rate"]
        for call in mock_calculate_pricing.call_args_list
    ]

    assert commission_rates
    assert all(rate == Decimal("0.08") for rate in commission_rates)


def test_calculate_pricing_grouped_without_category_falls_back_to_product_rate():
    """Precise mode should use product commission_rate when category is absent."""
    product = _sample_product()

    with patch(
        "pricing.calculate_pricing.calculate_pricing",
        return_value={"filtered_logistics": {"land": [], "air": []}},
    ) as mock_calculate_pricing:
        calculate_pricing_grouped(product, [], mode="precise", commission_category=None)

    commission_rates = [
        call.args[0]["commission_rate"]
        for call in mock_calculate_pricing.call_args_list
    ]

    assert commission_rates
    assert all(rate == Decimal("0.08") for rate in commission_rates)


@pytest.mark.asyncio
async def test_fetch_commission_category_returns_dict_when_found():
    """Fetching a category should normalize the DB row into a dict."""
    session = AsyncMock()
    row = SimpleNamespace(
        rfbs_tier1_rate=Decimal("0.12"),
        rfbs_tier2_rate=Decimal("0.18"),
        rfbs_tier3_rate=Decimal("0.18"),
        fbp_tier1_rate=Decimal("0.11"),
        fbp_tier2_rate=Decimal("0.17"),
        fbp_tier3_rate=Decimal("0.17"),
    )
    session.execute.return_value = _execute_result(row)

    result = await fetch_commission_category(5, session)

    assert result == _sample_category()


@pytest.mark.asyncio
async def test_fetch_commission_category_returns_none_when_not_found():
    """Missing commission categories should return None."""
    session = AsyncMock()
    session.execute.return_value = _execute_result(None)

    result = await fetch_commission_category(999, session)

    assert result is None


@pytest.mark.asyncio
async def test_fetch_commission_category_returns_none_when_category_id_missing():
    """A missing category id should short-circuit without querying the DB."""
    session = AsyncMock()

    result = await fetch_commission_category(None, session)

    assert result is None
    session.execute.assert_not_awaited()
