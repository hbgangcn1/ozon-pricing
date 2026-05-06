"""
Integration tests for POST /api/logistics-pool/batch-add-to-my-logistics
and regression test for POST /api/logistics-pool/{pool_id}/add-to-my-logistics.

Uses real PostgreSQL via AsyncSessionLocal (no mocked sessions).
"""

import time
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import DataError, DBAPIError

from api import dependencies
from api.main import app
from database import AsyncSessionLocal, get_db
from db.logistics_crud import create_logistics
from db.logistics_pool import upsert


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pool_data(token: str, **overrides) -> dict:
    data = {
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
    data.update(overrides)
    return data


async def _seed_pool_rows(count: int) -> list[int]:
    """Insert `count` logistics_pool rows; return their IDs."""
    ids = []
    async with AsyncSessionLocal() as session:
        for i in range(count):
            token = f"batch_{time.time_ns()}_{i}"
            new_id = await upsert(session, _pool_data(token))
            ids.append(new_id)
        await session.commit()
    return ids


async def _delete_pool_rows(ids: list[int]) -> None:
    """Clean up seeded logistics_pool rows."""
    if not ids:
        return
    async with AsyncSessionLocal() as session:
        await session.execute(
            text("DELETE FROM logistics_pool WHERE id = ANY(:ids)"),
            {"ids": ids},
        )
        await session.commit()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def overridden_app(db_session, test_user):
    """Override auth + DB + quota dependencies for the test user."""

    async def _yield_session():
        yield db_session

    app.dependency_overrides[dependencies.get_current_user_id] = (
        lambda: test_user["id"]
    )
    app.dependency_overrides[get_db] = _yield_session

    with (
        patch(
            "api.routes.logistics_pool._get_user_subscription",
            new=AsyncMock(return_value=("user", "free")),
        ),
        patch(
            "api.routes.logistics_pool.get_plan_by_code",
            new=AsyncMock(
                return_value={"logistics_limit": -1, "plan_name": "Unlimited"}
            ),
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


# ---------------------------------------------------------------------------
# Test A: full success
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_batch_add_full_success(http_client, db_session, test_user):
    pool_ids = await _seed_pool_rows(3)
    try:
        resp = await http_client.post(
            "/api/logistics-pool/batch-add-to-my-logistics",
            json={"ids": pool_ids},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["added"] == 3
        assert len(body["new_ids"]) == 3
        assert body["errors"] == []
        assert body["not_found"] == []

        # Verify 3 logistics rows in DB for test_user
        from sqlalchemy import select
        from models.logistics import Logistics
        result = await db_session.execute(
            select(Logistics).where(Logistics.user_id == test_user["id"])
        )
        rows = result.scalars().all()
        assert len(rows) == 3
    finally:
        await _delete_pool_rows(pool_ids)


# ---------------------------------------------------------------------------
# Test B: partial not_found
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_batch_add_partial_not_found(http_client, db_session, test_user):
    pool_ids = await _seed_pool_rows(1)
    try:
        resp = await http_client.post(
            "/api/logistics-pool/batch-add-to-my-logistics",
            json={"ids": [pool_ids[0], 999999999]},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["added"] == 1
        assert body["not_found"] == [999999999]
        assert body["errors"] == []
    finally:
        await _delete_pool_rows(pool_ids)


# ---------------------------------------------------------------------------
# Test C: empty ids → 400
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_batch_add_empty_ids_400(http_client):
    resp = await http_client.post(
        "/api/logistics-pool/batch-add-to-my-logistics",
        json={"ids": []},
    )
    assert resp.status_code == 400
    assert "ids 不能为空" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Test D: over 200 ids → 400
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_batch_add_over_limit_400(http_client):
    resp = await http_client.post(
        "/api/logistics-pool/batch-add-to-my-logistics",
        json={"ids": list(range(1, 202))},
    )
    assert resp.status_code == 400
    assert "单次最多添加 200 条" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Test E: IntegrityError isolated via SAVEPOINT
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_batch_add_integrity_error_isolated(
    http_client, db_session, test_user
):
    """
    Inject an invalid volume_mode on the 2nd call to _sanitize_pool_data
    so the DB CHECK constraint fires. The SAVEPOINT must isolate the failure
    and the other 2 rows must still be inserted.
    """
    pool_ids = await _seed_pool_rows(3)
    try:
        call_counter = {"n": 0}
        original_sanitize = (
            __import__(
                "api.routes.logistics_pool",
                fromlist=["_sanitize_pool_data"],
            )._sanitize_pool_data
        )

        def _patched_sanitize(data):
            call_counter["n"] += 1
            result = original_sanitize(data)
            if call_counter["n"] == 2:
                result["volume_mode"] = "__INVALID__"
            return result

        with patch(
            "api.routes.logistics_pool._sanitize_pool_data",
            side_effect=_patched_sanitize,
        ):
            resp = await http_client.post(
                "/api/logistics-pool/batch-add-to-my-logistics",
                json={"ids": pool_ids},
            )

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["added"] == 2, body
        assert len(body["errors"]) == 1, body
        assert len(body["new_ids"]) == 2, body

        # Verify 2 logistics rows in DB
        from sqlalchemy import select
        from models.logistics import Logistics
        result = await db_session.execute(
            select(Logistics).where(Logistics.user_id == test_user["id"])
        )
        rows = result.scalars().all()
        assert len(rows) == 2
    finally:
        await _delete_pool_rows(pool_ids)


# ---------------------------------------------------------------------------
# Test F: DataError isolated
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_batch_add_dataerror_isolated(
    http_client, db_session, test_user
):
    pool_ids = await _seed_pool_rows(3)
    try:
        call_counter = {"n": 0}
        original_create = create_logistics

        async def _patched_create(session, user_id, data):
            call_counter["n"] += 1
            if call_counter["n"] == 2:
                raise DataError("INSERT", {}, Exception("bad enum"))
            return await original_create(session, user_id, data)

        with patch(
            "api.routes.logistics_pool.create_logistics",
            side_effect=_patched_create,
        ):
            resp = await http_client.post(
                "/api/logistics-pool/batch-add-to-my-logistics",
                json={"ids": pool_ids},
            )

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["added"] == 2, body
        assert len(body["errors"]) == 1, body
    finally:
        await _delete_pool_rows(pool_ids)


# ---------------------------------------------------------------------------
# Test G: AttributeError propagates to 500
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_batch_add_attribute_error_propagates_to_500(
    overridden_app, db_session, test_user
):
    pool_ids = await _seed_pool_rows(3)
    try:
        with patch(
            "api.routes.logistics_pool.create_logistics",
            side_effect=AttributeError("programmer bug"),
        ):
            transport = ASGITransport(
                app=overridden_app, raise_app_exceptions=False
            )
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as ac:
                resp = await ac.post(
                    "/api/logistics-pool/batch-add-to-my-logistics",
                    json={"ids": pool_ids},
                )
        assert resp.status_code == 500, resp.text
    finally:
        await _delete_pool_rows(pool_ids)


# ---------------------------------------------------------------------------
# Test I: DBAPIError with connection_invalidated re-raises (500), not silenced
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_batch_add_connection_invalidated_propagates_to_500(
    overridden_app, db_session, test_user
):
    pool_ids = await _seed_pool_rows(3)
    try:
        exc = DBAPIError("INSERT", {}, Exception("connection lost"))
        exc.connection_invalidated = True

        with patch(
            "api.routes.logistics_pool.create_logistics",
            side_effect=exc,
        ):
            transport = ASGITransport(
                app=overridden_app, raise_app_exceptions=False
            )
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as ac:
                resp = await ac.post(
                    "/api/logistics-pool/batch-add-to-my-logistics",
                    json={"ids": pool_ids},
                )
        assert resp.status_code == 500, resp.text
    finally:
        await _delete_pool_rows(pool_ids)


# ---------------------------------------------------------------------------
# Test J: DBAPIError without connection_invalidated → isolated single-row skip
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_batch_add_dbapi_error_isolated(
    http_client, db_session, test_user
):
    pool_ids = await _seed_pool_rows(3)
    try:
        call_counter = {"n": 0}
        original_create = create_logistics

        async def _patched_create(session, user_id, data):
            call_counter["n"] += 1
            if call_counter["n"] == 2:
                exc = DBAPIError("INSERT", {}, Exception("operational"))
                exc.connection_invalidated = False
                raise exc
            return await original_create(session, user_id, data)

        with patch(
            "api.routes.logistics_pool.create_logistics",
            side_effect=_patched_create,
        ):
            resp = await http_client.post(
                "/api/logistics-pool/batch-add-to-my-logistics",
                json={"ids": pool_ids},
            )

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["added"] == 2, body
        assert len(body["errors"]) == 1, body
    finally:
        await _delete_pool_rows(pool_ids)


# ---------------------------------------------------------------------------
# Test H: single add regression
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_single_add_regression(http_client, db_session, test_user):
    pool_ids = await _seed_pool_rows(1)
    try:
        resp = await http_client.post(
            f"/api/logistics-pool/{pool_ids[0]}/add-to-my-logistics",
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "id" in body
        assert isinstance(body["id"], int)

        # Verify logistics row exists in DB
        from sqlalchemy import select
        from models.logistics import Logistics
        result = await db_session.execute(
            select(Logistics).where(
                Logistics.id == body["id"],
                Logistics.user_id == test_user["id"],
            )
        )
        row = result.scalar_one_or_none()
        assert row is not None
    finally:
        await _delete_pool_rows(pool_ids)
