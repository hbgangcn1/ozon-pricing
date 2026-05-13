import sys
import os
import time
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402
from api.main import app  # noqa: E402
from api import dependencies  # noqa: E402
from database import get_db  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _ensure_overrides():
    app.dependency_overrides[dependencies.get_current_user_id] = lambda: 1
    app.dependency_overrides[dependencies.require_admin] = lambda: 1
    yield
    app.dependency_overrides.pop(dependencies.get_current_user_id, None)
    app.dependency_overrides.pop(dependencies.require_admin, None)


def _db_override(session):
    async def override():
        yield session

    return override


def _default_calc_return():
    return {
        "suggested_price": None,
        "filtered_logistics": {"land": [], "air": []},
    }


class TestCalculateEndpointPreciseMode:
    @patch("api.routes.pricing.calculate_pricing")
    @patch("api.routes.pricing.get_user_logistics", new_callable=AsyncMock)
    @patch("api.routes.pricing.get_fallback_exchange_rate")
    @patch("api.routes.pricing.get_fallback_usd_rate")
    def test_precise_mode_free_user_gets_403(
        self, mock_usd, mock_rate, mock_logistics, mock_calc
    ):
        mock_rate.return_value = 0.085
        mock_usd.return_value = 7.2
        mock_logistics.return_value = []
        mock_calc.return_value = _default_calc_return()

        mock_user = MagicMock()
        mock_user.subscription_type = "free"
        mock_user.trial_expires_at = 0

        mock_session = AsyncMock()
        mock_session.execute.return_value = MagicMock(
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        )
        mock_session.get.return_value = mock_user

        app.dependency_overrides[get_db] = _db_override(mock_session)
        try:
            r = client.post(
                "/api/pricing/calculate",
                json={
                    "mode": "precise",
                    "product_data": {"name": "x", "weight_g": 100},
                },
                headers={"Authorization": "Bearer faketoken"},
            )
            assert r.status_code == 403
            assert "精准模式" in r.json()["detail"]
        finally:
            del app.dependency_overrides[get_db]

    @patch("api.routes.pricing.calculate_pricing")
    @patch("api.routes.pricing.get_user_logistics", new_callable=AsyncMock)
    @patch("api.routes.pricing.get_fallback_exchange_rate")
    @patch("api.routes.pricing.get_fallback_usd_rate")
    def test_precise_mode_efficiency_user_gets_403(
        self, mock_usd, mock_rate, mock_logistics, mock_calc
    ):
        mock_rate.return_value = 0.085
        mock_usd.return_value = 7.2
        mock_logistics.return_value = []
        mock_calc.return_value = _default_calc_return()

        mock_user = MagicMock()
        mock_user.subscription_type = "efficiency"
        mock_user.trial_expires_at = 0

        mock_session = AsyncMock()
        mock_session.execute.return_value = MagicMock(
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        )
        mock_session.get.return_value = mock_user

        app.dependency_overrides[get_db] = _db_override(mock_session)
        try:
            r = client.post(
                "/api/pricing/calculate",
                json={
                    "mode": "precise",
                    "product_data": {"name": "x", "weight_g": 100},
                },
                headers={"Authorization": "Bearer faketoken"},
            )
            assert r.status_code == 403
        finally:
            del app.dependency_overrides[get_db]

    @patch("api.routes.pricing.calculate_pricing")
    @patch("api.routes.pricing.get_user_logistics", new_callable=AsyncMock)
    @patch("api.routes.pricing.get_fallback_exchange_rate")
    @patch("api.routes.pricing.get_fallback_usd_rate")
    def test_precise_mode_enterprise_user_allowed(
        self, mock_usd, mock_rate, mock_logistics, mock_calc
    ):
        mock_rate.return_value = 0.085
        mock_usd.return_value = 7.2
        mock_logistics.return_value = []
        mock_calc.return_value = _default_calc_return()

        mock_user = MagicMock()
        mock_user.subscription_type = "enterprise"
        mock_user.subscription_expires = int(time.time()) + 365 * 86400
        mock_user.trial_expires_at = 0

        mock_session = AsyncMock()
        mock_session.execute.return_value = MagicMock(
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        )
        mock_session.get.return_value = mock_user

        app.dependency_overrides[get_db] = _db_override(mock_session)
        try:
            r = client.post(
                "/api/pricing/calculate",
                json={
                    "mode": "precise",
                    "product_data": {"name": "x", "weight_g": 100},
                },
                headers={"Authorization": "Bearer faketoken"},
            )
            assert r.status_code == 200
        finally:
            del app.dependency_overrides[get_db]

    @patch("api.routes.pricing.calculate_pricing")
    @patch("api.routes.pricing.get_user_logistics", new_callable=AsyncMock)
    @patch("api.routes.pricing.get_fallback_exchange_rate")
    @patch("api.routes.pricing.get_fallback_usd_rate")
    def test_precise_mode_no_user_in_db_denied(
        self, mock_usd, mock_rate, mock_logistics, mock_calc
    ):
        mock_rate.return_value = 0.085
        mock_usd.return_value = 7.2
        mock_logistics.return_value = []
        mock_calc.return_value = _default_calc_return()

        mock_session = AsyncMock()
        mock_session.execute.return_value = MagicMock(
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        )
        mock_session.get.return_value = None

        app.dependency_overrides[get_db] = _db_override(mock_session)
        try:
            r = client.post(
                "/api/pricing/calculate",
                json={
                    "mode": "precise",
                    "product_data": {"name": "x", "weight_g": 100},
                },
                headers={"Authorization": "Bearer faketoken"},
            )
            assert r.status_code == 403
        finally:
            del app.dependency_overrides[get_db]


class TestCalculateEndpointProductId:
    @patch("api.routes.pricing.calculate_pricing")
    @patch("api.routes.pricing.get_user_logistics", new_callable=AsyncMock)
    @patch("api.routes.pricing.get_fallback_exchange_rate")
    @patch("api.routes.pricing.get_fallback_usd_rate")
    @patch("api.routes.pricing.get_product_by_id", new_callable=AsyncMock)
    def test_product_id_found(
        self, mock_get_product, mock_usd, mock_rate, mock_logistics, mock_calc
    ):
        mock_rate.return_value = 0.085
        mock_usd.return_value = 7.2
        mock_logistics.return_value = []
        mock_calc.return_value = _default_calc_return()
        mock_get_product.return_value = {
            "name": "found_product",
            "weight_g": 200,
            "unit_price": 15.0,
        }

        mock_session = AsyncMock()
        mock_session.execute.return_value = MagicMock(
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        )

        app.dependency_overrides[get_db] = _db_override(mock_session)
        try:
            r = client.post(
                "/api/pricing/calculate",
                json={"mode": "detailed", "product_id": 42},
                headers={"Authorization": "Bearer faketoken"},
            )
            assert r.status_code == 200
        finally:
            del app.dependency_overrides[get_db]

    @patch("api.routes.pricing.calculate_pricing")
    @patch("api.routes.pricing.get_user_logistics", new_callable=AsyncMock)
    @patch("api.routes.pricing.get_fallback_exchange_rate")
    @patch("api.routes.pricing.get_fallback_usd_rate")
    @patch("api.routes.pricing.get_product_by_id", new_callable=AsyncMock)
    def test_product_id_not_found(
        self, mock_get_product, mock_usd, mock_rate, mock_logistics, mock_calc
    ):
        mock_rate.return_value = 0.085
        mock_usd.return_value = 7.2
        mock_logistics.return_value = []
        mock_calc.return_value = _default_calc_return()
        mock_get_product.return_value = None

        mock_session = AsyncMock()

        app.dependency_overrides[get_db] = _db_override(mock_session)
        try:
            r = client.post(
                "/api/pricing/calculate",
                json={"mode": "detailed", "product_id": 9999},
                headers={"Authorization": "Bearer faketoken"},
            )
            assert r.status_code == 404
            assert "产品不存在" in r.json()["detail"]
        finally:
            del app.dependency_overrides[get_db]


class TestCalculateEndpointDetailedMode:
    @patch("api.routes.pricing.calculate_pricing")
    @patch("api.routes.pricing.get_user_logistics", new_callable=AsyncMock)
    @patch("api.routes.pricing.get_fallback_exchange_rate")
    @patch("api.routes.pricing.get_fallback_usd_rate")
    def test_detailed_mode_returns_product_in_response(
        self, mock_usd, mock_rate, mock_logistics, mock_calc
    ):
        mock_rate.return_value = 0.085
        mock_usd.return_value = 7.2
        mock_logistics.return_value = []
        mock_calc.return_value = _default_calc_return()

        mock_session = AsyncMock()
        mock_session.execute.return_value = MagicMock(
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        )

        app.dependency_overrides[get_db] = _db_override(mock_session)
        try:
            payload = {
                "mode": "detailed",
                "product_data": {"name": "widget", "weight_g": 300, "unit_price": 20.0},
            }
            r = client.post(
                "/api/pricing/calculate",
                json=payload,
                headers={"Authorization": "Bearer faketoken"},
            )
            assert r.status_code == 200
            body = r.json()
            assert body["product"] is not None
            assert body["product"]["name"] == "widget"
        finally:
            del app.dependency_overrides[get_db]

    @patch("api.routes.pricing.calculate_pricing")
    @patch("api.routes.pricing.get_user_logistics", new_callable=AsyncMock)
    @patch("api.routes.pricing.get_fallback_exchange_rate")
    @patch("api.routes.pricing.get_fallback_usd_rate")
    def test_fast_mode_product_is_none_in_response(
        self, mock_usd, mock_rate, mock_logistics, mock_calc
    ):
        mock_rate.return_value = 0.085
        mock_usd.return_value = 7.2
        mock_logistics.return_value = []
        mock_calc.return_value = _default_calc_return()

        mock_session = AsyncMock()
        mock_session.execute.return_value = MagicMock(
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        )

        app.dependency_overrides[get_db] = _db_override(mock_session)
        try:
            r = client.post(
                "/api/pricing/calculate",
                json={"mode": "fast", "product_data": {"name": "x", "weight_g": 100}},
                headers={"Authorization": "Bearer faketoken"},
            )
            assert r.status_code == 200
            assert r.json()["product"] is None
        finally:
            del app.dependency_overrides[get_db]


class TestCalculateEndpointLogisticsTypeFilter:
    @patch("api.routes.pricing.calculate_pricing")
    @patch("api.routes.pricing.get_user_logistics", new_callable=AsyncMock)
    @patch("api.routes.pricing.get_fallback_exchange_rate")
    @patch("api.routes.pricing.get_fallback_usd_rate")
    def test_logistics_with_land_and_air_rows(
        self, mock_usd, mock_rate, mock_logistics, mock_calc
    ):
        mock_rate.return_value = 0.085
        mock_usd.return_value = 7.2
        mock_logistics.return_value = [
            {"type": "land", "delivery_method": "pickup"},
            {"type": "air", "delivery_method": "door"},
        ]
        mock_calc.return_value = _default_calc_return()

        mock_session = AsyncMock()
        mock_session.execute.return_value = MagicMock(
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        )

        app.dependency_overrides[get_db] = _db_override(mock_session)
        try:
            r = client.post(
                "/api/pricing/calculate",
                json={"mode": "fast", "product_data": {"name": "x", "weight_g": 100}},
                headers={"Authorization": "Bearer faketoken"},
            )
            assert r.status_code == 200
        finally:
            del app.dependency_overrides[get_db]


class TestCalculateEndpointWithRichResult:
    def _rich_calc_return(self):
        return {
            "suggested_price": 150.0,
            "land_price": 150.0,
            "air_price": 150.0,
            "land_cost": 8.0,
            "air_cost": 12.0,
            "best_land": {
                "name": "陆运A",
                "min_days": 5,
                "max_days": 10,
                "priority_group": "B",
            },
            "best_air": {
                "name": "空运A",
                "min_days": 2,
                "max_days": 4,
                "priority_group": "A",
            },
            "land_expected_profit": 30.0,
            "air_expected_profit": 25.0,
            "profit_margin": 0.2,
            "land_pricing_mode": "margin",
            "air_pricing_mode": "margin",
            "land_commission_info": 5.0,
            "air_commission_info": 5.0,
            "land_payment_info": 2.0,
            "air_payment_info": 2.0,
            "land_payment_fixed": False,
            "air_payment_fixed": False,
            "avg_land_cost": 9.0,
            "avg_air_cost": 13.0,
            "avg_land_days": 7.0,
            "avg_air_days": 3.0,
            "saved_land_cost": 1.0,
            "saved_air_cost": 1.0,
            "saved_land_days": 0.5,
            "saved_air_days": 0.5,
            "filtered_logistics": {"land": ["L1"], "air": ["A1"]},
        }

    @patch("api.routes.pricing.calculate_pricing")
    @patch("api.routes.pricing.get_user_logistics", new_callable=AsyncMock)
    @patch("api.routes.pricing.get_fallback_exchange_rate")
    @patch("api.routes.pricing.get_fallback_usd_rate")
    def test_detailed_mode_rich_result_response_structure(
        self, mock_usd, mock_rate, mock_logistics, mock_calc
    ):
        mock_rate.return_value = 0.085
        mock_usd.return_value = 7.2
        mock_logistics.return_value = []
        mock_calc.return_value = self._rich_calc_return()

        mock_session = AsyncMock()
        mock_session.execute.return_value = MagicMock(
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        )

        app.dependency_overrides[get_db] = _db_override(mock_session)
        try:
            payload = {
                "mode": "detailed",
                "product_data": {
                    "name": "rich",
                    "weight_g": 500,
                    "unit_price": 50.0,
                    "commission_rate": 5,
                    "vat_rate": 20,
                },
            }
            r = client.post(
                "/api/pricing/calculate",
                json=payload,
                headers={"Authorization": "Bearer faketoken"},
            )
            assert r.status_code == 200
            body = r.json()
            assert body["calculation_mode"] == "detailed"
            assert "price_priority" in body
            assert "speed_priority" in body
            assert "exchange_rates" in body
            assert body["exchange_rates"]["rub_cny"] == pytest.approx(0.085, abs=1e-4)
        finally:
            del app.dependency_overrides[get_db]


class TestCalculateBreakevenResponses:
    def _rich_calc_return(self, suggested_price, margin, logistics_name):
        return {
            "suggested_price": suggested_price,
            "land_price": suggested_price,
            "air_price": suggested_price,
            "land_cost": 8.0,
            "air_cost": 12.0,
            "best_land": {
                "name": f"{logistics_name}-陆运",
                "min_days": 5,
                "max_days": 10,
                "priority_group": "B",
            },
            "best_air": {
                "name": f"{logistics_name}-空运",
                "min_days": 2,
                "max_days": 4,
                "priority_group": "A",
            },
            "land_expected_profit": 30.0,
            "air_expected_profit": 25.0,
            "profit_margin": margin,
            "land_pricing_mode": "margin",
            "air_pricing_mode": "margin",
            "land_commission_info": 5.0,
            "air_commission_info": 5.0,
            "land_payment_info": 2.0,
            "air_payment_info": 2.0,
            "land_payment_fixed": False,
            "air_payment_fixed": False,
            "avg_land_cost": 9.0,
            "avg_air_cost": 13.0,
            "avg_land_days": 7.0,
            "avg_air_days": 3.0,
            "saved_land_cost": 1.0,
            "saved_air_cost": 1.0,
            "saved_land_days": 0.5,
            "saved_air_days": 0.5,
            "filtered_logistics": {
                "land": [{"name": "L1", "reason": "未被选中"}],
                "air": [],
            },
        }

    @patch("api.routes.pricing.calculate_pricing")
    @patch("api.routes.pricing.get_user_logistics", new_callable=AsyncMock)
    @patch("api.routes.pricing.get_fallback_exchange_rate")
    @patch("api.routes.pricing.get_fallback_usd_rate")
    def test_calculate_returns_normal_and_breakeven_results(
        self, mock_usd, mock_rate, mock_logistics, mock_calc
    ):
        mock_rate.return_value = 0.085
        mock_usd.return_value = 7.2
        mock_logistics.return_value = [
            {"type": "land", "delivery_method": "pickup", "name": "陆运规则"},
            {"type": "air", "delivery_method": "door", "name": "空运规则"},
        ]
        seen_margins = []

        def side_effect(product, *_args, **_kwargs):
            seen_margins.append(product.get("target_profit_margin"))
            if product.get("target_profit_margin") == 0:
                return self._rich_calc_return(88.0, 0.0, "盈亏平衡")
            return self._rich_calc_return(120.0, 0.35, "常规定价")

        mock_calc.side_effect = side_effect

        mock_session = AsyncMock()
        mock_session.execute.return_value = MagicMock(
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        )
        mock_session.get.return_value = MagicMock(
                    subscription_type="enterprise",
                    subscription_expires=int(time.time()) + 365 * 86400,
                    trial_expires_at=0,
                )

        app.dependency_overrides[get_db] = _db_override(mock_session)
        try:
            payload = {
                "mode": "precise",
                "product_data": {
                    "name": "rich",
                    "weight_g": 500,
                    "unit_price": 50.0,
                    "target_profit_margin": 0.35,
                    "commission_rate": 5,
                    "vat_rate": 20,
                },
            }
            response = client.post(
                "/api/pricing/calculate",
                json=payload,
                headers={"Authorization": "Bearer faketoken"},
            )
            assert response.status_code == 200
            body = response.json()
            assert body["price_priority"]["land"]["price_cny"] == 120.0
            assert body["breakeven_price_priority"]["land"]["price_cny"] == 88.0
            assert body["breakeven_speed_priority"]["air"]["price_cny"] == 88.0
            assert body["product"]["target_profit_margin"] == 0.35
            assert Decimal("0.35") in seen_margins
            assert Decimal("0") in seen_margins
        finally:
            del app.dependency_overrides[get_db]

    @patch("api.routes.pricing.calculate_pricing_grouped")
    @patch("api.routes.pricing.get_user_logistics", new_callable=AsyncMock)
    @patch("api.routes.pricing.get_fallback_exchange_rate")
    @patch("api.routes.pricing.get_fallback_usd_rate")
    def test_calculate_grouped_returns_normal_and_breakeven_results(
        self, mock_usd, mock_rate, mock_logistics, mock_grouped
    ):
        mock_rate.return_value = 0.085
        mock_usd.return_value = 7.2
        mock_logistics.return_value = [{"type": "land", "delivery_method": "pickup"}]
        seen_margins = []

        def side_effect(product, *_args, **_kwargs):
            seen_margins.append(product.get("target_profit_margin"))
            if product.get("target_profit_margin") == 0:
                group = self._rich_calc_return(90.0, 0.0, "分组盈亏平衡")
            else:
                group = self._rich_calc_return(130.0, 0.4, "分组常规")
            dual = {
                "price_priority": group,
                "speed_priority": group,
            }
            return {
                "rfbs_ru": dual,
                "rfbs_AZ": dual,
                "rfbs_AM": dual,
                "rfbs_BY": dual,
                "rfbs_GE": dual,
                "rfbs_KGZ": dual,
                "rfbs_KZ": dual,
                "rfbs_UZ": dual,
                "fbp_ru": dual,
                "fbp_cis": dual,
            }

        mock_grouped.side_effect = side_effect

        mock_session = AsyncMock()
        mock_session.get.return_value = MagicMock(
                    subscription_type="enterprise",
                    subscription_expires=int(time.time()) + 365 * 86400,
                    trial_expires_at=0,
                )

        app.dependency_overrides[get_db] = _db_override(mock_session)
        try:
            payload = {
                "mode": "precise",
                "product_data": {
                    "name": "grouped",
                    "weight_g": 500,
                    "unit_price": 50.0,
                    "target_profit_margin": 0.4,
                },
            }
            response = client.post(
                "/api/pricing/calculate-grouped",
                json=payload,
                headers={"Authorization": "Bearer faketoken"},
            )
            assert response.status_code == 200
            body = response.json()
            assert body["rfbs_ru"]["price_priority"]["land"]["price_cny"] == 130.0
            assert (
                body["breakeven_rfbs_ru"]["price_priority"]["land"]["price_cny"] == 90.0
            )
            assert (
                body["breakeven_fbp_cis"]["speed_priority"]["air"]["price_cny"] == 90.0
            )
            assert body["product"]["target_profit_margin"] == 0.4
            assert Decimal("0.4") in seen_margins
            assert Decimal("0") in seen_margins
        finally:
            del app.dependency_overrides[get_db]
