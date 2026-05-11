import pytest
from unittest.mock import AsyncMock, patch

from api import dependencies
from api.main import app
from database import get_db


def _override_user(user_id: int):
    return lambda: user_id


def _override_db(session):
    async def _get_db_override():
        yield session

    return _get_db_override


@pytest.mark.asyncio
async def test_plans_returns_empty_list_on_backend_error(client):
    with patch(
        "api.routes.subscriptions.is_registration_open",
        side_effect=RuntimeError("boom"),
    ):
        resp = await client.get("/api/subscriptions/plans")

    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_current_returns_404_when_user_subscription_missing(client, test_user):
    app.dependency_overrides[dependencies.get_current_user_id] = _override_user(
        test_user["id"]
    )
    app.dependency_overrides[get_db] = _override_db(object())
    with patch(
        "api.routes.subscriptions.get_user_subscription_info",
        new=AsyncMock(return_value=None),
    ):
        try:
            resp = await client.get("/api/subscriptions/current")
        finally:
            app.dependency_overrides.pop(dependencies.get_current_user_id, None)
            app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 404
    assert resp.json()["detail"] == "用户不存在"


@pytest.mark.asyncio
async def test_current_falls_back_to_free_when_plan_missing(client, test_user):
    app.dependency_overrides[dependencies.get_current_user_id] = _override_user(
        test_user["id"]
    )

    class _Session:
        pass

    app.dependency_overrides[get_db] = _override_db(_Session())
    with patch(
        "api.routes.subscriptions.get_user_subscription_info",
        new=AsyncMock(return_value={"user_type": "enterprise"}),
    ), patch(
        "api.routes.subscriptions.get_plan_by_code",
        new=AsyncMock(side_effect=[None, {"calc_limit": -1, "logistics_limit": 1}]),
    ):
        try:
            resp = await client.get("/api/subscriptions/current")
        finally:
            app.dependency_overrides.pop(dependencies.get_current_user_id, None)
            app.dependency_overrides.pop(get_db, None)

    data = resp.json()
    assert resp.status_code == 200
    assert data["plan_code"] == "free"
    assert data["calc_limit"] == -1
    assert data["logistics_limit"] == 1
