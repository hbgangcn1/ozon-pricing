# pyright: reportUnusedFunction=false
import os
import sys
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: F401, E402
from fastapi.testclient import TestClient

from api import dependencies  # noqa: E402
from api.main import app  # noqa: E402
from database import get_db  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)

_ADMIN_USER_ID = 1


def _db_override(session):
    async def override():
        yield session

    return override


def _admin_user(user_id=_ADMIN_USER_ID):
    return {
        "id": user_id,
        "username": "admin",
        "role": "admin",
        "user_type": "permanent",
        "subscription_type": "enterprise",
        "remaining_calculations": -1,
    }


def _category_row(category_id=1, name="默认类目", user_id=_ADMIN_USER_ID):
    return {
        "id": category_id,
        "user_id": user_id,
        "name": name,
        "rfbs_tier1_rate": 0.06,
        "rfbs_tier2_rate": 0.07,
        "rfbs_tier3_rate": 0.08,
        "fbp_tier1_rate": 0.05,
        "fbp_tier2_rate": 0.06,
        "fbp_tier3_rate": 0.07,
        "is_active": 1,
    }


@pytest.fixture(autouse=True)
def _reset_dependencies():
    saved = dict(app.dependency_overrides)
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()
    app.dependency_overrides.update(saved)


def test_list_categories_success():
    session = AsyncMock()
    pro_user = {
        "id": 7,
        "username": "pro_user",
        "role": "user",
        "user_type": "permanent",
        "subscription_type": "professional",
        "remaining_calculations": -1,
        "trial_used": 0,
        "trial_started_at": 0,
        "trial_expires_at": 0,
        "trial_plan_at_start": "",
    }
    app.dependency_overrides[dependencies.get_user_with_subscription] = (
        lambda: pro_user
    )
    app.dependency_overrides[get_db] = _db_override(session)

    with patch(
        "api.routes.commission_categories.get_all",
        new=AsyncMock(return_value=[_category_row()]),
    ) as mock_get_all:
        response = client.get("/api/commission-categories")

    assert response.status_code == 200
    assert response.json() == [_category_row()]
    mock_get_all.assert_awaited_once_with(
        session,
        include_inactive=False,
        user_id=7,
    )


def test_list_categories_requires_login():
    response = client.get("/api/commission-categories")

    assert response.status_code == 401
    assert response.json()["detail"] == "未提供认证凭证"


def test_create_category_success():
    session = AsyncMock()
    payload = {
        "name": "服饰",
        "rfbs_tier1_rate": 0.06,
        "rfbs_tier2_rate": 0.07,
        "rfbs_tier3_rate": 0.08,
    }
    created = {
        "name": "服饰",
        "user_id": _ADMIN_USER_ID,
        "rfbs_tier1_rate": 0.06,
        "rfbs_tier2_rate": 0.07,
        "rfbs_tier3_rate": 0.08,
        "fbp_tier1_rate": 0.05,
        "fbp_tier2_rate": 0.06,
        "fbp_tier3_rate": 0.07,
        "id": 11,
        "is_active": 1,
    }
    app.dependency_overrides[dependencies.get_user_with_subscription] = lambda: (
        _admin_user()
    )
    app.dependency_overrides[get_db] = _db_override(session)

    with (
        patch(
            "api.routes.commission_categories.create",
            new=AsyncMock(return_value=11),
        ) as mock_create,
        patch(
            "api.routes.commission_categories.get_by_id",
            new=AsyncMock(return_value=created),
        ) as mock_get,
    ):
        response = client.post("/api/commission-categories", json=payload)

    assert response.status_code == 201
    assert response.json() == created
    mock_create.assert_awaited_once_with(
        session,
        {
            "rfbs_tier1_rate": 0.06,
            "rfbs_tier2_rate": 0.07,
            "rfbs_tier3_rate": 0.08,
            "fbp_tier1_rate": round(0.06 - 0.01, 4),
            "fbp_tier2_rate": round(0.07 - 0.01, 4),
            "fbp_tier3_rate": round(0.08 - 0.01, 4),
            "name": "服饰",
            "user_id": _ADMIN_USER_ID,
            "is_active": 1,
        },
    )
    mock_get.assert_awaited_once_with(session, 11, _ADMIN_USER_ID)


def test_create_category_rejects_duplicate_name():
    session = AsyncMock()
    app.dependency_overrides[dependencies.get_user_with_subscription] = lambda: (
        _admin_user()
    )
    app.dependency_overrides[get_db] = _db_override(session)

    with patch(
        "api.routes.commission_categories.create",
        new=AsyncMock(return_value=None),
    ) as mock_create:
        response = client.post(
            "/api/commission-categories",
            json={
                "name": "重复类目",
                "rfbs_tier1_rate": 0.05,
                "rfbs_tier2_rate": 0.06,
                "rfbs_tier3_rate": 0.07,
            },
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "佣金类目名称已存在"
    mock_create.assert_awaited_once()


def test_update_category_success():
    session = AsyncMock()
    current = _category_row(category_id=3, name="旧名称")
    updated = _category_row(category_id=3, name="新名称")
    app.dependency_overrides[dependencies.get_user_with_subscription] = lambda: (
        _admin_user()
    )
    app.dependency_overrides[get_db] = _db_override(session)

    with (
        patch(
            "api.routes.commission_categories.get_by_id",
            new=AsyncMock(side_effect=[current, updated]),
        ) as mock_get,
        patch(
            "api.routes.commission_categories.update",
            new=AsyncMock(return_value=True),
        ) as mock_update,
    ):
        response = client.patch(
            "/api/commission-categories/3",
            json={"name": "新名称", "rfbs_tier2_rate": 0.08},
        )

    assert response.status_code == 200
    assert response.json() == updated
    mock_update.assert_awaited_once_with(
        session,
        3,
        {
            "name": "新名称",
            "rfbs_tier2_rate": 0.08,
            "fbp_tier2_rate": round(0.08 - 0.01, 4),
        },
        _ADMIN_USER_ID,
    )
    assert mock_get.await_count == 2


def test_update_category_returns_404_when_missing():
    session = AsyncMock()
    app.dependency_overrides[dependencies.get_user_with_subscription] = lambda: (
        _admin_user()
    )
    app.dependency_overrides[get_db] = _db_override(session)

    with patch(
        "api.routes.commission_categories.get_by_id",
        new=AsyncMock(return_value=None),
    ) as mock_get:
        response = client.patch(
            "/api/commission-categories/999",
            json={"name": "不存在"},
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "佣金类目不存在"
    mock_get.assert_awaited_once_with(session, 999, _ADMIN_USER_ID)


def test_delete_category_success():
    session = AsyncMock()
    app.dependency_overrides[dependencies.get_user_with_subscription] = lambda: (
        _admin_user()
    )
    app.dependency_overrides[get_db] = _db_override(session)

    with patch(
        "api.routes.commission_categories.soft_delete",
        new=AsyncMock(return_value=True),
    ) as mock_delete:
        response = client.delete("/api/commission-categories/5")

    assert response.status_code == 200
    assert response.json() == {"message": "删除成功", "success": True}
    mock_delete.assert_awaited_once_with(session, 5, _ADMIN_USER_ID)


def test_delete_category_returns_404_when_missing():
    session = AsyncMock()
    app.dependency_overrides[dependencies.get_user_with_subscription] = lambda: (
        _admin_user()
    )
    app.dependency_overrides[get_db] = _db_override(session)

    with patch(
        "api.routes.commission_categories.soft_delete",
        new=AsyncMock(return_value=False),
    ) as mock_delete:
        response = client.delete("/api/commission-categories/404")

    assert response.status_code == 404
    assert response.json()["detail"] == "佣金类目不存在"
    mock_delete.assert_awaited_once_with(session, 404, _ADMIN_USER_ID)
