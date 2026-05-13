"""
Boundary tests for POST /api/logistics-pool/batch-add-to-my-logistics
covering the new max_length=200 contract introduced by OpenSpec change
fix-logistics-pool-batch-add-blackscreen.

Spec contract (specs/logistics-pool-batch-add/spec.md):
- empty ids -> 400 string detail "ids 不能为空"
- exactly 200 ids -> 200 OK
- 201 ids -> 400 string detail "单次最多添加 200 条"
- 51 ids -> 200 (regression guard, used to be 422 under old max_length=50)
"""

import time
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from api import dependencies
from api.main import app
from database import AsyncSessionLocal, get_db
from db.logistics_pool import upsert
from sqlalchemy import text


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
    ids = []
    async with AsyncSessionLocal() as session:
        for i in range(count):
            token = f"boundary_{time.time_ns()}_{i}"
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


@pytest_asyncio.fixture
async def overridden_app(db_session, test_user):
    async def _yield_session():
        yield db_session

    app.dependency_overrides[dependencies.get_current_user_id] = (
        lambda: test_user["id"]
    )
    app.dependency_overrides[get_db] = _yield_session

    with (
        patch(
            "api.routes.logistics_pool.get_effective_logistics_limit",
            new=AsyncMock(return_value=-1),
        ),
        patch(
            "api.routes.logistics_pool.count_user_active_rules",
            new=AsyncMock(return_value=0),
        ),
        patch(
            "api.routes.logistics_pool.recalculate_priority_groups",
            new=AsyncMock(),
        ),
    ):
        yield app

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def http_client(overridden_app):
    transport = ASGITransport(app=overridden_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_empty_ids_returns_400_string_detail(http_client):
    resp = await http_client.post(
        "/api/logistics-pool/batch-add-to-my-logistics",
        json={"ids": []},
    )
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert isinstance(detail, str)
    assert "ids 不能为空" in detail


@pytest.mark.asyncio
async def test_201_ids_returns_400_string_detail(http_client):
    resp = await http_client.post(
        "/api/logistics-pool/batch-add-to-my-logistics",
        json={"ids": list(range(1, 202))},
    )
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert isinstance(detail, str)
    assert "单次最多添加 200 条" in detail


@pytest.mark.asyncio
async def test_exactly_200_ids_succeeds(http_client):
    pool_ids = await _seed_pool_rows(200)
    try:
        resp = await http_client.post(
            "/api/logistics-pool/batch-add-to-my-logistics",
            json={"ids": pool_ids},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["added"] == 200
    finally:
        await _delete_pool_rows(pool_ids)


@pytest.mark.asyncio
async def test_51_ids_no_longer_422(http_client):
    pool_ids = await _seed_pool_rows(51)
    try:
        resp = await http_client.post(
            "/api/logistics-pool/batch-add-to-my-logistics",
            json={"ids": pool_ids},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["added"] == 51
    finally:
        await _delete_pool_rows(pool_ids)
