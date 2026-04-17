"""
Comprehensive tests for api/routes/pricing.py
Targeting missing lines: 30, 35-43, 47-52, 56-61, 75-125, 153-173, 221-223, 233-235, 249, 252
"""

import sys
import os
import decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402
from api.main import app  # noqa: E402
from api import dependencies  # noqa: E402
from database import get_db  # noqa: E402
from api.routes.pricing import (  # noqa: E402
    convert_decimals,
    get_fallback_exchange_rate,
    get_fallback_usd_rate,
    build_breakdown,
    format_result,
    format_combo,
    get_user_logistics,
)
from api.models.schemas import (  # noqa: E402
    PricingResultItem,
    BreakdownItem,
)

client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _ensure_overrides():
    app.dependency_overrides[dependencies.get_current_user_id] = lambda: 1
    app.dependency_overrides[dependencies.require_admin] = lambda: 1
    yield
    app.dependency_overrides.pop(dependencies.get_current_user_id, None)
    app.dependency_overrides.pop(dependencies.require_admin, None)


# ---------------------------------------------------------------------------
# Helper builders
# ---------------------------------------------------------------------------


def _make_mock_session(logistics_rows=None):
    """Build an async session mock that returns the given logistics rows."""
    if logistics_rows is None:
        logistics_rows = []

    mock_session = AsyncMock()

    # Scalars chain: session.execute(...) -> result.scalars().all()
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = logistics_rows
    mock_result.scalars.return_value = mock_scalars
    mock_session.execute.return_value = mock_result

    return mock_session


def _db_override(session):
    async def override():
        yield session

    return override


def _minimal_product():
    return {
        "unit_price": 10.0,
        "labeling_fee": 0.5,
        "shipping_fee": 1.0,
        "commission_rate": 5,  # 5% → to_rate gives 0.05
        "promotion_cost_rate": 3,  # 3%
        "withdrawal_fee_rate": 1,  # 1%
        "payment_processing_fee": 2,  # 2%
        "return_rate": 0,
        "vat_rate": 20,  # 20%
    }


# ===========================================================================
# Unit tests: convert_decimals (lines 24-31)
# ===========================================================================


class TestConvertDecimals:
    def test_dict_branch(self):
        data = {"price": decimal.Decimal("9.99")}
        result: dict = convert_decimals(data)
        assert result == {"price": 9.99}
        assert isinstance(result["price"], float)

    def test_list_branch_line30(self):
        # Exercises the list branch AND the Decimal leaf (line 30)
        data = [decimal.Decimal("1.5"), decimal.Decimal("2.75")]
        result = convert_decimals(data)
        assert result == [1.5, 2.75]
        assert all(isinstance(v, float) for v in result)

    def test_decimal_leaf(self):
        result = convert_decimals(decimal.Decimal("3.14"))
        assert isinstance(result, float)
        assert abs(result - 3.14) < 1e-9

    def test_passthrough(self):
        assert convert_decimals("hello") == "hello"
        assert convert_decimals(42) == 42
        assert convert_decimals(None) is None

    def test_nested_dict_list(self):
        data = {"items": [decimal.Decimal("1.0"), decimal.Decimal("2.0")]}
        result = convert_decimals(data)
        assert result == {"items": [1.0, 2.0]}


# ===========================================================================
# Unit tests: get_user_logistics (lines 35-43)
# ===========================================================================


class TestGetUserLogistics:
    @pytest.mark.asyncio
    async def test_returns_empty_when_no_rows(self):
        session = _make_mock_session([])
        result = await get_user_logistics(session, user_id=1)
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_row_data(self):
        # Build a mock ORM row with __table__.columns
        mock_col = MagicMock()
        mock_col.key = "type"
        mock_row = MagicMock()
        mock_row.__table__ = MagicMock()
        mock_row.__table__.columns = [mock_col]
        mock_row.type = "land"

        session = _make_mock_session([mock_row])
        result = await get_user_logistics(session, user_id=1)
        assert result == [{"type": "land"}]

    @pytest.mark.asyncio
    async def test_logistics_type_filter_appends_where_clause(self):
        """
        Exercises line 40: stmt.where(Logistics.type == logistics_type)
        The session.execute is still awaited – we just verify no exception
        and that the filter branch was taken.
        """
        session = _make_mock_session([])
        result = await get_user_logistics(session, user_id=1, logistics_type="land")
        assert result == []
        # execute was called exactly once
        session.execute.assert_awaited_once()


# ===========================================================================
# Unit tests: get_fallback_exchange_rate (lines 47-52)
# ===========================================================================


class TestGetFallbackExchangeRate:
    def test_returns_float_from_exchange_service(self):
        mock_module = MagicMock()
        mock_module.get_fallback_exchange_rate.return_value = 0.09
        with patch.dict("sys.modules", {"exchange_service": mock_module}):
            result = get_fallback_exchange_rate()
        assert result == round(0.09, 4)

    def test_import_error_fallback_line51_52(self):
        broken = MagicMock(spec=[])
        with patch.dict("sys.modules", {"exchange_service": broken}):
            result = get_fallback_exchange_rate()
        assert result == round(0.0904, 4)


# ===========================================================================
# Unit tests: get_fallback_usd_rate (lines 56-61)
# ===========================================================================


class TestGetFallbackUsdRate:
    def test_returns_float_from_exchange_service(self):
        mock_module = MagicMock()
        mock_module.get_fallback_usd_rate.return_value = 7.1
        with patch.dict("sys.modules", {"exchange_service": mock_module}):
            result = get_fallback_usd_rate()
        assert result == round(7.1, 4)

    def test_import_error_fallback_line60_61(self):
        broken = MagicMock(spec=[])
        with patch.dict("sys.modules", {"exchange_service": broken}):
            result = get_fallback_usd_rate()
        assert result == round(7.2, 4)


# ===========================================================================
# Unit tests: build_breakdown (lines 75-129)
# ===========================================================================


class TestBuildBreakdown:
    def _call(self, product=None, **kwargs):
        defaults = dict(
            product=product or _minimal_product(),
            logistics_cost_cny=5.0,
            price_cny=100.0,
            commission_rub=10.0,
            payment_rub=5.0,
            payment_fixed=False,
            expected_profit=20.0,
            profit_margin_pct=0.2,
            rate=0.085,
        )
        defaults.update(kwargs)
        return build_breakdown(**defaults)

    def test_returns_list_of_breakdown_items(self):
        items = self._call()
        assert isinstance(items, list)
        assert all(isinstance(i, BreakdownItem) for i in items)

    def test_always_includes_profit_item(self):
        """运营利润 item is always present even when value is 0."""
        items = self._call(expected_profit=0.0)
        labels = [i.label for i in items]
        assert "运营利润" in labels

    def test_payment_fixed_branch_line101(self):
        """When payment_fixed=True, payment_cny = round(10 * rate, 2)."""
        items = self._call(payment_fixed=True, rate=0.085)
        labels = [i.label for i in items]
        # 收单费 should appear because 10 * 0.085 = 0.85 > 0.01
        assert "收单费" in labels

    def test_payment_variable_branch_line104(self):
        """When payment_fixed=False, payment uses payment_processing_fee rate."""
        product = _minimal_product()
        product["payment_processing_fee"] = 2  # 2%
        items = self._call(product=product, payment_fixed=False, price_cny=100.0)
        labels = [i.label for i in items]
        assert "收单费" in labels  # 100 * 0.02 = 2.0 > 0.01

    def test_to_rate_converts_percentage_above_1(self):
        """to_rate: if val >= 1 → val/100."""
        product = _minimal_product()
        product["commission_rate"] = 10  # → 0.10
        items = self._call(product=product, price_cny=200.0)
        # commission = 200 * 0.10 = 20 → should appear
        commission_item = next((i for i in items if i.label == "佣金"), None)
        assert commission_item is not None
        assert abs(commission_item.value - 20.0) < 0.01

    def test_to_rate_passes_small_value_unchanged(self):
        """to_rate: if val < 1 → val is returned as-is (already a rate)."""
        product = _minimal_product()
        product["commission_rate"] = 0.05  # already a fraction → stays 0.05
        items = self._call(product=product, price_cny=200.0)
        commission_item = next((i for i in items if i.label == "佣金"), None)
        # 200 * 0.05 = 10.0 → should appear
        assert commission_item is not None
        assert abs(commission_item.value - 10.0) < 0.01

    def test_zero_fees_excluded(self):
        """Items with abs(value) <= 0.01 are excluded (except 运营利润)."""
        product = {
            "unit_price": 0,
            "labeling_fee": 0,
            "shipping_fee": 0,
            "commission_rate": 0,
            "promotion_cost_rate": 0,
            "withdrawal_fee_rate": 0,
            "payment_processing_fee": 0,
            "return_rate": 0,
            "vat_rate": 0,
        }
        items = self._call(
            product=product,
            logistics_cost_cny=0,
            commission_rub=0,
            payment_rub=0,
            payment_fixed=False,
            expected_profit=0,
        )
        # Only 运营利润 survives the filter
        assert all(i.label == "运营利润" for i in items)

    def test_vat_included(self):
        product = _minimal_product()
        product["vat_rate"] = 20  # 20%
        items = self._call(product=product, price_cny=100.0)
        vat_item = next((i for i in items if i.label == "增值税"), None)
        assert vat_item is not None
        assert abs(vat_item.value - 20.0) < 0.01

    def test_agency_fee_from_commission_rub(self):
        """agency_cny = commission_rub * rate."""
        items = self._call(commission_rub=100.0, rate=0.085)
        agency_item = next((i for i in items if i.label == "代理费"), None)
        assert agency_item is not None
        assert abs(agency_item.value - round(100.0 * 0.085, 2)) < 0.01

    def test_zero_commission_rub_no_agency(self):
        """When commission_rub=0, agency_cny=0 so 代理费 is excluded."""
        items = self._call(commission_rub=0)
        labels = [i.label for i in items]
        assert "代理费" not in labels


# ===========================================================================
# Unit tests: format_result (lines 132-200)
# ===========================================================================


class TestFormatResult:
    def _good_res(self, is_land=True):
        prefix = "land" if is_land else "air"
        return {
            "suggested_price": 100.0,
            "land_price": 100.0,
            "air_price": 100.0,
            f"{prefix}_cost": 5.0,
            f"best_{prefix}": {
                "name": "顺丰",
                "min_days": 3,
                "max_days": 7,
                "priority_group": "A",
            },
            f"{prefix}_expected_profit": 20.0,
            "profit_margin": 0.2,
            "land_profit_margin": 0.2,
            "air_profit_margin": 0.2,
            f"{prefix}_pricing_mode": "cost_plus",
            f"{prefix}_commission_info": 10.0,
            f"{prefix}_payment_info": 5.0,
            f"{prefix}_payment_fixed": False,
            f"avg_{prefix}_cost": 6.0,
            f"avg_{prefix}_days": 5.0,
            f"saved_{prefix}_cost": 1.0,
            f"saved_{prefix}_days": 0.5,
        }

    def test_unavailable_when_no_res(self):
        item = format_result(None, _minimal_product(), 0.085)
        assert item.is_available is False
        assert item.price_cny == 0
        assert item.breakdown == []

    def test_unavailable_when_no_suggested_price(self):
        item = format_result({"suggested_price": None}, _minimal_product(), 0.085)
        assert item.is_available is False

    def test_available_is_land_true_lines153_173(self):
        """Exercises lines 153-173: is_land=True path."""
        res = self._good_res(is_land=True)
        item = format_result(res, _minimal_product(), 0.085, is_land=True)
        assert item.is_available is True
        assert item.price_cny == 100.0
        assert item.logistics_name == "顺丰"
        assert item.days_min == 3
        assert item.days_max == 7
        assert item.pricing_mode == "cost_plus"
        assert item.profit_cny == 20.0
        assert abs(item.profit_margin_pct - 0.2) < 0.01

    def test_available_is_land_false_lines153_173(self):
        """Exercises lines 153-173: is_land=False path."""
        res = self._good_res(is_land=False)
        item = format_result(res, _minimal_product(), 0.085, is_land=False)
        assert item.is_available is True
        assert item.logistics_name == "顺丰"

    def test_price_rub_calculated(self):
        res = self._good_res(is_land=True)
        item = format_result(res, _minimal_product(), rate=0.1, is_land=True)
        assert abs(item.price_rub - round(100.0 / 0.1, 2)) < 0.01

    def test_zero_rate_no_division_error(self):
        res = self._good_res(is_land=True)
        item = format_result(res, _minimal_product(), rate=0, is_land=True)
        assert item.price_rub == 0

    def test_breakdown_populated(self):
        res = self._good_res(is_land=True)
        item = format_result(res, _minimal_product(), 0.085, is_land=True)
        assert isinstance(item.breakdown, list)
        # 运营利润 is always present
        labels = [b.label for b in item.breakdown]
        assert "运营利润" in labels

    def test_no_best_log(self):
        """best_land is missing → defaults used."""
        res = self._good_res(is_land=True)
        del res["best_land"]
        item = format_result(res, _minimal_product(), 0.085, is_land=True)
        assert item.is_available is True
        assert item.logistics_name == ""
        assert item.days_min == 0

    def test_avg_saved_fields(self):
        res = self._good_res(is_land=True)
        item = format_result(res, _minimal_product(), 0.085, is_land=True)
        assert item.avg_cost == round(6.0, 4)
        assert item.saved_cost == round(1.0, 4)
        assert item.avg_days == round(5.0, 2)
        assert item.saved_days == round(0.5, 2)


# ===========================================================================
# Unit tests: format_combo
# ===========================================================================


class TestFormatCombo:
    def test_builds_combo_result(self):
        empty = PricingResultItem()
        combo_results = {
            "land": empty,
            "air": empty,
        }
        result = format_combo(combo_results)
        assert result.land is empty
        assert result.air is empty

    def test_missing_keys_use_default_pricingresultitem(self):
        result = format_combo({})
        # PricingComboResult fields have default PricingResultItem() via get()
        assert result.land is not None


# ===========================================================================
# Integration tests: /api/pricing/calculate endpoint
# ===========================================================================


def _default_calc_return():
    return {
        "suggested_price": None,
        "filtered_logistics": {"land": [], "air": []},
    }


