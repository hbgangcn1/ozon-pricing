import sys
import os
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402
from api.main import app  # noqa: E402
from api import dependencies  # noqa: E402

MOCK_USER = {
    "id": 1,
    "username": "testuser",
    "role": "admin",
    "user_type": "enterprise",
    "remaining_calculations": 100,
}

app.dependency_overrides[dependencies.get_current_user_id] = lambda: 1
app.dependency_overrides[dependencies.require_admin] = lambda: 1
app.dependency_overrides[dependencies.get_current_user] = lambda: MOCK_USER

client = TestClient(app, raise_server_exceptions=False)


def _make_db_ctx(fetchone=None, fetchall=None, description=None, rowcount=1):
    cursor = MagicMock()
    cursor.fetchone.return_value = fetchone
    cursor.fetchall.return_value = fetchall or []
    cursor.description = description or []
    cursor.rowcount = rowcount
    conn = MagicMock()
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=(conn, cursor))
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx, conn, cursor


def _pass_sql(sql, conn):
    return sql


class TestRootEndpoints:
    def test_root(self):
        r = client.get("/")
        assert r.status_code == 200
        assert "version" in r.json()

    def test_health(self):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "healthy"


class TestAuth:
    @patch("api.routes.auth.verify_user")
    @patch("api.routes.auth.create_access_token")
    def test_login_success(self, mock_token, mock_verify):
        mock_verify.return_value = {
            "id": 1,
            "username": "u",
            "role": "user",
            "user_type": "free",
            "remaining_calculations": 10,
        }
        mock_token.return_value = "tok123"
        r = client.post("/api/auth/login", json={"username": "u", "password": "p"})
        assert r.status_code == 200
        assert r.json()["access_token"] == "tok123"

    @patch("api.routes.auth.verify_user")
    def test_login_bad_credentials(self, mock_verify):
        mock_verify.return_value = None
        r = client.post("/api/auth/login", json={"username": "u", "password": "wrong"})
        assert r.status_code == 401

    def test_logout(self):
        r = client.post("/api/auth/logout")
        assert r.status_code == 200
        assert "message" in r.json()

    def test_me(self):
        r = client.get("/api/auth/me", headers={"Authorization": "Bearer faketoken"})
        assert r.status_code == 200
        data = r.json()
        assert data["id"] == 1
        assert data["username"] == "testuser"

    @patch("api.routes.auth.is_registration_open")
    def test_register_closed(self, mock_open):
        mock_open.return_value = False
        r = client.post(
            "/api/auth/register",
            json={
                "username": "newuser",
                "password": "StrongP@ssw0rd!",
                "security_question": "q",
                "security_answer": "a",
            },
        )
        assert r.status_code == 403

    @patch("api.routes.auth.is_registration_open")
    @patch("api.routes.auth.create_user")
    @patch("api.routes.auth.create_access_token")
    @patch("api.routes.auth.get_db_connection")
    @patch("api.routes.auth._safe_adapt_sql", side_effect=_pass_sql)
    def test_register_success(self, _sql, mock_db, mock_token, mock_create, mock_open):
        mock_open.return_value = True
        ctx, conn, cursor = _make_db_ctx(fetchone=None)
        mock_db.return_value = ctx
        mock_create.return_value = 42
        mock_token.return_value = "newtoken"
        r = client.post(
            "/api/auth/register",
            json={
                "username": "validuser",
                "password": "StrongP@ss123!",
                "security_question": "q",
                "security_answer": "a",
            },
        )
        assert r.status_code == 200
        assert r.json()["access_token"] == "newtoken"

    @patch("api.routes.auth.update_user_password")
    def test_change_password_success(self, mock_update):
        mock_update.return_value = True
        r = client.post(
            "/api/auth/change-password",
            json={
                "current_password": "OldP@ss123!x",
                "new_password": "NewStrongP@ss1!",
            },
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 200

    @patch("api.routes.auth.update_user_password")
    def test_change_password_wrong_current(self, mock_update):
        mock_update.return_value = False
        r = client.post(
            "/api/auth/change-password",
            json={
                "current_password": "WrongOld@1234",
                "new_password": "NewStrongP@ss1!",
            },
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 401


class TestProducts:
    @patch("api.routes.products.get_all_products_for_user")
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

    @patch("api.routes.products.get_product_by_id")
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

    @patch("api.routes.products.get_product_by_id")
    def test_get_product_not_found(self, mock_get):
        mock_get.return_value = None
        r = client.get(
            "/api/products/999", headers={"Authorization": "Bearer faketoken"}
        )
        assert r.status_code == 404

    @patch("api.routes.products.get_product_by_id")
    @patch("api.routes.products.add_product")
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

    @patch("api.routes.products.get_product_by_id")
    @patch("api.routes.products.update_product")
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

    @patch("api.routes.products.delete_product")
    def test_delete_product_success(self, mock_del):
        mock_del.return_value = True
        r = client.delete(
            "/api/products/1", headers={"Authorization": "Bearer faketoken"}
        )
        assert r.status_code == 200

    @patch("api.routes.products.delete_product")
    def test_delete_product_not_found(self, mock_del):
        mock_del.return_value = False
        r = client.delete(
            "/api/products/999", headers={"Authorization": "Bearer faketoken"}
        )
        assert r.status_code == 404


def _logistics_row():
    return {
        "id": 1,
        "user_id": 1,
        "name": "Test",
        "type": "land",
        "min_days": 1,
        "max_days": 10,
        "price_limit": 0,
        "price_limit_rub": 0,
        "price_min": 0,
        "price_min_rub": 0,
        "base_fee": 0,
        "min_weight": 0,
        "max_weight": 100000,
        "max_sum_of_sides": 0,
        "max_longest_side": 0,
        "max_second_side": 0,
        "min_second_side": 0,
        "min_length": 0,
        "max_cylinder_sum": 0,
        "min_cylinder_sum": 0,
        "max_cylinder_length": 0,
        "min_cylinder_length": 0,
        "volume_mode": "none",
        "longest_side_threshold": 0,
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
        "priority_group": 0,
        "price_limit_currency": "RUB",
        "price_min_currency": "RUB",
        "is_active": 1,
    }


def _logistics_columns():
    return [(k,) for k in _logistics_row().keys()]


class TestLogistics:
    @patch("api.routes.logistics.get_db_connection")
    @patch("api.routes.logistics._safe_adapt_sql", side_effect=_pass_sql)
    def test_get_logistics_list(self, _sql, mock_db):
        ctx, conn, cursor = _make_db_ctx(
            fetchall=[tuple(_logistics_row().values())],
            description=_logistics_columns(),
        )
        mock_db.return_value = ctx
        r = client.get("/api/logistics", headers={"Authorization": "Bearer faketoken"})
        assert r.status_code == 200

    @patch("api.routes.logistics.get_db_connection")
    @patch("api.routes.logistics._safe_adapt_sql", side_effect=_pass_sql)
    def test_get_logistics_by_id(self, _sql, mock_db):
        ctx, conn, cursor = _make_db_ctx(
            fetchone=tuple(_logistics_row().values()),
            description=_logistics_columns(),
        )
        mock_db.return_value = ctx
        r = client.get(
            "/api/logistics/1", headers={"Authorization": "Bearer faketoken"}
        )
        assert r.status_code == 200

    @patch("api.routes.logistics.get_db_connection")
    @patch("api.routes.logistics._safe_adapt_sql", side_effect=_pass_sql)
    def test_get_logistics_by_id_not_found(self, _sql, mock_db):
        ctx, conn, cursor = _make_db_ctx(
            fetchone=None,
            description=_logistics_columns(),
        )
        mock_db.return_value = ctx
        r = client.get(
            "/api/logistics/999", headers={"Authorization": "Bearer faketoken"}
        )
        assert r.status_code == 404

    @patch("api.routes.logistics.get_db_connection")
    @patch("api.routes.logistics._safe_adapt_sql", side_effect=_pass_sql)
    def test_delete_logistics_success(self, _sql, mock_db):
        ctx, conn, cursor = _make_db_ctx(rowcount=1)
        mock_db.return_value = ctx
        r = client.delete(
            "/api/logistics/1", headers={"Authorization": "Bearer faketoken"}
        )
        assert r.status_code == 200

    @patch("api.routes.logistics.get_db_connection")
    @patch("api.routes.logistics._safe_adapt_sql", side_effect=_pass_sql)
    def test_delete_logistics_not_found(self, _sql, mock_db):
        ctx, conn, cursor = _make_db_ctx(rowcount=0)
        mock_db.return_value = ctx
        r = client.delete(
            "/api/logistics/999", headers={"Authorization": "Bearer faketoken"}
        )
        assert r.status_code == 404

    @patch("api.routes.logistics.get_db_connection")
    @patch("api.routes.logistics._safe_adapt_sql", side_effect=_pass_sql)
    def test_batch_delete_logistics(self, _sql, mock_db):
        ctx, conn, cursor = _make_db_ctx(rowcount=2)
        mock_db.return_value = ctx
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
    @patch("api.routes.admin.get_db_connection")
    @patch("api.routes.admin._safe_adapt_sql", side_effect=_pass_sql)
    def test_get_users(self, _sql, mock_db):
        cols = [
            ("id",),
            ("username",),
            ("role",),
            ("user_type",),
            ("subscription_expires",),
            ("status",),
        ]
        rows = [(1, "admin", "admin", "enterprise", None, "正常")]
        cursor = MagicMock()
        cursor.fetchone.return_value = (1,)
        cursor.fetchall.return_value = rows
        cursor.description = cols
        cursor.rowcount = 1
        conn = MagicMock()
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=(conn, cursor))
        ctx.__exit__ = MagicMock(return_value=False)
        mock_db.return_value = ctx
        r = client.get(
            "/api/admin/users", headers={"Authorization": "Bearer faketoken"}
        )
        assert r.status_code == 200
        body = r.json()
        assert "users" in body and "total" in body

    @patch("api.routes.admin.get_db_connection")
    @patch("api.routes.admin._safe_adapt_sql", side_effect=_pass_sql)
    def test_create_admin_user(self, _sql, mock_db):
        ctx, conn, cursor = _make_db_ctx(fetchone=(99,))
        mock_db.return_value = ctx
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

    @patch("api.routes.admin.get_db_connection")
    @patch("api.routes.admin._safe_adapt_sql", side_effect=_pass_sql)
    def test_update_admin_user(self, _sql, mock_db):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [
            (2,),
            (2, "u2", "user", "free", None, "正常"),
        ]
        cursor.description = [
            ("id",),
            ("username",),
            ("role",),
            ("user_type",),
            ("subscription_expires",),
            ("status",),
        ]
        cursor.rowcount = 1
        conn = MagicMock()
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=(conn, cursor))
        ctx.__exit__ = MagicMock(return_value=False)
        mock_db.return_value = ctx
        r = client.put(
            "/api/admin/users/2",
            json={"role": "user"},
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 200

    @patch("api.routes.admin.get_db_connection")
    @patch("api.routes.admin._safe_adapt_sql", side_effect=_pass_sql)
    def test_reset_password(self, _sql, mock_db):
        ctx, conn, cursor = _make_db_ctx(rowcount=1)
        mock_db.return_value = ctx
        r = client.post(
            "/api/admin/users/2/reset-password",
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 200

    @patch("api.routes.admin.get_db_connection")
    @patch("api.routes.admin._safe_adapt_sql", side_effect=_pass_sql)
    def test_delete_admin_user(self, _sql, mock_db):
        ctx, conn, cursor = _make_db_ctx(rowcount=1)
        mock_db.return_value = ctx
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
    @patch("api.routes.orders.get_db_connection")
    @patch("api.routes.orders._safe_adapt_sql", side_effect=_pass_sql)
    def test_get_orders_empty(self, _sql, mock_db):
        ctx, conn, cursor = _make_db_ctx(fetchall=[])
        mock_db.return_value = ctx
        r = client.get("/api/orders", headers={"Authorization": "Bearer faketoken"})
        assert r.status_code == 200
        assert r.json() == []

    @patch("api.routes.orders.get_db_connection")
    @patch("api.routes.orders._safe_adapt_sql", side_effect=_pass_sql)
    def test_get_orders_with_data(self, _sql, mock_db):
        import datetime as dt

        rows = [
            (1, "ORD001", "efficiency", 99.0, "paid", dt.datetime(2024, 1, 1), None)
        ]
        ctx, conn, cursor = _make_db_ctx(fetchall=rows)
        mock_db.return_value = ctx
        r = client.get("/api/orders", headers={"Authorization": "Bearer faketoken"})
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["order_id"] == "ORD001"
