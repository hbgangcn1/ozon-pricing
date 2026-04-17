import os
import sys
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api import dependencies  # noqa: E402
from api.main import app  # noqa: E402
from api.routes.pricing import format_result  # noqa: E402
from database import get_db  # noqa: E402


client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def ensure_overrides():
    app.dependency_overrides[dependencies.get_current_user_id] = lambda: 1
    yield
    app.dependency_overrides.pop(dependencies.get_current_user_id, None)
    app.dependency_overrides.pop(get_db, None)


def _db_override(session):
    async def override():
        yield session

    return override


def _product():
    return {
        "unit_price": 10.0,
        "labeling_fee": 0.5,
        "shipping_fee": 1.0,
        "commission_rate": 5,
        "promotion_cost_rate": 3,
        "withdrawal_fee_rate": 1,
        "payment_processing_fee": 2,
        "return_rate": 0,
        "vat_rate": 20,
    }


def _result(suggested_price):
    return {
        "suggested_price": suggested_price,
        "land_price": suggested_price,
        "land_cost": 0,
        "best_land": {
            "name": "零运费线路",
            "min_days": 3,
            "max_days": 5,
            "priority_group": "A",
        },
        "land_expected_profit": 0,
        "profit_margin": 0,
        "land_profit_margin": 0,
        "air_profit_margin": 0,
        "land_pricing_mode": "margin",
        "land_commission_info": 0,
        "land_payment_info": 0,
        "land_payment_fixed": False,
        "avg_land_cost": 0,
        "saved_land_cost": 0,
        "avg_land_days": 0,
        "saved_land_days": 0,
        "filtered_logistics": {"land": [], "air": []},
    }


def test_format_result_returns_available_when_suggested_price_is_zero():
    item = format_result(_result(0), _product(), rate=0.085, is_land=True)

    assert item.is_available is True
    assert item.price_cny == 0


def test_format_result_returns_unavailable_when_suggested_price_is_none():
    item = format_result(_result(None), _product(), rate=0.085, is_land=True)

    assert item.is_available is False
    assert item.price_cny == 0


def test_format_result_returns_available_when_suggested_price_is_positive():
    item = format_result(_result(15.5), _product(), rate=0.085, is_land=True)

    assert item.is_available is True
    assert item.price_cny == 15.5


def test_format_result_returns_unavailable_for_empty_dict():
    item = format_result({}, _product(), rate=0.085, is_land=True)

    assert item.is_available is False


def test_format_result_returns_unavailable_for_none_result():
    item = format_result(None, _product(), rate=0.085, is_land=True)

    assert item.is_available is False


@patch("api.routes.pricing.calculate_pricing")
@patch("api.routes.pricing.get_user_logistics", new_callable=AsyncMock)
@patch("api.routes.pricing.get_fallback_exchange_rate")
@patch("api.routes.pricing.get_fallback_usd_rate")
def test_precise_calculate_endpoint_keeps_zero_price_result_available(
    mock_usd,
    mock_rate,
    mock_logistics,
    mock_calc,
):
    mock_rate.return_value = 0.085
    mock_usd.return_value = 7.2
    mock_logistics.return_value = [
        {"type": "land", "delivery_method": "pickup", "name": "零运费线路"}
    ]

    mock_calc.side_effect = lambda *_args, **_kwargs: _result(0)

    mock_session = AsyncMock()
    mock_session.get.return_value = MagicMock(user_type="enterprise")
    app.dependency_overrides[get_db] = _db_override(mock_session)

    response = client.post(
        "/api/pricing/calculate",
        json={
            "mode": "precise",
            "product_data": {
                "name": "zero-price-product",
                "weight_g": 100,
                "unit_price": 10.0,
                "target_profit_margin": 0.35,
            },
        },
        headers={"Authorization": "Bearer faketoken"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["price_priority"]["land"]["price_cny"] == 0
    assert body["price_priority"]["land"]["is_available"] is True
    assert body["breakeven_price_priority"]["land"]["is_available"] is True


def test_format_result_air_uses_air_profit_margin():
    res = {
        "suggested_price": 100,
        "air_price": 100,
        "air_cost": 8.5,
        "best_air": {
            "name": "空运线路",
            "min_days": 1,
            "max_days": 3,
            "priority_group": "B",
        },
        "air_expected_profit": 12.5,
        "air_profit_margin": 0.18,
        "land_profit_margin": 0.22,
        "profit_margin": 0.22,
        "air_pricing_mode": "margin",
        "air_commission_info": 15,
        "air_payment_info": 10,
        "air_payment_fixed": True,
        "avg_air_cost": 9.0,
        "saved_air_cost": 0.5,
        "avg_air_days": 2.0,
        "saved_air_days": 1.0,
    }
    item = format_result(res, _product(), rate=0.085, is_land=False)
    assert item.is_available is True
    assert item.profit_margin_pct == Decimal("0.18")


def test_format_result_land_uses_land_profit_margin():
    res = {
        "suggested_price": 80,
        "land_price": 80,
        "land_cost": 5.0,
        "best_land": {
            "name": "陆运线路",
            "min_days": 5,
            "max_days": 10,
            "priority_group": "A",
        },
        "land_expected_profit": 10.0,
        "land_profit_margin": 0.22,
        "air_profit_margin": 0.18,
        "profit_margin": 0.22,
        "land_pricing_mode": "margin",
        "land_commission_info": 15,
        "land_payment_info": 10,
        "land_payment_fixed": False,
        "avg_land_cost": 6.0,
        "saved_land_cost": 1.0,
        "avg_land_days": 7.0,
        "saved_land_days": 2.0,
    }
    item = format_result(res, _product(), rate=0.085, is_land=True)
    assert item.is_available is True
    assert item.profit_margin_pct == Decimal("0.22")
