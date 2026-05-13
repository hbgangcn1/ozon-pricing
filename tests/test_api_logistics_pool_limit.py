import time

import pytest
from sqlalchemy import text

from api.dependencies import get_current_user_id
from api.main import app
from database import AsyncSessionLocal
from db.logistics_pool import upsert


def _pool_data(token: str) -> dict:
    return {
        "name": f"Pool {token}",
        "type": "standard",
        "min_days": 3,
        "max_days": 7,
        "price_limit_cny": 199.0,
        "price_min_cny": 20.0,
        "delivery_method": f"method_{token}",
        "fulfillment_type": "fbp",
        "destination": f"DEST_{token}",
        "fbp_service_level": f"level_{token}",
        "source_file": f"source_{token}.xlsx",
        "is_active": 1,
        "volume_mode": "none",
    }


async def _seed_pool_rows(count: int) -> list[int]:
    ids: list[int] = []
    async with AsyncSessionLocal() as session:
        for i in range(count):
            token = f"limit_{time.time_ns()}_{i}"
            new_id = await upsert(session, _pool_data(token))
            ids.append(new_id)
        await session.commit()
    return ids


async def _delete_pool_rows(ids: list[int]) -> None:
    if not ids:
        return
    async with AsyncSessionLocal() as session:
        await session.execute(
            text("DELETE FROM logistics_pool WHERE id = ANY(:ids)"),
            {"ids": ids},
        )
        await session.commit()


@pytest.mark.asyncio
async def test_logistics_pool_batch_add_rejects_51_ids(client, test_user):
    app.dependency_overrides[get_current_user_id] = lambda: test_user["id"]
    try:
        response = await client.post(
            "/api/logistics-pool/batch-add-to-my-logistics",
            json={"ids": list(range(1, 52))},
        )
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()


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
