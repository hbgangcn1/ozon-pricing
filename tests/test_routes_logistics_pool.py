# pyright: reportUnusedFunction=false
import os
import sys
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient

from api import dependencies  # noqa: E402
from api.main import app  # noqa: E402
from database import get_db  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _patch_recalculate():
    with (
        patch(
            "api.routes.logistics_pool.recalculate_priority_groups",
            new=AsyncMock(),
        ),
        patch(
            "api.routes.logistics_pool._get_user_subscription",
            new=AsyncMock(return_value=("admin", "free")),
        ),
        patch(
            "api.routes.logistics_pool.get_plan_by_code",
            new=AsyncMock(return_value={"logistics_limit": -1, "plan_name": "Unlimited"}),
        ),
        patch(
            "api.routes.logistics_pool.get_logistics_by_filters",
            new=AsyncMock(return_value=([], 0)),
        ),
    ):
        yield


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
        "fee_mode": "first_weight",
        "continue_unit": "500g",
        "continue_fee": 15.0,
        "first_fee": 52.5,
        "first_weight_g": 1000,
    }


@pytest.fixture(autouse=True)
def _reset_dependencies():
    saved = dict(app.dependency_overrides)
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()
    app.dependency_overrides.update(saved)


def test_list_logistics_pool_success():
    session = AsyncMock()
    items = [_pool_row()]
    app.dependency_overrides[dependencies.get_current_user_id] = lambda: 8
    app.dependency_overrides[get_db] = _db_override(session)

    with patch(
        "api.routes.logistics_pool.get_all",
        new=AsyncMock(return_value=(items, 1)),
    ) as mock_get_all:
        response = client.get(
            "/api/logistics-pool",
            params={"fulfillment_type": "fbp", "limit": 50, "offset": 10},
        )

    assert response.status_code == 200
    assert response.json() == {
        "items": items,
        "total": 1,
        "limit": 50,
        "offset": 10,
    }
    mock_get_all.assert_awaited_once_with(
        session,
        fulfillment_type="fbp",
        destination=None,
        fbp_service_level=None,
        limit=50,
        offset=10,
    )


def test_list_logistics_pool_requires_login():
    response = client.get("/api/logistics-pool")

    assert response.status_code == 401
    assert response.json()["detail"] == "未提供认证凭证"


def test_import_logistics_pool_success():
    session = AsyncMock()
    rows = [
        {"delivery_method": "pickup", "destination": "RU", "source_file": "pool.xlsx"},
        {"delivery_method": "door", "destination": "BY", "source_file": "pool.xlsx"},
    ]
    app.dependency_overrides[dependencies.require_admin] = lambda: 1
    app.dependency_overrides[dependencies.get_user_with_subscription] = lambda: {
        "id": 1,
        "username": "admin",
        "role": "admin",
        "user_type": "permanent",
        "subscription_type": "enterprise",
        "remaining_calculations": -1,
    }
    app.dependency_overrides[get_db] = _db_override(session)

    with (
        patch(
            "api.routes.logistics_pool.parse_file",
            return_value={"rows": rows, "skipped": 1, "errors": ["row 0 ignored"]},
        ) as mock_parse,
        patch(
            "api.routes.logistics_pool.insert_row",
            new=AsyncMock(side_effect=[101, 102]),
        ) as mock_insert,
    ):
        response = client.post(
            "/api/logistics-pool/import",
            files={
                "file": (
                    "pool.xlsx",
                    b"fake-xlsx-content",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "imported": 2,
        "skipped": 1,
        "errors": ["row 0 ignored"],
    }
    mock_parse.assert_called_once()
    assert mock_insert.await_args_list[0].args == (session, rows[0])
    assert mock_insert.await_args_list[1].args == (session, rows[1])


def test_import_logistics_pool_requires_admin():
    response = client.post(
        "/api/logistics-pool/import",
        files={
            "file": (
                "pool.xlsx",
                b"fake-xlsx-content",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "未提供认证凭证"


def test_set_logistics_pool_active_success():
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
        ) as mock_get,
    ):
        response = client.patch("/api/logistics-pool/6", json={"is_active": 0})

    assert response.status_code == 200
    assert response.json() == updated
    mock_set_active.assert_awaited_once_with(session, 6, 0)
    mock_get.assert_awaited_once_with(session, 6)


def test_set_logistics_pool_active_rejects_invalid_status():
    session = AsyncMock()
    app.dependency_overrides[dependencies.require_admin] = lambda: 1
    app.dependency_overrides[get_db] = _db_override(session)

    response = client.patch("/api/logistics-pool/6", json={"is_active": 2})

    assert response.status_code == 400
    assert response.json()["detail"] == "is_active 只能是 0 或 1"


def test_add_to_my_logistics_success():
    session = AsyncMock()
    pool_item = _pool_row(pool_id=9)
    app.dependency_overrides[dependencies.get_current_user_id] = lambda: 18
    app.dependency_overrides[get_db] = _db_override(session)

    with (
        patch(
            "api.routes.logistics_pool.get_by_id",
            new=AsyncMock(return_value=pool_item),
        ) as mock_get,
        patch(
            "api.routes.logistics_pool.create_logistics",
            new=AsyncMock(return_value=501),
        ) as mock_create,
    ):
        response = client.post("/api/logistics-pool/9/add-to-my-logistics")

    assert response.status_code == 200
    assert response.json() == {"id": 501}
    mock_get.assert_awaited_once_with(session, 9)
    mock_create.assert_awaited_once_with(
        session,
        18,
        {
            "name": "标准物流",
            "delivery_method": "pickup",
            "fulfillment_type": "fbp",
            "destination": "RU",
            "fbp_service_level": "standard",
            "base_fee": 11.5,
            "fee_mode": "first_weight",
            "continue_unit": "500g",
            "continue_fee": 15.0,
            "first_fee": 52.5,
            "first_weight_g": 1000,
            "min_days": 0,
            "max_days": 0,
        },
    )


def test_add_to_my_logistics_returns_404_when_pool_item_missing():
    session = AsyncMock()
    app.dependency_overrides[dependencies.get_current_user_id] = lambda: 18
    app.dependency_overrides[get_db] = _db_override(session)

    with patch(
        "api.routes.logistics_pool.get_by_id",
        new=AsyncMock(return_value=None),
    ) as mock_get:
        response = client.post("/api/logistics-pool/404/add-to-my-logistics")

    assert response.status_code == 404
    assert response.json()["detail"] == "物流池条目不存在"
    mock_get.assert_awaited_once_with(session, 404)


def test_batch_add_to_my_logistics_success():
    session = AsyncMock()
    pool_items = {
        10: _pool_row(pool_id=10),
        11: _pool_row(pool_id=11),
    }
    app.dependency_overrides[dependencies.get_current_user_id] = lambda: 18
    app.dependency_overrides[get_db] = _db_override(session)

    call_count = 0

    async def mock_get_by_id(sess, pid):
        return pool_items.get(pid)

    async def mock_create(sess, uid, data):
        nonlocal call_count
        call_count += 1
        return 600 + call_count

    with (
        patch(
            "api.routes.logistics_pool.get_by_id",
            new=AsyncMock(side_effect=mock_get_by_id),
        ),
        patch(
            "api.routes.logistics_pool.create_logistics",
            new=AsyncMock(side_effect=mock_create),
        ),
    ):
        response = client.post(
            "/api/logistics-pool/batch-add-to-my-logistics",
            json={"ids": [10, 11]},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["added"] == 2
    assert body["not_found"] == []
    assert len(body["new_ids"]) == 2


def test_batch_add_to_my_logistics_partial_not_found():
    session = AsyncMock()
    pool_item = _pool_row(pool_id=20)
    app.dependency_overrides[dependencies.get_current_user_id] = lambda: 18
    app.dependency_overrides[get_db] = _db_override(session)

    async def mock_get_by_id(sess, pid):
        if pid == 20:
            return pool_item
        return None

    with (
        patch(
            "api.routes.logistics_pool.get_by_id",
            new=AsyncMock(side_effect=mock_get_by_id),
        ),
        patch(
            "api.routes.logistics_pool.create_logistics",
            new=AsyncMock(return_value=700),
        ),
    ):
        response = client.post(
            "/api/logistics-pool/batch-add-to-my-logistics",
            json={"ids": [20, 999]},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["added"] == 1
    assert body["not_found"] == [999]


def test_batch_add_to_my_logistics_empty_ids():
    session = AsyncMock()
    app.dependency_overrides[dependencies.get_current_user_id] = lambda: 18
    app.dependency_overrides[get_db] = _db_override(session)

    response = client.post(
        "/api/logistics-pool/batch-add-to-my-logistics",
        json={"ids": []},
    )

    assert response.status_code == 400
    assert "不能为空" in response.json()["detail"]


def test_batch_add_to_my_logistics_requires_login():
    response = client.post(
        "/api/logistics-pool/batch-add-to-my-logistics",
        json={"ids": [1, 2]},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "未提供认证凭证"
