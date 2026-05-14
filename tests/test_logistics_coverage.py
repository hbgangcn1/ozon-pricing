"""Coverage tests for logistics, logistics_pool and rate_limit edge paths."""
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import DBAPIError, OperationalError, StatementError

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


class TestLogisticsToggleTransport:
    @pytest.fixture(autouse=True)
    def _bypass(self, test_user):
        from api.main import app
        from api.dependencies import get_current_user_id
        app.dependency_overrides[get_current_user_id] = lambda: test_user["id"]
        yield
        app.dependency_overrides.pop(get_current_user_id, None)

    @pytest.mark.asyncio
    async def test_toggle_not_found(self, client):
        response = await client.patch("/api/logistics/999999/toggle-transport")
        assert response.status_code == 404
        assert "不存在" in response.json()["detail"]


class TestLogisticsBatchDelete:
    @pytest.fixture(autouse=True)
    def _bypass(self, test_user):
        from api.main import app
        from api.dependencies import get_current_user_id
        app.dependency_overrides[get_current_user_id] = lambda: test_user["id"]
        yield
        app.dependency_overrides.pop(get_current_user_id, None)

    @pytest.mark.asyncio
    async def test_batch_delete_empty(self, client):
        response = await client.post("/api/logistics/batch-delete", json=[])
        assert response.status_code == 400
        assert "ID列表" in response.json()["detail"]


class TestLogisticsFbpRussiaRestriction:
    @pytest.fixture(autouse=True)
    def _bypass(self, test_user):
        from api.main import app
        from api.dependencies import get_current_user_id
        app.dependency_overrides[get_current_user_id] = lambda: test_user["id"]
        yield
        app.dependency_overrides.pop(get_current_user_id, None)

    @pytest.mark.asyncio
    async def test_create_fbp_express_non_ru(self, client, test_user):
        payload = {
            "name": "fbp-test",
            "type": "land",
            "min_days": 1,
            "max_days": 10,
            "price_limit_cny": "100.00",
            "price_min_cny": "10.00",
            "base_fee": "5.00",
            "min_weight": 100,
            "max_weight": 1000,
            "fee_mode": "per_kg",
            "first_fee": "10.00",
            "first_weight_g": 100,
            "continue_fee": "2.00",
            "continue_unit": "100",
            "fulfillment_type": "fbp",
            "fbp_service_level": "express",
            "destination": "CN",
        }
        response = await client.post("/api/logistics", json=payload)
        assert response.status_code == 422
        assert "RU" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_update_fbp_super_express_non_ru(self, client, test_user):
        from api.routes import logistics as log_mod

        fake_existing = {
            "id": 1,
            "user_id": test_user["id"],
            "fulfillment_type": "fbp",
            "fbp_service_level": "super_express",
            "destination": "RU",
        }
        with patch.object(log_mod, "get_logistics_by_id", new=AsyncMock(return_value=fake_existing)):
            with patch.object(log_mod, "update_logistics", new=AsyncMock(return_value=True)):
                response = await client.put("/api/logistics/1", json={"destination": "CN"})

        assert response.status_code == 422
        assert "RU" in response.json()["detail"]


class TestLogisticsPoolSetActive:
    @pytest.fixture(autouse=True)
    def _bypass(self, test_admin):
        from api.main import app
        from api.dependencies import require_admin
        app.dependency_overrides[require_admin] = lambda: test_admin["id"]
        yield
        app.dependency_overrides.pop(require_admin, None)

    @pytest.mark.asyncio
    async def test_set_active_invalid_value(self, client):
        response = await client.patch("/api/logistics-pool/1", json={"is_active": 2})
        assert response.status_code == 400
        assert "0 或 1" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_set_active_not_found(self, client):
        from api.routes import logistics_pool as pool_mod

        with patch.object(pool_mod, "set_active", new=AsyncMock(return_value=False)):
            response = await client.patch("/api/logistics-pool/999", json={"is_active": 1})

        assert response.status_code == 404
        assert "不存在" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_set_active_get_none_after(self, client):
        from api.routes import logistics_pool as pool_mod

        with patch.object(pool_mod, "set_active", new=AsyncMock(return_value=True)):
            with patch.object(pool_mod, "get_by_id", new=AsyncMock(return_value=None)):
                response = await client.patch("/api/logistics-pool/1", json={"is_active": 1})

        assert response.status_code == 404
        assert "查询失败" in response.json()["detail"]


class TestLogisticsPoolBatchAddErrors:
    @pytest.fixture(autouse=True)
    def _bypass(self, test_user):
        from api.main import app
        from api.dependencies import get_current_user_id
        app.dependency_overrides[get_current_user_id] = lambda: test_user["id"]
        yield
        app.dependency_overrides.pop(get_current_user_id, None)

    @pytest.mark.asyncio
    async def test_batch_add_dbapi_error_skips(self, client, test_user):
        from api.routes import logistics_pool as pool_mod

        fake_item = {"name": "rule1", "type": "land", "base_fee": "5.00"}
        with patch.object(pool_mod, "get_by_ids", new=AsyncMock(return_value={1: fake_item})):
            with patch.object(pool_mod, "create_logistics", new=AsyncMock(side_effect=DBAPIError("db fail", None, None))):
                response = await client.post(
                    "/api/logistics-pool/batch-add-to-my-logistics",
                    json={"ids": [1]},
                )

        assert response.status_code == 200
        data = response.json()
        assert data["added"] == 0
        assert len(data["errors"]) == 1

    @pytest.mark.asyncio
    async def test_batch_add_statement_error_skips(self, client, test_user):
        from api.routes import logistics_pool as pool_mod

        fake_item = {"name": "rule1", "type": "land", "base_fee": "5.00"}
        with patch.object(pool_mod, "get_by_ids", new=AsyncMock(return_value={1: fake_item})):
            with patch.object(pool_mod, "create_logistics", new=AsyncMock(side_effect=StatementError("stmt fail", None, None, None))):
                response = await client.post(
                    "/api/logistics-pool/batch-add-to-my-logistics",
                    json={"ids": [1]},
                )

        assert response.status_code == 200
        data = response.json()
        assert data["added"] == 0
        assert len(data["errors"]) == 1


class TestRateLimitMiddleware:
    def test_redis_fallback_to_memory(self):
        from api.middleware.rate_limit import RateLimitMiddleware, _try_get_redis

        with patch("api.middleware.rate_limit._try_get_redis", return_value=None):
            middleware = RateLimitMiddleware(MagicMock())
            assert middleware._check_rate_limit_memory("127.0.0.1") is True

    def test_evict_oldest_keys(self):
        from api.middleware.rate_limit import RateLimitMiddleware, MAX_TRACKED_KEYS

        middleware = RateLimitMiddleware(MagicMock())
        for i in range(MAX_TRACKED_KEYS + 5):
            middleware.requests[f"ip_{i}"].append(float(i))
        middleware._evict_oldest_keys()
        assert len(middleware.requests) <= MAX_TRACKED_KEYS

    def test_localhost_bypass_in_non_production(self):
        from api.middleware.rate_limit import RateLimitMiddleware

        middleware = RateLimitMiddleware(MagicMock())
        middleware._is_production = False
        result = middleware._check_rate_limit_memory("127.0.0.1")
        assert result is True

    def test_memory_limit_enforced(self):
        import time
        from api.middleware.rate_limit import RateLimitMiddleware

        now = time.time()
        middleware = RateLimitMiddleware(MagicMock(), max_requests=2, window_seconds=60)
        middleware.requests["1.2.3.4"] = [now - 1.0, now - 0.5]
        result = middleware._check_rate_limit_memory("1.2.3.4")
        assert result is False

    def test_try_get_redis_exception_returns_none(self):
        from api.middleware.rate_limit import _try_get_redis

        with patch("redis_cache.get_redis_client", side_effect=ImportError):
            result = _try_get_redis()
        assert result is None

    def test_redis_check_rate_limit(self):
        from api.middleware.rate_limit import RateLimitMiddleware

        mock_redis = MagicMock()
        mock_pipe = MagicMock()
        mock_redis.pipeline.return_value = mock_pipe
        mock_pipe.execute.return_value = [0, 0, 1, 1]

        middleware = RateLimitMiddleware(MagicMock(), max_requests=10)
        result = middleware._check_rate_limit_redis("1.2.3.4", mock_redis)
        assert result is True
        mock_pipe.execute.assert_called_once()

    def test_redis_rate_limit_exceeded(self):
        from api.middleware.rate_limit import RateLimitMiddleware

        mock_redis = MagicMock()
        mock_pipe = MagicMock()
        mock_redis.pipeline.return_value = mock_pipe
        mock_pipe.execute.return_value = [0, 10, 1, 1]

        middleware = RateLimitMiddleware(MagicMock(), max_requests=10)
        result = middleware._check_rate_limit_redis("1.2.3.4", mock_redis)
        assert result is False
        mock_redis.zrem.assert_called_once()

    @pytest.mark.asyncio
    async def test_dispatch_redis_exception_fallback(self):
        from api.middleware.rate_limit import RateLimitMiddleware

        middleware = RateLimitMiddleware(MagicMock())
        mock_redis = MagicMock()
        mock_redis.pipeline.side_effect = RuntimeError("redis down")

        request = MagicMock()
        request.method = "GET"
        request.headers = {}
        request.client.host = "1.2.3.4"

        call_next = AsyncMock(return_value=MagicMock())

        with patch("api.middleware.rate_limit._try_get_redis", return_value=mock_redis):
            response = await middleware.dispatch(request, call_next)

        call_next.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_dispatch_rate_limited(self):
        from api.middleware.rate_limit import RateLimitMiddleware

        middleware = RateLimitMiddleware(MagicMock(), max_requests=0, window_seconds=60)
        middleware._is_production = True

        request = MagicMock()
        request.method = "GET"
        request.headers = {}
        request.client.host = "1.2.3.4"

        call_next = AsyncMock()

        response = await middleware.dispatch(request, call_next)

        assert response.status_code == 429
        assert "Retry-After" in response.headers
        call_next.assert_not_awaited()
