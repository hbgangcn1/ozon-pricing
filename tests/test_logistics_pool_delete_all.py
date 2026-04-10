# pyright: reportUnusedFunction=false
import os
import sys
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api import dependencies  # noqa: E402
from api.main import app  # noqa: E402
from database import get_db  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)


def _db_override(session):
    async def override():
        yield session

    return override


def _pool_row(pool_id=1):
    return {
        "id": pool_id,
        "name": "标准物流",
        "delivery_method": "pickup",
        "source_file": "rules.xlsx",
        "imported_at": "2026-04-06 10:00:00",
        "fulfillment_type": "fbp",
        "destination": "RU",
        "fbp_service_level": "standard",
        "is_active": 1,
        "base_fee": 11.5,
    }


@pytest.fixture(autouse=True)
def _reset_dependencies():
    saved = dict(app.dependency_overrides)
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()
    app.dependency_overrides.update(saved)


def test_delete_all_logistics_pool_returns_deleted_count():
    session = AsyncMock()
    app.dependency_overrides[dependencies.require_admin] = lambda: 1
    app.dependency_overrides[get_db] = _db_override(session)

    with patch(
        "api.routes.logistics_pool.delete_all",
        new=AsyncMock(return_value=3),
    ) as mock_delete_all:
        response = client.delete("/api/logistics-pool/all")

    assert response.status_code == 200
    assert response.json() == {"deleted": 3}
    assert response.json()["deleted"] >= 0
    mock_delete_all.assert_awaited_once_with(session)


def test_set_logistics_pool_active_still_works_after_route_reorder():
    session = AsyncMock()
    updated = {**_pool_row(pool_id=6), "is_active": 0}
    app.dependency_overrides[dependencies.require_admin] = lambda: 1
    app.dependency_overrides[get_db] = _db_override(session)

    with (
        patch(
            "api.routes.logistics_pool.set_active",
            new=AsyncMock(return_value=True),
        ) as mock_set_active,
        patch(
            "api.routes.logistics_pool.get_by_id",
            new=AsyncMock(return_value=updated),
        ) as mock_get_by_id,
    ):
        response = client.patch("/api/logistics-pool/6", json={"is_active": 0})

    assert response.status_code == 200
    assert response.json() == updated
    mock_set_active.assert_awaited_once_with(session, 6, 0)
    mock_get_by_id.assert_awaited_once_with(session, 6)
