"""Tests for /api/subscriptions/trial/{claim,status} routes (Task 4.1)."""

import pytest

from api import dependencies
from api.main import app
from database import get_db
from models.user import User


def _override_user(user_id: int):
    return lambda: user_id


def _override_db(session):
    async def _get_db_override():
        yield session

    return _get_db_override


@pytest.mark.asyncio
async def test_trial_status_returns_eligible_for_free_user_without_trial(
    client, db_session, test_user
):
    user = await db_session.get(User, test_user["id"])
    user.subscription_type = "free"
    user.trial_used = 0
    user.trial_started_at = 0
    user.trial_expires_at = 0
    user.trial_plan_at_start = ""
    await db_session.commit()

    app.dependency_overrides[dependencies.get_current_user_id] = _override_user(
        test_user["id"]
    )
    app.dependency_overrides[get_db] = _override_db(db_session)
    try:
        resp = await client.get("/api/subscriptions/trial/status")
    finally:
        app.dependency_overrides.pop(dependencies.get_current_user_id, None)
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    body = resp.json()
    assert body["eligible"] is True
    assert body["in_trial"] is False
    assert body["trial_used"] is False
    assert body["remaining_seconds"] == 0


@pytest.mark.asyncio
async def test_trial_claim_then_status_shows_in_trial(
    client, db_session, test_user
):
    user = await db_session.get(User, test_user["id"])
    user.subscription_type = "free"
    user.trial_used = 0
    user.trial_started_at = 0
    user.trial_expires_at = 0
    user.trial_plan_at_start = ""
    await db_session.commit()

    app.dependency_overrides[dependencies.get_current_user_id] = _override_user(
        test_user["id"]
    )
    app.dependency_overrides[get_db] = _override_db(db_session)
    try:
        claim = await client.post("/api/subscriptions/trial/claim")
        assert claim.status_code == 200
        cj = claim.json()
        assert cj["status"] == "claimed"
        assert cj["trial_expires_at"] > cj["trial_started_at"] > 0

        await db_session.refresh(user)
        assert user.trial_used == 1

        status = await client.get("/api/subscriptions/trial/status")
    finally:
        app.dependency_overrides.pop(dependencies.get_current_user_id, None)
        app.dependency_overrides.pop(get_db, None)

    sj = status.json()
    assert sj["in_trial"] is True
    assert sj["trial_used"] is True
    assert sj["eligible"] is False
    assert sj["remaining_seconds"] > 0


@pytest.mark.asyncio
async def test_trial_claim_twice_returns_409_already_used(
    client, db_session, test_user
):
    user = await db_session.get(User, test_user["id"])
    user.subscription_type = "free"
    user.trial_used = 0
    await db_session.commit()

    app.dependency_overrides[dependencies.get_current_user_id] = _override_user(
        test_user["id"]
    )
    app.dependency_overrides[get_db] = _override_db(db_session)
    try:
        first = await client.post("/api/subscriptions/trial/claim")
        assert first.status_code == 200
        second = await client.post("/api/subscriptions/trial/claim")
    finally:
        app.dependency_overrides.pop(dependencies.get_current_user_id, None)
        app.dependency_overrides.pop(get_db, None)

    assert second.status_code == 409
    assert "试用已使用" in second.json()["detail"]


@pytest.mark.asyncio
async def test_trial_claim_on_pro_plan_returns_409_ineligible(
    client, db_session, test_user
):
    user = await db_session.get(User, test_user["id"])
    user.subscription_type = "professional"
    user.trial_used = 0
    await db_session.commit()

    app.dependency_overrides[dependencies.get_current_user_id] = _override_user(
        test_user["id"]
    )
    app.dependency_overrides[get_db] = _override_db(db_session)
    try:
        resp = await client.post("/api/subscriptions/trial/claim")
    finally:
        app.dependency_overrides.pop(dependencies.get_current_user_id, None)
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 409
    assert "不可领取" in resp.json()["detail"]
