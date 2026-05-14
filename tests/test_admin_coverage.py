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


class TestAdminGetUserDetail:
    @pytest.fixture(autouse=True)
    def _bypass(self, test_admin):
        from api.main import app
        from api.dependencies import require_admin
        app.dependency_overrides[require_admin] = lambda: test_admin["id"]
        yield
        app.dependency_overrides.pop(require_admin, None)

    @pytest.mark.asyncio
    async def test_get_user_not_found(self, client):
        response = await client.get("/api/admin/users/999999")
        assert response.status_code == 404
        assert "不存在" in response.json()["detail"]


class TestAdminResetPassword:
    @pytest.fixture(autouse=True)
    def _bypass(self, test_admin):
        from api.main import app
        from api.dependencies import require_admin
        app.dependency_overrides[require_admin] = lambda: test_admin["id"]
        yield
        app.dependency_overrides.pop(require_admin, None)

    @pytest.mark.asyncio
    async def test_reset_user_not_found(self, client):
        response = await client.post("/api/admin/users/999999/reset-password")
        assert response.status_code == 404
        assert "不存在" in response.json()["detail"]


class TestAdminDeleteUser:
    @pytest.fixture(autouse=True)
    def _bypass(self, test_admin):
        from api.main import app
        from api.dependencies import require_admin
        app.dependency_overrides[require_admin] = lambda: test_admin["id"]
        yield
        app.dependency_overrides.pop(require_admin, None)

    @pytest.mark.asyncio
    async def test_delete_super_admin_blocked(self, client):
        response = await client.delete("/api/admin/users/1")
        assert response.status_code == 400
        assert "超级管理员" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_delete_not_found(self, client):
        from api.routes import admin as admin_mod

        with patch.object(admin_mod, "db_admin") as mock_db:
            mock_db.delete_user_admin = AsyncMock(return_value=False)
            response = await client.delete("/api/admin/users/999999")

        assert response.status_code == 404
        assert "不存在" in response.json()["detail"]
