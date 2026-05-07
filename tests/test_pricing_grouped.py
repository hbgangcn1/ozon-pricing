import os
import sys
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.routes._pricing_helpers import get_commission_rate  # noqa: E402


def _execute_result(category):
    result = MagicMock()
    result.scalar_one_or_none.return_value = category
    return result


@pytest.mark.asyncio
async def test_get_commission_rate_returns_none_when_category_id_missing():
    session = AsyncMock()

    result = await get_commission_rate(Decimal("1200"), None, "fbp", session)

    assert result is None
    session.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_commission_rate_uses_tier1_for_prices_up_to_1500():
    session = AsyncMock()
    category = SimpleNamespace(
        fbp_tier1_rate=Decimal("0.05"),
        fbp_tier2_rate=Decimal("0.06"),
        fbp_tier3_rate=Decimal("0.07"),
    )
    session.execute.return_value = _execute_result(category)

    result = await get_commission_rate(Decimal("1500"), 1, "fbp", session)

    assert result == Decimal("0.0500")


@pytest.mark.asyncio
async def test_get_commission_rate_uses_tier2_for_mid_prices():
    session = AsyncMock()
    category = SimpleNamespace(
        fbp_tier1_rate=Decimal("0.05"),
        fbp_tier2_rate=Decimal("0.0689"),
        fbp_tier3_rate=Decimal("0.07"),
    )
    session.execute.return_value = _execute_result(category)

    result = await get_commission_rate(Decimal("3200"), 1, "fbp", session)

    assert result == Decimal("0.0689")


@pytest.mark.asyncio
async def test_get_commission_rate_uses_tier3_for_prices_above_5000():
    session = AsyncMock()
    category = SimpleNamespace(
        fbp_tier1_rate=Decimal("0.05"),
        fbp_tier2_rate=Decimal("0.06"),
        fbp_tier3_rate=Decimal("0.0744"),
    )
    session.execute.return_value = _execute_result(category)

    result = await get_commission_rate(Decimal("5000.01"), 1, "fbp", session)

    assert result == Decimal("0.0744")


@pytest.mark.asyncio
async def test_get_commission_rate_adds_one_percent_for_rfbs():
    session = AsyncMock()
    category = SimpleNamespace(
        fbp_tier1_rate=Decimal("0.05"),
        fbp_tier2_rate=Decimal("0.0733"),
        fbp_tier3_rate=Decimal("0.08"),
    )
    session.execute.return_value = _execute_result(category)

    fbp_rate = await get_commission_rate(Decimal("2200"), 1, "fbp", session)
    rfbs_rate = await get_commission_rate(Decimal("2200"), 1, "rfbs", session)

    assert fbp_rate is not None
    assert rfbs_rate is not None
    assert fbp_rate == Decimal("0.0733")
    assert rfbs_rate == Decimal("0.0833")
    assert rfbs_rate - fbp_rate == Decimal("0.0100")


@pytest.mark.asyncio
async def test_get_commission_rate_returns_none_when_category_not_found():
    session = AsyncMock()
    session.execute.return_value = _execute_result(None)

    result = await get_commission_rate(Decimal("1200"), 999, "fbp", session)

    assert result is None
