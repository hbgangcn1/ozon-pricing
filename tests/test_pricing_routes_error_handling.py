import logging
from decimal import Decimal
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient
import pytest

from api import dependencies
from api.main import app
from api.routes import pricing as pricing_route
from database import get_db
from pricing.calculate_pricing import calculate_pricing


client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _dependency_overrides():  # pyright: ignore[reportUnusedFunction]
    app.dependency_overrides[dependencies.get_current_user_id] = lambda: 1

    async def override_db():
        yield AsyncMock()

    app.dependency_overrides[get_db] = override_db
    yield
    app.dependency_overrides.pop(dependencies.get_current_user_id, None)
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture(autouse=True)
def _quota_allowed(monkeypatch):  # pyright: ignore[reportUnusedFunction]
    async def allowed(_session, _user_id):
        return True

    monkeypatch.setattr(pricing_route, "decrement_user_calculations", allowed)


def _product():
    return {
        "weight_g": 500,
        "length_cm": 10,
        "width_cm": 10,
        "height_cm": 5,
        "unit_price": Decimal("20.0"),
        "labeling_fee": Decimal("0"),
        "shipping_fee": Decimal("0"),
        "target_profit_margin": Decimal("0.2"),
        "commission_rate": Decimal("0.08"),
        "withdrawal_fee_rate": Decimal("0.02"),
        "promotion_cost_rate": Decimal("0"),
        "payment_processing_fee": Decimal("0"),
        "return_rate": Decimal("0"),
        "vat_rate": Decimal("0"),
    }


def _land_rule():
    return {
        "name": "陆运A",
        "type": "land",
        "fee_mode": "base_plus_continue",
        "base_fee": Decimal("5"),
        "continue_unit": 100,
        "continue_fee": Decimal("1"),
        "min_weight": 0,
        "max_weight": 0,
        "volume_mode": "none",
        "volume_coefficient": 5000,
        "min_days": 3,
        "max_days": 7,
        "price_limit_cny": Decimal("0"),
        "price_min_cny": Decimal("0"),
    }


def _assert_sanitized_500(response):
    assert response.status_code == 500
    body = response.json()
    assert body == {"detail": "计算失败，请稍后重试"}
    assert "boom" not in str(body)


def test_calculate_internal_error_returns_sanitized_500(monkeypatch):
    async def broken_logistics(_session, _user_id):
        raise RuntimeError("boom calculate leak")

    monkeypatch.setattr(pricing_route, "get_user_logistics", broken_logistics)
    response = client.post(
        "/api/pricing/calculate",
        json={"mode": "fast", "product_data": {"name": "x", "weight_g": 100}},
    )
    _assert_sanitized_500(response)


def test_calculate_grouped_internal_error_returns_sanitized_500(monkeypatch):
    async def broken_logistics(_session, _user_id):
        raise RuntimeError("boom grouped leak")

    monkeypatch.setattr(pricing_route, "get_user_logistics", broken_logistics)
    response = client.post(
        "/api/pricing/calculate-grouped",
        json={"mode": "fast", "product_data": {"name": "x", "weight_g": 100}},
    )
    _assert_sanitized_500(response)


def test_sse_progress_callback_warning_and_calculation_continues(caplog):
    def broken_callback():
        raise RuntimeError("callback failed")

    caplog.set_level(logging.WARNING, logger="pricing.calculate_pricing")
    result = calculate_pricing(
        _product(),
        [_land_rule()],
        [],
        progress_callback=broken_callback,
    )

    assert result["best_land"] is not None
    assert "SSE progress callback failed" in caplog.text
