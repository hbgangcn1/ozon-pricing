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


def _db_override(session):
    async def override():
        yield session

    return override


@pytest.fixture(autouse=True)
def _reset_dependencies():
    saved = dict(app.dependency_overrides)
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()
    app.dependency_overrides.update(saved)


def test_extend_subscription_accepts_positive_days():
    session = AsyncMock()
    app.dependency_overrides[dependencies.require_admin] = lambda: 1
    app.dependency_overrides[get_db] = _db_override(session)

    with patch(
        "api.routes.admin.db_admin.extend_subscription",
        new=AsyncMock(return_value=True),
    ) as mock_extend:
        response = client.post(
            "/api/admin/users/12/subscription/extend",
            json={"days": 30},
        )

    assert response.status_code == 200
    assert response.json() == {"message": "订阅时长调整成功", "success": True}
    mock_extend.assert_awaited_once_with(session, 12, 30)


def test_extend_subscription_accepts_negative_days():
    session = AsyncMock()
    app.dependency_overrides[dependencies.require_admin] = lambda: 1
    app.dependency_overrides[get_db] = _db_override(session)

    with patch(
        "api.routes.admin.db_admin.extend_subscription",
        new=AsyncMock(return_value=True),
    ) as mock_extend:
        response = client.post(
            "/api/admin/users/12/subscription/extend",
            json={"days": -7},
        )

    assert response.status_code == 200
    mock_extend.assert_awaited_once_with(session, 12, -7)


def test_extend_subscription_returns_404_when_user_missing():
    session = AsyncMock()
    app.dependency_overrides[dependencies.require_admin] = lambda: 1
    app.dependency_overrides[get_db] = _db_override(session)

    with patch(
        "api.routes.admin.db_admin.extend_subscription",
        new=AsyncMock(return_value=False),
    ) as mock_extend:
        response = client.post(
            "/api/admin/users/404/subscription/extend",
            json={"days": 3},
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "用户不存在"
    mock_extend.assert_awaited_once_with(session, 404, 3)


def test_adjust_calculations_accepts_positive_delta():
    session = AsyncMock()
    app.dependency_overrides[dependencies.require_admin] = lambda: 1
    app.dependency_overrides[get_db] = _db_override(session)

    with patch(
        "api.routes.admin.db_admin.adjust_calculations",
        new=AsyncMock(return_value=True),
    ) as mock_adjust:
        response = client.post(
            "/api/admin/users/18/calculations/adjust",
            json={"delta": 15},
        )

    assert response.status_code == 200
    assert response.json() == {"message": "计算次数调整成功", "success": True}
    mock_adjust.assert_awaited_once_with(session, 18, 15)


def test_adjust_calculations_accepts_negative_delta():
    session = AsyncMock()
    app.dependency_overrides[dependencies.require_admin] = lambda: 1
    app.dependency_overrides[get_db] = _db_override(session)

    with patch(
        "api.routes.admin.db_admin.adjust_calculations",
        new=AsyncMock(return_value=True),
    ) as mock_adjust:
        response = client.post(
            "/api/admin/users/18/calculations/adjust",
            json={"delta": -4},
        )

    assert response.status_code == 200
    mock_adjust.assert_awaited_once_with(session, 18, -4)


def test_adjust_calculations_returns_404_when_user_missing():
    session = AsyncMock()
    app.dependency_overrides[dependencies.require_admin] = lambda: 1
    app.dependency_overrides[get_db] = _db_override(session)

    with patch(
        "api.routes.admin.db_admin.adjust_calculations",
        new=AsyncMock(return_value=False),
    ) as mock_adjust:
        response = client.post(
            "/api/admin/users/404/calculations/adjust",
            json={"delta": 1},
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "用户不存在"
    mock_adjust.assert_awaited_once_with(session, 404, 1)


def test_set_user_type_accepts_valid_type():
    session = AsyncMock()
    app.dependency_overrides[dependencies.require_admin] = lambda: 1
    app.dependency_overrides[get_db] = _db_override(session)

    with patch(
        "api.routes.admin.db_admin.set_user_type",
        new=AsyncMock(return_value=True),
    ) as mock_set_user_type:
        response = client.post(
            "/api/admin/users/22/type",
            json={"user_type": "enterprise"},
        )

    assert response.status_code == 200
    assert response.json() == {"message": "用户类型更新成功", "success": True}
    mock_set_user_type.assert_awaited_once_with(session, 22, "enterprise")


def test_set_user_type_rejects_invalid_type():
    session = AsyncMock()
    app.dependency_overrides[dependencies.require_admin] = lambda: 1
    app.dependency_overrides[get_db] = _db_override(session)

    with patch(
        "api.routes.admin.db_admin.set_user_type",
        new=AsyncMock(return_value=False),
    ) as mock_set_user_type:
        response = client.post(
            "/api/admin/users/22/type",
            json={"user_type": "invalid-tier"},
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "用户不存在或用户类型无效"
    mock_set_user_type.assert_awaited_once_with(session, 22, "invalid-tier")
