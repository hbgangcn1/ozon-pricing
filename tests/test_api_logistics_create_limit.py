"""Tests for /api/logistics create-limit + list disabled_by_overflow (Task 4.3)."""

import time

import pytest

from api import dependencies
from api.main import app
from database import get_db
from models.logistics import Logistics
from models.user import User


def _override_user(user_id: int):
    return lambda: user_id


def _override_db(session):
    async def _get_db_override():
        yield session

    return _get_db_override


def _payload(name: str = "rule_x"):
    return {
        "name": name,
        "type": "land",
        "min_days": 5,
        "max_days": 30,
        "base_fee": 10.0,
        "min_weight": 0.0,
        "max_weight": 30.0,
        "max_sum_of_sides": 200,
        "max_longest_side": 100,
        "volume_mode": "longest_side",
        "longest_side_threshold": 60,
        "fee_mode": "first_continue",
        "first_fee": 10.0,
        "first_weight_g": 500,
        "continue_fee": 5.0,
        "continue_unit": "g",
        "fulfillment_type": "rfbs",
        "destination": "RU",
        "is_active": True,
    }


async def _seed_active_rules(db_session, user_id, count):
    ids = []
    for i in range(count):
        r = Logistics(
            user_id=user_id,
            name=f"seed_{i}",
            type="land",
            is_active=1,
            disabled_by_overflow=0,
        )
        db_session.add(r)
        await db_session.flush()
        ids.append(r.id)
    await db_session.commit()
    return ids


@pytest.mark.asyncio
async def test_create_blocked_when_at_efficiency_limit(
    client, db_session, test_user
):
    user = await db_session.get(User, test_user["id"])
    user.subscription_type = "efficiency"
    user.trial_expires_at = 0
    await db_session.commit()
    await _seed_active_rules(db_session, test_user["id"], 3)

    app.dependency_overrides[dependencies.get_current_user_id] = _override_user(
        test_user["id"]
    )
    app.dependency_overrides[get_db] = _override_db(db_session)
    try:
        resp = await client.post("/api/logistics", json=_payload())
    finally:
        app.dependency_overrides.pop(dependencies.get_current_user_id, None)
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 403
    assert "上限" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_create_allowed_during_trial_uses_pro_limit(
    client, db_session, test_user
):
    user = await db_session.get(User, test_user["id"])
    user.subscription_type = "efficiency"
    user.trial_used = 1
    user.trial_started_at = int(time.time()) - 100
    user.trial_expires_at = int(time.time()) + 7 * 24 * 3600
    user.trial_plan_at_start = "efficiency"
    await db_session.commit()
    await _seed_active_rules(db_session, test_user["id"], 5)

    app.dependency_overrides[dependencies.get_current_user_id] = _override_user(
        test_user["id"]
    )
    app.dependency_overrides[get_db] = _override_db(db_session)
    try:
        resp = await client.post("/api/logistics", json=_payload("trial_rule"))
    finally:
        app.dependency_overrides.pop(dependencies.get_current_user_id, None)
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 201, resp.text


@pytest.mark.asyncio
async def test_create_allowed_when_overflow_disabled_does_not_count(
    client, db_session, test_user
):
    user = await db_session.get(User, test_user["id"])
    user.subscription_type = "efficiency"
    user.trial_expires_at = 0
    await db_session.commit()
    ids = await _seed_active_rules(db_session, test_user["id"], 5)
    for rid in ids[3:]:
        rule = await db_session.get(Logistics, rid)
        rule.disabled_by_overflow = 1
    await db_session.commit()

    app.dependency_overrides[dependencies.get_current_user_id] = _override_user(
        test_user["id"]
    )
    app.dependency_overrides[get_db] = _override_db(db_session)
    try:
        resp = await client.post("/api/logistics", json=_payload("post_overflow"))
    finally:
        app.dependency_overrides.pop(dependencies.get_current_user_id, None)
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_response_includes_disabled_by_overflow_field(
    client, db_session, test_user
):
    ids = await _seed_active_rules(db_session, test_user["id"], 2)
    rule = await db_session.get(Logistics, ids[0])
    rule.disabled_by_overflow = 1
    await db_session.commit()

    app.dependency_overrides[dependencies.get_current_user_id] = _override_user(
        test_user["id"]
    )
    app.dependency_overrides[get_db] = _override_db(db_session)
    try:
        resp = await client.get("/api/logistics")
    finally:
        app.dependency_overrides.pop(dependencies.get_current_user_id, None)
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    body = resp.json()
    assert body["items"], "expected at least one item"
    for item in body["items"]:
        assert "disabled_by_overflow" in item
    by_id = {it["id"]: it for it in body["items"]}
    assert by_id[ids[0]]["disabled_by_overflow"] == 1
    assert by_id[ids[1]]["disabled_by_overflow"] == 0
