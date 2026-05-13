import pytest

from api.dependencies import get_current_user_id
from api.main import app


@pytest.mark.asyncio
async def test_logistics_pool_list_accepts_limit_1000(client, test_user):
    app.dependency_overrides[get_current_user_id] = lambda: test_user["id"]
    try:
        response = await client.get("/api/logistics-pool?limit=1000")
        assert response.status_code == 200
        body = response.json()
        assert body["limit"] == 1000
        assert "items" in body
        assert "total" in body
        assert "offset" in body
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_logistics_pool_list_rejects_limit_1001(client, test_user):
    app.dependency_overrides[get_current_user_id] = lambda: test_user["id"]
    try:
        response = await client.get("/api/logistics-pool?limit=1001")
        assert response.status_code == 422
        body = response.json()
        detail = body.get("detail", [])
        assert any(
            "limit" in (err.get("loc") or []) for err in detail
        ), f"422 should pinpoint 'limit' field, got: {detail}"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_logistics_pool_list_empty_returns_200(client, test_user):
    """空池场景：用 destination 过滤到一个绝不存在的值，模拟"空结果"——不破坏本地数据。"""
    app.dependency_overrides[get_current_user_id] = lambda: test_user["id"]
    try:
        response = await client.get(
            "/api/logistics-pool?destination=__NONEXISTENT_DEST_FOR_EMPTY_TEST__"
        )
        assert response.status_code == 200, (
            f"empty result must be 200 not 404, got {response.status_code}"
        )
        body = response.json()
        assert body["items"] == []
        assert body["total"] == 0
        assert body["limit"] == 100
        assert body["offset"] == 0
    finally:
        app.dependency_overrides.clear()
