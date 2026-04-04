"""
Integration tests for subscriptions.py and settings.py routes.
These tests hit the real PostgreSQL database.
"""

import os
import sys
import time
import pytest
from unittest.mock import patch

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


def _get_system_config(key):
    """Read a system_config value from DB."""
    with get_db_connection() as (conn, c):
        sql = _safe_adapt_sql(
            "SELECT config_value FROM system_config WHERE config_key = %s",
            conn,
        )
        c.execute(sql, (key,))
        row = c.fetchone()
    return row[0] if row else None


def _cleanup_system_config(key):
    """Remove a system_config key inserted during tests."""
    try:
        with get_db_connection() as (conn, c):
            sql = _safe_adapt_sql(
                "DELETE FROM system_config WHERE config_key = %s", conn
            )
            c.execute(sql, (key,))
            conn.commit()
    except Exception:
        pass


_MOCK_BACKUP_RETURN = (
    None,
    None,
    None,
    None,
    lambda: {"interval_hours": 6, "enabled": True, "max_backups": 28},
    None,
    None,
    None,
    None,
    None,
    None,
)


class TestSubscriptionsPlans:
    def test_plans_returns_list(self):
        resp = client.get("/api/subscriptions/plans")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_plans_schema_when_data_present(self):
        resp = client.get("/api/subscriptions/plans")
        assert resp.status_code == 200
        data = resp.json()
        if not data:
            pytest.skip("No active plans in test DB")
        plan = data[0]
        required = [
            "id",
            "code",
            "name",
            "display_price_month",
            "display_price_year",
            "actual_price_month",
            "actual_price_year",
            "test_price_month",
            "test_price_year",
            "calc_limit",
            "logistics_limit",
            "sort",
            "status",
            "description",
            "features",
        ]
        for field in required:
            assert field in plan, f"Missing field: {field}"

    def test_plans_features_is_list(self):
        resp = client.get("/api/subscriptions/plans")
        assert resp.status_code == 200
        data = resp.json()
        for plan in data:
            assert isinstance(plan["features"], list)

    def test_plans_status_true_only(self):
        resp = client.get("/api/subscriptions/plans")
        assert resp.status_code == 200
        data = resp.json()
        for plan in data:
            assert plan["status"] is True


class TestSubscriptionsCurrent:
    def test_current_returns_subscription_schema(self, test_user):
        _set_user(test_user["id"])
        try:
            resp = client.get("/api/subscriptions/current")
            assert resp.status_code == 200
            data = resp.json()
            assert "plan_code" in data
            assert "calc_limit" in data
            assert "logistics_limit" in data
            assert "expired_at" in data
        finally:
            _clear_overrides()

    def test_current_plan_code_matches_user_type(self, test_user):
        _set_user(test_user["id"])
        try:
            resp = client.get("/api/subscriptions/current")
            assert resp.status_code == 200
            data = resp.json()
            assert data["plan_code"] in [
                "free",
                "efficiency",
                "professional",
                "enterprise",
                "permanent",
            ]
        finally:
            _clear_overrides()

    def test_current_user_type_free(self, test_user):
        _set_user(test_user["id"])
        try:
            resp = client.get("/api/subscriptions/current")
            assert resp.status_code == 200
            data = resp.json()
            assert data["plan_code"] == "free"
        finally:
            _clear_overrides()

    def test_current_no_auth_returns_error(self):
        _clear_overrides()
        resp = client.get("/api/subscriptions/current")
        assert resp.status_code in (401, 403, 422)


class TestSettingsGetSettings:
    def test_get_settings_returns_schema(self, test_admin):
        _set_admin(test_admin["id"])
        with patch(
            "api.routes.settings._load_backup_service",
            return_value=_MOCK_BACKUP_RETURN,
        ):
            try:
                resp = client.get("/api/settings")
                assert resp.status_code == 200
                data = resp.json()
                assert "open_registration" in data
                assert "backup_interval" in data
                assert isinstance(data["open_registration"], bool)
                assert isinstance(data["backup_interval"], int)
            finally:
                _clear_overrides()

    def test_get_settings_backup_interval_from_mock(self, test_admin):
        _set_admin(test_admin["id"])
        mock_return = list(_MOCK_BACKUP_RETURN)
        mock_return[4] = lambda: {
            "interval_hours": 12,
            "enabled": True,
            "max_backups": 10,
        }
        with patch(
            "api.routes.settings._load_backup_service",
            return_value=tuple(mock_return),
        ):
            try:
                resp = client.get("/api/settings")
                assert resp.status_code == 200
                data = resp.json()
                assert data["backup_interval"] == 12
            finally:
                _clear_overrides()

    def test_get_settings_no_admin_returns_error(self):
        _clear_overrides()
        with patch(
            "api.routes.settings._load_backup_service",
            return_value=_MOCK_BACKUP_RETURN,
        ):
            resp = client.get("/api/settings")
            assert resp.status_code in (401, 403, 422)


class TestSettingsOpenRegistration:
    def test_enable_registration(self, test_admin):
        _set_admin(test_admin["id"])
        try:
            resp = client.put("/api/settings/open-registration?enabled=true")
            assert resp.status_code == 200
            data = resp.json()
            assert "message" in data

            val = _get_system_config("open_registration")
            assert val == "true"
        finally:
            _clear_overrides()

    def test_disable_registration(self, test_admin):
        _set_admin(test_admin["id"])
        try:
            resp = client.put("/api/settings/open-registration?enabled=false")
            assert resp.status_code == 200
            data = resp.json()
            assert "message" in data

            val = _get_system_config("open_registration")
            assert val == "false"
        finally:
            _clear_overrides()

    def test_toggle_registration_twice(self, test_admin):
        _set_admin(test_admin["id"])
        try:
            client.put("/api/settings/open-registration?enabled=true")
            val1 = _get_system_config("open_registration")
            assert val1 == "true"

            client.put("/api/settings/open-registration?enabled=false")
            val2 = _get_system_config("open_registration")
            assert val2 == "false"
        finally:
            _clear_overrides()

    def test_open_registration_response_message(self, test_admin):
        _set_admin(test_admin["id"])
        try:
            resp = client.put("/api/settings/open-registration?enabled=true")
            assert resp.status_code == 200
            data = resp.json()
            assert data.get("message") == "设置已更新"
        finally:
            _clear_overrides()

    def test_no_admin_returns_error(self):
        _clear_overrides()
        resp = client.put("/api/settings/open-registration?enabled=true")
        assert resp.status_code in (401, 403, 422)
