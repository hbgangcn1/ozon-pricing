"""Route smoke tests for API endpoints."""

# pyright: reportUnusedFunction=false

import os
import sys
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("ALLOWED_ORIGINS", "http://testserver")

from fastapi.testclient import TestClient  # noqa: E402
from api.main import app  # noqa: E402
from api import dependencies  # noqa: E402
from database import get_db  # noqa: E402


@pytest.fixture(autouse=True)
def _patch_recalculate():
    with patch(
        "api.routes.logistics.recalculate_priority_groups",
        new=AsyncMock(),
    ):
        yield


MOCK_USER = {
    "id": 1,
    "username": "testuser",
    "role": "admin",
    "user_type": "enterprise",
    "remaining_calculations": 100,
}

client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _mock_auth_dependencies(monkeypatch):
    monkeypatch.setitem(
        app.dependency_overrides,
        dependencies.get_current_user_id,
        lambda: 1,
    )
    monkeypatch.setitem(
        app.dependency_overrides,
        dependencies.require_admin,
        lambda: 1,
    )
    monkeypatch.setitem(
        app.dependency_overrides,
        dependencies.get_current_user,
        lambda: MOCK_USER,
    )


@pytest.fixture(autouse=True)
def _allow_testserver_origin(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", "http://testserver")


@pytest.fixture(autouse=True)
def _reset_username_check_limiter():
    from api.middleware.username_check_limiter import username_check_limiter
    from api.routes.auth import recover_start_limiter, recover_verify_limiter

    username_check_limiter.reset()
    recover_start_limiter.reset()
    recover_verify_limiter.reset()
    yield
    username_check_limiter.reset()
    recover_start_limiter.reset()
    recover_verify_limiter.reset()


@pytest.fixture(autouse=True)
def _preserve_username_limiter_ip_test_isolation(monkeypatch):
    from api.routes.auth import login as auth_login

    def _test_client_ip(request):
        return request.headers.get("X-Forwarded-For", "testclient").split(",")[0].strip()

    monkeypatch.setattr(auth_login, "get_username_check_client_ip", _test_client_ip)


def _logistics_row():
    return {
        "id": 1,
        "user_id": 1,
        "name": "Test",
        "type": "land",
        "min_days": 1,
        "max_days": 10,
        "price_limit_cny": 0,
        "price_min_cny": 0,
        "base_fee": 0,
        "min_weight": 0,
        "max_weight": 100000,
        "max_sum_of_sides": 0,
        "max_longest_side": 0,
        "max_second_side": 0,
        "max_third_side": 0,
        "min_second_side": 0,
        "min_length": 0,
        "max_cylinder_sum": 0,
        "min_cylinder_sum": 0,
        "max_cylinder_length": 0,
        "min_cylinder_length": 0,
        "volume_mode": "none",
        "longest_side_threshold": 0,
        "sum_of_sides_threshold": 0,
        "allow_battery": 0,
        "allow_liquid": 0,
        "battery_capacity_limit_wh": 0,
        "require_msds": 0,
        "fee_mode": "base_weight",
        "first_fee": 0,
        "first_weight_g": 0,
        "continue_fee": 0,
        "continue_unit": "g",
        "volume_coefficient": 5000,
        "delivery_method": "pickup",
        "priority_group": "D",
        "is_active": 1,
        "fulfillment_type": "rfbs",
        "destination": "RU",
        "fbp_service_level": None,
        "fbp_company": None,
        "is_smart": 0,
    }


class TestProducts:
    @patch("api.routes.products.get_all_products_for_user", new_callable=AsyncMock)
    def test_get_products(self, mock_get):
        mock_get.return_value = [
            {
                "id": 1,
                "user_id": 1,
                "name": "Widget",
                "russian_name": None,
                "category": None,
                "model": None,
                "unit_price": 10.0,
                "weight_g": 100,
                "length_cm": 10,
                "width_cm": 10,
                "height_cm": 10,
                "is_cylinder": False,
                "cylinder_diameter": 0,
                "cylinder_length": 0,
                "has_battery": False,
                "battery_capacity_wh": 0,
                "has_msds": False,
                "has_liquid": False,
                "labeling_fee": 0,
                "shipping_fee": 0,
                "battery_capacity_mah": 0,
                "battery_voltage": 0,
                "commission_rate": 0,
                "target_profit_margin": 0,
                "promotion_cost_rate": 0,
                "withdrawal_fee_rate": 0,
                "payment_processing_fee": 0,
                "return_rate": 0,
                "vat_rate": 0,
            }
        ]
        r = client.get("/api/products", headers={"Authorization": "Bearer faketoken"})
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    @patch("api.routes.products.get_product_by_id", new_callable=AsyncMock)
    def test_get_product_found(self, mock_get):
        mock_get.return_value = {
            "id": 1,
            "user_id": 1,
            "name": "Widget",
            "russian_name": None,
            "category": None,
            "model": None,
            "unit_price": 10.0,
            "weight_g": 100,
            "length_cm": 10,
            "width_cm": 10,
            "height_cm": 10,
            "is_cylinder": False,
            "cylinder_diameter": 0,
            "cylinder_length": 0,
            "has_battery": False,
            "battery_capacity_wh": 0,
            "has_msds": False,
            "has_liquid": False,
            "labeling_fee": 0,
            "shipping_fee": 0,
            "battery_capacity_mah": 0,
            "battery_voltage": 0,
            "commission_rate": 0,
            "target_profit_margin": 0,
            "promotion_cost_rate": 0,
            "withdrawal_fee_rate": 0,
            "payment_processing_fee": 0,
            "return_rate": 0,
            "vat_rate": 0,
        }
        r = client.get("/api/products/1", headers={"Authorization": "Bearer faketoken"})
        assert r.status_code == 200

    @patch("api.routes.products.get_product_by_id", new_callable=AsyncMock)
    def test_get_product_not_found(self, mock_get):
        mock_get.return_value = None
        r = client.get(
            "/api/products/999", headers={"Authorization": "Bearer faketoken"}
        )
        assert r.status_code == 404

    @patch("api.routes.products.get_product_by_id", new_callable=AsyncMock)
    @patch("api.routes.products.add_product", new_callable=AsyncMock)
    def test_create_product(self, mock_add, mock_get):
        product_row = {
            "id": 10,
            "user_id": 1,
            "name": "NewProd",
            "russian_name": None,
            "category": None,
            "model": None,
            "unit_price": 5.0,
            "weight_g": 50,
            "length_cm": 5,
            "width_cm": 5,
            "height_cm": 5,
            "is_cylinder": False,
            "cylinder_diameter": 0,
            "cylinder_length": 0,
            "has_battery": False,
            "battery_capacity_wh": 0,
            "has_msds": False,
            "has_liquid": False,
            "labeling_fee": 0,
            "shipping_fee": 0,
            "battery_capacity_mah": 0,
            "battery_voltage": 0,
            "commission_rate": 0,
            "target_profit_margin": 0,
            "promotion_cost_rate": 0,
            "withdrawal_fee_rate": 0,
            "payment_processing_fee": 0,
            "return_rate": 0,
            "vat_rate": 0,
        }
        mock_add.return_value = 10
        mock_get.return_value = product_row
        r = client.post(
            "/api/products",
            json={"name": "NewProd", "weight_g": 50},
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 201

    @patch("api.routes.products.get_product_by_id", new_callable=AsyncMock)
    @patch("api.routes.products.update_product", new_callable=AsyncMock)
    def test_update_product(self, mock_update, mock_get):
        existing = {
            "id": 1,
            "user_id": 1,
            "name": "Old",
            "russian_name": None,
            "category": None,
            "model": None,
            "unit_price": 10.0,
            "weight_g": 100,
            "length_cm": 10,
            "width_cm": 10,
            "height_cm": 10,
            "is_cylinder": False,
            "cylinder_diameter": 0,
            "cylinder_length": 0,
            "has_battery": False,
            "battery_capacity_wh": 0,
            "has_msds": False,
            "has_liquid": False,
            "labeling_fee": 0,
            "shipping_fee": 0,
            "battery_capacity_mah": 0,
            "battery_voltage": 0,
            "commission_rate": 0,
            "target_profit_margin": 0,
            "promotion_cost_rate": 0,
            "withdrawal_fee_rate": 0,
            "payment_processing_fee": 0,
            "return_rate": 0,
            "vat_rate": 0,
        }
        mock_get.side_effect = [existing, {**existing, "name": "New"}]
        mock_update.return_value = True
        r = client.put(
            "/api/products/1",
            json={"name": "New"},
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 200

    @patch("api.routes.products.delete_product", new_callable=AsyncMock)
    def test_delete_product_success(self, mock_del):
        mock_del.return_value = True
        r = client.delete(
            "/api/products/1", headers={"Authorization": "Bearer faketoken"}
        )
        assert r.status_code == 200

    @patch("api.routes.products.delete_product", new_callable=AsyncMock)
    def test_delete_product_not_found(self, mock_del):
        mock_del.return_value = False
        r = client.delete(
            "/api/products/999", headers={"Authorization": "Bearer faketoken"}
        )
        assert r.status_code == 404


class TestLogistics:
    @patch("api.routes.logistics.get_logistics_by_filters", new_callable=AsyncMock)
    def test_get_logistics_list(self, mock_get):
        mock_get.return_value = ([_logistics_row()], 1)
        r = client.get("/api/logistics", headers={"Authorization": "Bearer faketoken"})
        assert r.status_code == 200

    @patch("api.routes.logistics.get_logistics_by_id", new_callable=AsyncMock)
    def test_get_logistics_by_id(self, mock_get):
        mock_get.return_value = _logistics_row()
        r = client.get(
            "/api/logistics/1", headers={"Authorization": "Bearer faketoken"}
        )
        assert r.status_code == 200

    @patch("api.routes.logistics.get_logistics_by_id", new_callable=AsyncMock)
    def test_get_logistics_by_id_not_found(self, mock_get):
        mock_get.return_value = None
        r = client.get(
            "/api/logistics/999", headers={"Authorization": "Bearer faketoken"}
        )
        assert r.status_code == 404

    @patch("api.routes.logistics.delete_logistics", new_callable=AsyncMock)
    def test_delete_logistics_success(self, mock_del):
        mock_del.return_value = 1
        r = client.delete(
            "/api/logistics/1", headers={"Authorization": "Bearer faketoken"}
        )
        assert r.status_code == 200

    @patch("api.routes.logistics.delete_logistics", new_callable=AsyncMock)
    def test_delete_logistics_not_found(self, mock_del):
        mock_del.return_value = 0
        r = client.delete(
            "/api/logistics/999", headers={"Authorization": "Bearer faketoken"}
        )
        assert r.status_code == 404

    @patch("api.routes.logistics.batch_delete_logistics", new_callable=AsyncMock)
    def test_batch_delete_logistics(self, mock_batch):
        mock_batch.return_value = 2
        r = client.post(
            "/api/logistics/batch-delete",
            json=[1, 2],
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 200

    def test_batch_delete_empty(self):
        r = client.post(
            "/api/logistics/batch-delete",
            json=[],
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 400


class TestAdmin:
    @patch("api.routes.admin.db_admin.get_all_users", new_callable=AsyncMock)
    def test_get_users(self, mock_get):
        mock_get.return_value = {
            "users": [
                {
                    "id": 1,
                    "username": "admin",
                    "role": "admin",
                    "user_type": "enterprise",
                    "is_frozen": 0,
                }
            ],
            "total_count": 1,
        }
        r = client.get(
            "/api/admin/users", headers={"Authorization": "Bearer faketoken"}
        )
        assert r.status_code == 200
        body = r.json()
        assert "users" in body and "total" in body

    @patch("api.routes.admin.create_user", new_callable=AsyncMock)
    def test_create_admin_user(self, mock_create):
        mock_create.return_value = 99
        r = client.post(
            "/api/admin/users",
            json={
                "username": "newadmin",
                "password": "Pass@123456",
                "role": "user",
                "user_type": "free",
            },
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 201

    def test_update_admin_user(self):
        mock_user = MagicMock()
        mock_user.id = 2
        mock_user.username = "u2"
        mock_user.role = "user"
        mock_user.user_type = "free"
        mock_user.is_frozen = 0

        mock_session = AsyncMock()
        mock_session.get.return_value = mock_user
        mock_session.flush.return_value = None

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db
        try:
            r = client.put(
                "/api/admin/users/2",
                json={"role": "user"},
                headers={"Authorization": "Bearer faketoken"},
            )
            assert r.status_code == 200
        finally:
            del app.dependency_overrides[get_db]

    @patch("api.routes.admin.db_admin.reset_user_password", new_callable=AsyncMock)
    def test_reset_password(self, mock_reset):
        mock_reset.return_value = "new_pass_123"
        mock_user = MagicMock()
        mock_user.id = 2
        mock_user.username = "u2"
        mock_user.role = "user"

        mock_session = AsyncMock()
        mock_session.get.return_value = mock_user

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db
        try:
            r = client.post(
                "/api/admin/users/2/reset-password",
                headers={"Authorization": "Bearer faketoken"},
            )
            assert r.status_code == 200
        finally:
            del app.dependency_overrides[get_db]

    @patch("api.routes.admin.db_admin.delete_user_admin", new_callable=AsyncMock)
    def test_delete_admin_user(self, mock_del):
        mock_del.return_value = True
        r = client.delete(
            "/api/admin/users/2",
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 200

    def test_delete_superadmin_blocked(self):
        r = client.delete(
            "/api/admin/users/1",
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 400


class TestOrders:
    @patch("api.routes.orders.get_user_orders", new_callable=AsyncMock)
    def test_get_orders_empty(self, mock_get):
        mock_get.return_value = {"orders": [], "total": 0}
        r = client.get("/api/orders", headers={"Authorization": "Bearer faketoken"})
        assert r.status_code == 200
        data = r.json()
        assert data["orders"] == []
        assert data["total"] == 0

    @patch("api.routes.orders.get_user_orders", new_callable=AsyncMock)
    def test_get_orders_with_data(self, mock_get):
        mock_get.return_value = {
            "orders": [
                {
                    "id": 1,
                    "order_id": "ORD001",
                    "order_type": "efficiency",
                    "amount": 99.0,
                    "status": "paid",
                    "created_at": "2024-01-01",
                    "updated_at": None,
                }
            ],
            "total": 1,
        }
        r = client.get("/api/orders", headers={"Authorization": "Bearer faketoken"})
        assert r.status_code == 200
        data = r.json()
        assert len(data["orders"]) == 1
        assert data["orders"][0]["order_id"] == "ORD001"
        assert data["total"] == 1
