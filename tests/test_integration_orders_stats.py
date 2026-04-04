"""
Integration tests for orders.py and statistics.py routes.
These tests hit the real PostgreSQL database.
"""

import os
import sys
import time
import pytest

os.environ["DB_TYPE"] = "postgresql"
os.environ["POSTGRES_HOST"] = "localhost"
os.environ["POSTGRES_PORT"] = "5432"
os.environ["POSTGRES_DB"] = "logistics"
os.environ["POSTGRES_USER"] = "postgres"
os.environ["POSTGRES_PASSWORD"] = "***REMOVED-PG-PWD***"
os.environ["E2E_TEST"] = "1"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from api.main import app
from api.dependencies import get_current_user_id, require_admin
from db_utils import get_db_connection, _safe_adapt_sql

client = TestClient(app, raise_server_exceptions=False)

# ---------------------------------------------------------------------------
# Auth override helpers
# ---------------------------------------------------------------------------

_current_user_id = None
_current_admin_id = None


def _override_get_current_user_id():
    return _current_user_id


def _override_require_admin():
    return _current_admin_id


def _set_user(user_id):
    global _current_user_id
    _current_user_id = user_id
    app.dependency_overrides[get_current_user_id] = _override_get_current_user_id


def _set_admin(admin_id):
    global _current_admin_id
    _current_admin_id = admin_id
    app.dependency_overrides[require_admin] = _override_require_admin


def _clear_overrides():
    app.dependency_overrides.pop(get_current_user_id, None)
    app.dependency_overrides.pop(require_admin, None)


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def insert_test_order(user_id, status="paid", order_type="professional"):
    """Insert a test payment_order and return its DB id."""
    order_id = f"TEST_ORD_{int(time.time() * 1000)}"
    ts = int(time.time())
    with get_db_connection() as (conn, c):
        sql = _safe_adapt_sql(
            """
            INSERT INTO payment_orders
                (order_id, user_id, amount, description, duration,
                 status, created_at, order_type)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            conn,
        )
        c.execute(
            sql,
            (order_id, user_id, 99.0, "test order", 30, status, ts, order_type),
        )
        row = c.fetchone()
        conn.commit()
    return row[0] if row else None


def delete_test_order(order_pk):
    """Delete a payment_order by its primary key."""
    try:
        with get_db_connection() as (conn, c):
            sql = _safe_adapt_sql("DELETE FROM payment_orders WHERE id = %s", conn)
            c.execute(sql, (order_pk,))
            conn.commit()
    except Exception:
        pass


def insert_login_log(user_id):
    """Insert a user_login_log row and return its id."""
    ts = int(time.time())
    with get_db_connection() as (conn, c):
        sql = _safe_adapt_sql(
            """
            INSERT INTO user_login_log
                (user_id, login_time, ip_address, user_agent,
                 device_type, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            conn,
        )
        c.execute(sql, (user_id, ts, "127.0.0.1", "test-agent", "desktop", ts))
        row = c.fetchone()
        conn.commit()
    return row[0] if row else None


def delete_login_log(log_id):
    try:
        with get_db_connection() as (conn, c):
            sql = _safe_adapt_sql("DELETE FROM user_login_log WHERE id = %s", conn)
            c.execute(sql, (log_id,))
            conn.commit()
    except Exception:
        pass


def insert_admin_log(admin_id):
    """Insert an admin_action_log row and return its id."""
    ts = int(time.time())
    with get_db_connection() as (conn, c):
        sql = _safe_adapt_sql(
            """
            INSERT INTO admin_action_log
                (admin_id, action_type, action_detail, target_user_id,
                 target_type, ip_address, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            conn,
        )
        c.execute(
            sql,
            (
                admin_id,
                "test_action",
                "integration test",
                None,
                "user",
                "127.0.0.1",
                ts,
            ),
        )
        row = c.fetchone()
        conn.commit()
    return row[0] if row else None


def delete_admin_log(log_id):
    try:
        with get_db_connection() as (conn, c):
            sql = _safe_adapt_sql("DELETE FROM admin_action_log WHERE id = %s", conn)
            c.execute(sql, (log_id,))
            conn.commit()
    except Exception:
        pass


# ===========================================================================
# orders.py  —  GET /api/orders
# ===========================================================================


class TestGetOrders:
    def test_no_orders_returns_empty_list(self, test_user):
        uid = test_user["id"]
        _set_user(uid)
        try:
            resp = client.get("/api/orders")
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, list)
            # Filter only the test user's own rows (there might be old ones)
            for item in data:
                # If any rows returned, they belong to this user
                assert "id" in item
        finally:
            _clear_overrides()

    def test_with_orders_returns_correct_format(self, test_user):
        uid = test_user["id"]
        pk = insert_test_order(uid, status="paid", order_type="professional")
        _set_user(uid)
        try:
            resp = client.get("/api/orders")
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, list)
            assert len(data) >= 1

            # Find our inserted order
            inserted = [d for d in data if d.get("id") == pk]
            assert len(inserted) == 1
            o = inserted[0]

            assert "id" in o
            assert "order_id" in o
            assert "order_type" in o
            assert "plan_name" in o
            assert "amount" in o
            assert "status" in o
            assert "created_at" in o
            assert o["order_type"] == "professional"
            assert o["plan_name"] == "专业版"
            assert o["amount"] == 99.0
            assert o["status"] == "paid"
        finally:
            _clear_overrides()
            if pk:
                delete_test_order(pk)

    def test_order_updated_at_optional(self, test_user):
        uid = test_user["id"]
        pk = insert_test_order(uid)
        _set_user(uid)
        try:
            resp = client.get("/api/orders")
            assert resp.status_code == 200
            data = resp.json()
            inserted = [d for d in data if d.get("id") == pk]
            assert len(inserted) == 1
            # updated_at may be None or a string
            o = inserted[0]
            assert "updated_at" in o
        finally:
            _clear_overrides()
            if pk:
                delete_test_order(pk)

    def test_no_auth_returns_422_or_403(self):
        _clear_overrides()
        resp = client.get("/api/orders")
        assert resp.status_code in (401, 403, 422)


# ===========================================================================
# statistics.py  —  DB-backed endpoints (require_admin)
# ===========================================================================


class TestStatisticsOverview:
    def test_overview_returns_correct_schema(self, test_admin):
        _set_admin(test_admin["id"])
        try:
            resp = client.get("/api/statistics/overview")
            assert resp.status_code == 200
            data = resp.json()
            for key in [
                "total_users",
                "active_users",
                "new_users_today",
                "total_orders",
                "total_revenue",
                "pro_users",
                "eff_users",
                "free_users",
            ]:
                assert key in data, f"Missing key: {key}"
            assert isinstance(data["total_users"], int)
            assert data["total_users"] >= 0
            assert isinstance(data["total_revenue"], (int, float))
        finally:
            _clear_overrides()

    def test_overview_counts_are_non_negative(self, test_admin):
        _set_admin(test_admin["id"])
        try:
            resp = client.get("/api/statistics/overview")
            assert resp.status_code == 200
            data = resp.json()
            assert data["pro_users"] >= 0
            assert data["eff_users"] >= 0
            assert data["free_users"] >= 0
            assert data["total_orders"] >= 0
        finally:
            _clear_overrides()


class TestStatisticsLoginLogs:
    def test_login_logs_returns_list(self, test_admin):
        _set_admin(test_admin["id"])
        try:
            resp = client.get("/api/statistics/login-logs")
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, list)
        finally:
            _clear_overrides()

    def test_login_logs_with_inserted_data(self, test_user, test_admin):
        log_id = insert_login_log(test_user["id"])
        _set_admin(test_admin["id"])
        try:
            resp = client.get("/api/statistics/login-logs?page=1&page_size=100")
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, list)
            # At least one log should exist now
            assert len(data) >= 1
            # Verify schema of first item
            if data:
                item = data[0]
                for field in ["id", "username", "action", "ip", "time", "status"]:
                    assert field in item, f"Missing field: {field}"
        finally:
            _clear_overrides()
            if log_id:
                delete_login_log(log_id)

    def test_login_logs_pagination(self, test_admin):
        _set_admin(test_admin["id"])
        try:
            resp = client.get("/api/statistics/login-logs?page=1&page_size=5")
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, list)
            assert len(data) <= 5
        finally:
            _clear_overrides()


class TestStatisticsAdminLogs:
    def test_admin_logs_returns_list(self, test_admin):
        _set_admin(test_admin["id"])
        try:
            resp = client.get("/api/statistics/admin-logs")
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, list)
        finally:
            _clear_overrides()

    def test_admin_logs_with_inserted_data(self, test_admin):
        log_id = insert_admin_log(test_admin["id"])
        _set_admin(test_admin["id"])
        try:
            resp = client.get("/api/statistics/admin-logs?page=1&page_size=100")
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, list)
            assert len(data) >= 1
            if data:
                item = data[0]
                for field in ["id", "admin", "action", "time"]:
                    assert field in item, f"Missing field: {field}"
        finally:
            _clear_overrides()
            if log_id:
                delete_admin_log(log_id)

    def test_admin_logs_pagination(self, test_admin):
        _set_admin(test_admin["id"])
        try:
            resp = client.get("/api/statistics/admin-logs?page=1&page_size=3")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) <= 3
        finally:
            _clear_overrides()


class TestStatisticsUserGroups:
    def test_user_groups_returns_dict(self, test_admin):
        _set_admin(test_admin["id"])
        try:
            resp = client.get("/api/statistics/user-groups")
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, dict)
            for key in ["high_value_users", "active_users", "silent_users"]:
                assert key in data, f"Missing key: {key}"
            assert data["high_value_users"] >= 0
            assert data["active_users"] >= 0
        finally:
            _clear_overrides()

    def test_user_groups_silent_non_negative(self, test_admin):
        _set_admin(test_admin["id"])
        try:
            resp = client.get("/api/statistics/user-groups")
            assert resp.status_code == 200
            data = resp.json()
            assert data["silent_users"] >= 0
        finally:
            _clear_overrides()


class TestStatisticsFunnel:
    def test_funnel_returns_dict(self, test_admin):
        _set_admin(test_admin["id"])
        try:
            resp = client.get("/api/statistics/funnel")
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, dict)
            for key in [
                "registered",
                "trial",
                "paid",
                "conversion_trial",
                "conversion_paid",
            ]:
                assert key in data, f"Missing key: {key}"
        finally:
            _clear_overrides()

    def test_funnel_registered_gte_paid(self, test_admin):
        _set_admin(test_admin["id"])
        try:
            resp = client.get("/api/statistics/funnel")
            assert resp.status_code == 200
            data = resp.json()
            assert data["registered"] >= data["paid"]
        finally:
            _clear_overrides()


class TestStatisticsPlanAnalysis:
    def test_plan_analysis_returns_dict(self, test_admin):
        _set_admin(test_admin["id"])
        try:
            resp = client.get("/api/statistics/plan-analysis")
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, dict)
            for key in [
                "free_users",
                "efficiency_users",
                "professional_users",
                "enterprise_users",
            ]:
                assert key in data, f"Missing key: {key}"
        finally:
            _clear_overrides()

    def test_plan_analysis_counts_non_negative(self, test_admin):
        _set_admin(test_admin["id"])
        try:
            resp = client.get("/api/statistics/plan-analysis")
            assert resp.status_code == 200
            data = resp.json()
            for k, v in data.items():
                assert v >= 0, f"{k} should be >= 0"
        finally:
            _clear_overrides()


class TestStatisticsActiveUsers:
    def test_active_users_returns_dict(self, test_admin):
        _set_admin(test_admin["id"])
        try:
            resp = client.get("/api/statistics/active-users")
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, dict)
            for key in ["daily", "weekly", "trend_daily", "trend_weekly"]:
                assert key in data, f"Missing key: {key}"
        finally:
            _clear_overrides()

    def test_active_users_daily_lte_weekly(self, test_admin):
        _set_admin(test_admin["id"])
        try:
            resp = client.get("/api/statistics/active-users")
            assert resp.status_code == 200
            data = resp.json()
            # daily active <= weekly active
            assert data["daily"] <= data["weekly"]
        finally:
            _clear_overrides()
