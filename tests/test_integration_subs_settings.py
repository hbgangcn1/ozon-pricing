"""
Integration tests for subscriptions.py and settings.py routes.
These tests hit the real PostgreSQL database.
"""

import pytest
from unittest.mock import patch

from api.main import app
from api.dependencies import get_current_user_id, require_admin
from database import AsyncSessionLocal
from sqlalchemy import select
from models.config import SystemConfig

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


async def _get_system_config(key):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(SystemConfig.config_value).where(SystemConfig.config_key == key)
        )
        return result.scalar_one_or_none()


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
    async def test_plans_returns_list(self, client):
        resp = await client.get("/api/subscriptions/plans")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    async def test_plans_schema_when_data_present(self, client):
        resp = await client.get("/api/subscriptions/plans")
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

    async def test_plans_features_is_list(self, client):
        resp = await client.get("/api/subscriptions/plans")
        assert resp.status_code == 200
        data = resp.json()
        for plan in data:
            assert isinstance(plan["features"], list)

    async def test_plans_status_true_only(self, client):
        resp = await client.get("/api/subscriptions/plans")
        assert resp.status_code == 200
        data = resp.json()
        for plan in data:
            assert plan["status"] is True


class TestSubscriptionsCurrent:
    async def test_current_returns_subscription_schema(self, client, test_user):
        _set_user(test_user["id"])
        try:
            resp = await client.get("/api/subscriptions/current")
            assert resp.status_code == 200
            data = resp.json()
            assert "plan_code" in data
            assert "calc_limit" in data
            assert "logistics_limit" in data
            assert "expired_at" in data
        finally:
            _clear_overrides()

    async def test_current_plan_code_matches_user_type(self, client, test_user):
        _set_user(test_user["id"])
        try:
            resp = await client.get("/api/subscriptions/current")
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

    async def test_current_user_type_free(self, client, test_user):
        _set_user(test_user["id"])
        try:
            resp = await client.get("/api/subscriptions/current")
            assert resp.status_code == 200
            data = resp.json()
            assert data["plan_code"] == "free"
        finally:
            _clear_overrides()

    async def test_current_no_auth_returns_error(self, client):
        _clear_overrides()
        resp = await client.get("/api/subscriptions/current")
        assert resp.status_code in (401, 403, 422)


class TestSettingsGetSettings:
    async def test_get_settings_returns_schema(self, client, test_admin):
        _set_admin(test_admin["id"])
        with patch(
            "api.routes.settings._load_backup_service",
            return_value=_MOCK_BACKUP_RETURN,
        ):
            try:
                resp = await client.get("/api/settings")
                assert resp.status_code == 200
                data = resp.json()
                assert "open_registration" in data
                assert "backup_interval" in data
                assert isinstance(data["open_registration"], bool)
                assert isinstance(data["backup_interval"], int)
            finally:
                _clear_overrides()

    async def test_get_settings_backup_interval_from_mock(self, client, test_admin):
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
                resp = await client.get("/api/settings")
                assert resp.status_code == 200
                data = resp.json()
                assert data["backup_interval"] == 12
            finally:
                _clear_overrides()

    async def test_get_settings_no_admin_returns_error(self, client):
        _clear_overrides()
        with patch(
            "api.routes.settings._load_backup_service",
            return_value=_MOCK_BACKUP_RETURN,
        ):
            resp = await client.get("/api/settings")
            assert resp.status_code in (401, 403, 422)


class TestSettingsOpenRegistration:
    async def test_enable_registration(self, client, test_admin):
        _set_admin(test_admin["id"])
        try:
            resp = await client.put("/api/settings/open-registration?enabled=true")
            assert resp.status_code == 200
            data = resp.json()
            assert "message" in data

            val = await _get_system_config("open_registration")
            assert val == "true"
        finally:
            _clear_overrides()

    async def test_disable_registration(self, client, test_admin):
        _set_admin(test_admin["id"])
        try:
            resp = await client.put("/api/settings/open-registration?enabled=false")
            assert resp.status_code == 200
            data = resp.json()
            assert "message" in data

            val = await _get_system_config("open_registration")
            assert val == "false"
        finally:
            _clear_overrides()

    async def test_toggle_registration_twice(self, client, test_admin):
        _set_admin(test_admin["id"])
        try:
            await client.put("/api/settings/open-registration?enabled=true")
            val1 = await _get_system_config("open_registration")
            assert val1 == "true"

            await client.put("/api/settings/open-registration?enabled=false")
            val2 = await _get_system_config("open_registration")
            assert val2 == "false"
        finally:
            _clear_overrides()

    async def test_open_registration_response_message(self, client, test_admin):
        _set_admin(test_admin["id"])
        try:
            resp = await client.put("/api/settings/open-registration?enabled=true")
            assert resp.status_code == 200
            data = resp.json()
            assert data.get("message") == "设置已更新"
        finally:
            _clear_overrides()

    async def test_no_admin_returns_error(self, client):
        _clear_overrides()
        resp = await client.put("/api/settings/open-registration?enabled=true")
        assert resp.status_code in (401, 403, 422)
