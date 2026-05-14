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


class TestAuthRefreshSuccessPaths:
    @pytest.fixture(autouse=True)
    def _bypass_csrf(self, test_user):
        with patch("api.routes.auth.refresh.validate_cookie_csrf"):
            yield

    @pytest.mark.asyncio
    async def test_refresh_token_expired_returns_401(self, client, test_user):
        from datetime import timedelta
        from security.tokens import create_refresh_token

        expired = create_refresh_token(
            user_id=test_user["id"], sid="sid-exp", expires_delta=timedelta(seconds=-1)
        )
        client.cookies.set("refresh_token", expired, path="/")
        response = await client.post("/api/auth/refresh")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_access_expired_returns_401(self, client, test_user):
        from datetime import timedelta
        from security.tokens import create_refresh_token

        expired = create_refresh_token(
            user_id=test_user["id"], sid="sid-exp2", expires_delta=timedelta(seconds=-1)
        )
        client.cookies.set("refresh_token", expired, path="/")
        response = await client.post("/api/auth/refresh-access")
        assert response.status_code == 401


class TestLogisticsPoolImport:
    @pytest.fixture(autouse=True)
    def _bypass(self, test_admin):
        from api.main import app
        from api.dependencies import require_admin
        app.dependency_overrides[require_admin] = lambda: test_admin["id"]
        yield
        app.dependency_overrides.pop(require_admin, None)

    @pytest.mark.asyncio
    async def test_import_non_xlsx_rejected(self, client):
        from io import BytesIO

        response = await client.post(
            "/api/logistics-pool/import",
            files={"file": ("data.txt", BytesIO(b"text"), "text/plain")},
        )
        assert response.status_code == 400
        assert "xlsx" in response.json()["detail"]


class TestLogisticsDelete:
    @pytest.fixture(autouse=True)
    def _bypass(self, test_user):
        from api.main import app
        from api.dependencies import get_current_user_id
        app.dependency_overrides[get_current_user_id] = lambda: test_user["id"]
        yield
        app.dependency_overrides.pop(get_current_user_id, None)

    @pytest.mark.asyncio
    async def test_delete_not_found(self, client):
        response = await client.delete("/api/logistics/999999")
        assert response.status_code == 404
        assert "不存在" in response.json()["detail"]


class TestProductsDelete:
    @pytest.fixture(autouse=True)
    def _bypass(self, test_user):
        from api.main import app
        from api.dependencies import get_current_user_id
        app.dependency_overrides[get_current_user_id] = lambda: test_user["id"]
        yield
        app.dependency_overrides.pop(get_current_user_id, None)

    @pytest.mark.asyncio
    async def test_delete_not_found(self, client):
        response = await client.delete("/api/products/999999")
        assert response.status_code == 404
        assert "不存在" in response.json()["detail"]


class TestAdminExtendSubscription:
    @pytest.fixture(autouse=True)
    def _bypass(self, test_admin):
        from api.main import app
        from api.dependencies import require_admin
        app.dependency_overrides[require_admin] = lambda: test_admin["id"]
        yield
        app.dependency_overrides.pop(require_admin, None)

    @pytest.mark.asyncio
    async def test_extend_user_not_found(self, client):
        response = await client.post(
            "/api/admin/users/999999/subscription/extend",
            json={"days": 30},
        )
        assert response.status_code == 404


class TestPricingRoutes:
    @pytest.fixture(autouse=True)
    def _bypass(self, test_user):
        from api.main import app
        from api.dependencies import get_current_user_id
        app.dependency_overrides[get_current_user_id] = lambda: test_user["id"]
        yield
        app.dependency_overrides.pop(get_current_user_id, None)

    @pytest.mark.asyncio
    async def test_calculate_grouped_missing_product_data(self, client):
        from api.routes import pricing as pricing_mod

        with patch.object(pricing_mod, "decrement_user_calculations", new=AsyncMock(return_value=True)):
            with patch.object(pricing_mod, "get_effective_plan", return_value="professional"):
                response = await client.post(
                    "/api/pricing/calculate-grouped",
                    json={"mode": "precise"},
                )
        assert response.status_code == 400
        assert "请提供产品数据" in response.json()["detail"]
