import os
import sys
from unittest.mock import AsyncMock, patch

import pytest  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import HTTPException  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from api.main import app  # noqa: E402
from api import dependencies  # noqa: E402
from database import get_db  # noqa: E402


def _admin_override():
    return 1


def _current_user_override():
    return 1


def _non_admin_override():
    raise HTTPException(status_code=403, detail="需要管理员权限")


def _make_mock_session():
    session = AsyncMock()
    session.commit = AsyncMock()
    return session


SAMPLE_PLAN = {
    "plan_code": "test_plan",
    "plan_name": "测试套餐",
    "display_price_month": 9.9,
    "display_price_year": 99,
    "actual_price_month": 9.9,
    "actual_price_year": 99,
    "test_price_month": 0.01,
    "test_price_year": 0.1,
    "calc_limit": -1,
    "logistics_limit": 3,
    "description": "测试描述",
    "features": ["功能A", "功能B"],
    "sort_order": 99,
    "is_active": 1,
}

PLAN_DB_ROW = {
    "id": 999,
    "plan_code": "test_plan",
    "plan_name": "测试套餐",
    "display_price_month": 9.9,
    "display_price_year": 99,
    "actual_price_month": 9.9,
    "actual_price_year": 99,
    "test_price_month": 0.01,
    "test_price_year": 0.1,
    "calc_limit": -1,
    "logistics_limit": 3,
    "description": "测试描述",
    "features": "功能A,功能B",
    "is_active": 1,
    "sort_order": 99,
    "created_at": "2025-01-01",
    "updated_at": "2025-01-01",
}

UPDATED_PLAN_DB_ROW = {
    **PLAN_DB_ROW,
    "plan_name": "新名称",
    "features": "功能A,功能C",
    "is_active": 0,
}

_mock_session = _make_mock_session()


async def _override_get_db():
    yield _mock_session


app.dependency_overrides[dependencies.get_current_user_id] = _current_user_override
app.dependency_overrides[dependencies.require_admin] = _admin_override
app.dependency_overrides[get_db] = _override_get_db

client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _reset_overrides():
    global _mock_session
    _mock_session = _make_mock_session()
    app.dependency_overrides[dependencies.get_current_user_id] = _current_user_override
    app.dependency_overrides[dependencies.require_admin] = _admin_override
    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides[dependencies.get_current_user_id] = _current_user_override
    app.dependency_overrides[dependencies.require_admin] = _admin_override
    app.dependency_overrides[get_db] = _override_get_db


_ = _reset_overrides


class TestCreatePlan:
    @patch("api.routes.subscriptions.get_plan_by_id", new_callable=AsyncMock)
    @patch("api.routes.subscriptions.create_plan", new_callable=AsyncMock)
    def test_admin_creates_plan(self, mock_create, mock_get):
        mock_create.return_value = 999
        mock_get.return_value = PLAN_DB_ROW

        response = client.post("/api/subscriptions/plans", json=SAMPLE_PLAN)

        assert response.status_code == 201
        data = response.json()
        assert data["id"] == 999
        assert data["code"] == "test_plan"
        assert data["name"] == "测试套餐"
        assert data["features"] == ["功能A", "功能B"]
        mock_create.assert_awaited_once_with(
            _mock_session,
            {
                **SAMPLE_PLAN,
                "features": "功能A,功能B",
            },
        )
        mock_get.assert_awaited_once_with(_mock_session, 999)
        _mock_session.commit.assert_awaited_once_with()

    def test_non_admin_403(self):
        app.dependency_overrides[dependencies.require_admin] = _non_admin_override

        response = client.post("/api/subscriptions/plans", json=SAMPLE_PLAN)

        assert response.status_code == 403
        assert response.json()["detail"] == "需要管理员权限"


class TestUpdatePlan:
    @patch("api.routes.subscriptions.get_plan_by_id", new_callable=AsyncMock)
    @patch("api.routes.subscriptions.update_plan", new_callable=AsyncMock)
    def test_admin_updates_existing_plan(self, mock_update, mock_get):
        mock_update.return_value = True
        mock_get.return_value = UPDATED_PLAN_DB_ROW

        response = client.put(
            "/api/subscriptions/plans/999",
            json={"plan_name": "新名称", "features": ["功能A", "功能C"]},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 999
        assert data["name"] == "新名称"
        assert data["features"] == ["功能A", "功能C"]
        assert data["status"] is False
        mock_update.assert_awaited_once_with(
            _mock_session,
            999,
            {"plan_name": "新名称", "features": "功能A,功能C"},
        )
        mock_get.assert_awaited_once_with(_mock_session, 999)
        _mock_session.commit.assert_awaited_once_with()

    @patch("api.routes.subscriptions.update_plan", new_callable=AsyncMock)
    def test_admin_updates_non_existent_plan_returns_404(self, mock_update):
        mock_update.return_value = False

        response = client.put(
            "/api/subscriptions/plans/99999",
            json={"plan_name": "新名称"},
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "套餐不存在"
        _mock_session.commit.assert_not_awaited()

    def test_non_admin_403(self):
        app.dependency_overrides[dependencies.require_admin] = _non_admin_override

        response = client.put(
            "/api/subscriptions/plans/999",
            json={"plan_name": "新名称"},
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "需要管理员权限"


class TestDeletePlan:
    @patch("api.routes.subscriptions.delete_plan", new_callable=AsyncMock)
    def test_admin_deletes_existing_plan(self, mock_delete):
        mock_delete.return_value = True

        response = client.delete("/api/subscriptions/plans/999")

        assert response.status_code == 200
        assert response.json() == {"message": "套餐已删除"}
        mock_delete.assert_awaited_once_with(_mock_session, 999)
        _mock_session.commit.assert_awaited_once_with()

    @patch("api.routes.subscriptions.delete_plan", new_callable=AsyncMock)
    def test_admin_deletes_non_existent_plan_returns_404(self, mock_delete):
        mock_delete.return_value = False

        response = client.delete("/api/subscriptions/plans/99999")

        assert response.status_code == 404
        assert response.json()["detail"] == "套餐不存在"
        _mock_session.commit.assert_not_awaited()

    def test_non_admin_403(self):
        app.dependency_overrides[dependencies.require_admin] = _non_admin_override

        response = client.delete("/api/subscriptions/plans/999")

        assert response.status_code == 403
        assert response.json()["detail"] == "需要管理员权限"


class TestTogglePlan:
    @patch("api.routes.subscriptions.toggle_plan_active", new_callable=AsyncMock)
    def test_admin_toggles_existing_plan(self, mock_toggle):
        mock_toggle.return_value = 0

        response = client.patch("/api/subscriptions/plans/999/toggle")

        assert response.status_code == 200
        assert response.json() == {"is_active": False}
        mock_toggle.assert_awaited_once_with(_mock_session, 999)
        _mock_session.commit.assert_awaited_once_with()

    @patch("api.routes.subscriptions.toggle_plan_active", new_callable=AsyncMock)
    def test_admin_toggles_non_existent_plan_returns_404(self, mock_toggle):
        mock_toggle.return_value = None

        response = client.patch("/api/subscriptions/plans/99999/toggle")

        assert response.status_code == 404
        assert response.json()["detail"] == "套餐不存在"
        _mock_session.commit.assert_not_awaited()

    def test_non_admin_403(self):
        app.dependency_overrides[dependencies.require_admin] = _non_admin_override

        response = client.patch("/api/subscriptions/plans/999/toggle")

        assert response.status_code == 403
        assert response.json()["detail"] == "需要管理员权限"
