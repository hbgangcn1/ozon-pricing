"""Coverage tests for statistics and admin error paths."""
import os
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from api.main import app
from security.tokens import create_access_token


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def admin_token(test_admin):
    return create_access_token(
        user_id=test_admin["id"],
        username=test_admin["username"],
        role="admin",
    )


class TestStatisticsErrorPaths:
    @pytest.fixture(autouse=True)
    def _bypass_csrf(self, test_admin):
        from api.main import app
        from api.dependencies import require_admin, get_current_user_id
        app.dependency_overrides[require_admin] = lambda: test_admin["id"]
        app.dependency_overrides[get_current_user_id] = lambda: test_admin["id"]
        yield
        app.dependency_overrides.pop(require_admin, None)
        app.dependency_overrides.pop(get_current_user_id, None)

    @pytest.mark.asyncio
    async def test_parse_date_filter_invalid_format(self, client, admin_token):
        client.cookies.set("access_token", admin_token)
        response = await client.get(
            "/api/statistics/login-logs?date_from=invalid",
        )
        assert response.status_code == 400
        assert "日期格式" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_overview_new_users_exception_fallback(self, client, admin_token):
        from api.routes import statistics as stats_mod

        client.cookies.set("access_token", admin_token)
        with patch.object(stats_mod, "count_new_users_today", new=AsyncMock(side_effect=RuntimeError("db down"))):
            response = await client.get(
                "/api/statistics/overview",
            )

        assert response.status_code == 200
        data = response.json()
        assert data["new_users_today"] == 0


class TestAdminErrorPaths:
    @pytest.fixture(autouse=True)
    def _bypass_csrf(self, test_admin):
        from api.main import app
        from api.dependencies import require_admin, get_current_user_id
        app.dependency_overrides[require_admin] = lambda: test_admin["id"]
        app.dependency_overrides[get_current_user_id] = lambda: test_admin["id"]
        yield
        app.dependency_overrides.pop(require_admin, None)
        app.dependency_overrides.pop(get_current_user_id, None)

    @pytest.mark.asyncio
    async def test_get_user_detail_not_found(self, client, admin_token):
        client.cookies.set("access_token", admin_token)
        response = await client.get(
            "/api/admin/users/999999",
        )
        assert response.status_code == 404
        assert "用户不存在" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_delete_super_admin_blocked(self, client, admin_token):
        client.cookies.set("access_token", admin_token)
        response = await client.delete(
            "/api/admin/users/1",
        )
        assert response.status_code == 400
        assert "超级管理员" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_delete_user_not_found(self, client, admin_token):
        client.cookies.set("access_token", admin_token)
        response = await client.delete(
            "/api/admin/users/999999",
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_reset_password_user_not_found(self, client, admin_token):
        client.cookies.set("access_token", admin_token)
        response = await client.post(
            "/api/admin/users/999999/reset-password",
        )
        assert response.status_code == 404
        assert "用户不存在" in response.json()["detail"]
