"""Tests for /api/logistics/overflow/{reselect,status} routes (Task 4.2)."""

import time

import pytest
from sqlalchemy import select

from api import dependencies
from api.main import app
from database import get_db
from models.logistics import Logistics
from models.trial_overflow_window import TrialOverflowWindow
from models.user import User


def _override_user(user_id: int):
    return lambda: user_id


def _override_db(session):
    async def _get_db_override():
        yield session

    return _get_db_override


async def _seed_rules(db_session, user_id: int, count: int):
    ids = []
    for i in range(count):
        rule = Logistics(
            user_id=user_id,
            name=f"rule_{i}",
            type="land",
            is_active=1,
            disabled_by_overflow=0,
            last_used_at=1000 + i,
        )
        db_session.add(rule)
        await db_session.flush()
        ids.append(rule.id)
    await db_session.commit()
    return ids


async def _open_window(db_session, user_id: int):
    now = int(time.time())
    win = TrialOverflowWindow(
        user_id=user_id,
        opened_at=now,
        expires_at=now + 48 * 3600,
        closed_at=0,
        close_reason="",
    )
    db_session.add(win)
    await db_session.commit()
    return win


async def _disable_rules(db_session, ids):
    for rid in ids:
        rule = await db_session.get(Logistics, rid)
        rule.disabled_by_overflow = 1
    await db_session.commit()


@pytest.mark.asyncio
async def test_overflow_status_no_window_returns_zeros(
    client, db_session, test_user
):
    user = await db_session.get(User, test_user["id"])
    user.subscription_type = "efficiency"
    await db_session.commit()

    app.dependency_overrides[dependencies.get_current_user_id] = _override_user(
        test_user["id"]
    )
    app.dependency_overrides[get_db] = _override_db(db_session)
    try:
        resp = await client.get("/api/logistics/overflow/status")
    finally:
        app.dependency_overrides.pop(dependencies.get_current_user_id, None)
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    body = resp.json()
    assert body["has_open_window"] is False
    assert body["expires_at"] == 0
    assert body["current_disabled_count"] == 0
    assert body["new_limit"] == 3


@pytest.mark.asyncio
async def test_overflow_reselect_happy_path_closes_window(
    client, db_session, test_user
):
    user = await db_session.get(User, test_user["id"])
    user.subscription_type = "efficiency"
    await db_session.commit()

    rule_ids = await _seed_rules(db_session, test_user["id"], 5)
    await _disable_rules(db_session, rule_ids[3:])
    win = await _open_window(db_session, test_user["id"])
    keep = rule_ids[:3]

    app.dependency_overrides[dependencies.get_current_user_id] = _override_user(
        test_user["id"]
    )
    app.dependency_overrides[get_db] = _override_db(db_session)
    try:
        resp = await client.post(
            "/api/logistics/overflow/reselect",
            json={"keep_ids": keep},
        )
    finally:
        app.dependency_overrides.pop(dependencies.get_current_user_id, None)
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    body = resp.json()
    assert sorted(body["enabled_ids"]) == sorted(keep)
    assert sorted(body["disabled_ids"]) == sorted(rule_ids[3:])

    await db_session.refresh(win)
    assert win.closed_at > 0
    assert win.close_reason == "reselected"

    rules = (
        await db_session.execute(
            select(Logistics).where(Logistics.id.in_(rule_ids))
        )
    ).scalars().all()
    by_id = {r.id: r for r in rules}
    for rid in keep:
        assert by_id[rid].disabled_by_overflow == 0
    for rid in rule_ids[3:]:
        assert by_id[rid].disabled_by_overflow == 1


@pytest.mark.asyncio
async def test_overflow_reselect_exceeds_limit_returns_422(
    client, db_session, test_user
):
    user = await db_session.get(User, test_user["id"])
    user.subscription_type = "efficiency"
    await db_session.commit()

    rule_ids = await _seed_rules(db_session, test_user["id"], 5)
    await _open_window(db_session, test_user["id"])

    app.dependency_overrides[dependencies.get_current_user_id] = _override_user(
        test_user["id"]
    )
    app.dependency_overrides[get_db] = _override_db(db_session)
    try:
        resp = await client.post(
            "/api/logistics/overflow/reselect",
            json={"keep_ids": rule_ids[:5]},
        )
    finally:
        app.dependency_overrides.pop(dependencies.get_current_user_id, None)
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 422
    assert "超过" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_overflow_reselect_foreign_id_returns_403(
    client, db_session, test_user
):
    user = await db_session.get(User, test_user["id"])
    user.subscription_type = "efficiency"
    await db_session.commit()

    rule_ids = await _seed_rules(db_session, test_user["id"], 2)
    await _open_window(db_session, test_user["id"])
    bogus_id = max(rule_ids) + 99999

    app.dependency_overrides[dependencies.get_current_user_id] = _override_user(
        test_user["id"]
    )
    app.dependency_overrides[get_db] = _override_db(db_session)
    try:
        resp = await client.post(
            "/api/logistics/overflow/reselect",
            json={"keep_ids": [rule_ids[0], bogus_id]},
        )
    finally:
        app.dependency_overrides.pop(dependencies.get_current_user_id, None)
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_overflow_reselect_no_open_window_returns_409(
    client, db_session, test_user
):
    user = await db_session.get(User, test_user["id"])
    user.subscription_type = "efficiency"
    await db_session.commit()

    rule_ids = await _seed_rules(db_session, test_user["id"], 2)

    app.dependency_overrides[dependencies.get_current_user_id] = _override_user(
        test_user["id"]
    )
    app.dependency_overrides[get_db] = _override_db(db_session)
    try:
        resp = await client.post(
            "/api/logistics/overflow/reselect",
            json={"keep_ids": [rule_ids[0]]},
        )
    finally:
        app.dependency_overrides.pop(dependencies.get_current_user_id, None)
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_overflow_reselect_twice_second_returns_409(
    client, db_session, test_user
):
    user = await db_session.get(User, test_user["id"])
    user.subscription_type = "efficiency"
    await db_session.commit()

    rule_ids = await _seed_rules(db_session, test_user["id"], 5)
    await _disable_rules(db_session, rule_ids[3:])
    await _open_window(db_session, test_user["id"])
    keep = rule_ids[:3]

    app.dependency_overrides[dependencies.get_current_user_id] = _override_user(
        test_user["id"]
    )
    app.dependency_overrides[get_db] = _override_db(db_session)
    try:
        first = await client.post(
            "/api/logistics/overflow/reselect",
            json={"keep_ids": keep},
        )
        second = await client.post(
            "/api/logistics/overflow/reselect",
            json={"keep_ids": keep},
        )
    finally:
        app.dependency_overrides.pop(dependencies.get_current_user_id, None)
        app.dependency_overrides.pop(get_db, None)

    assert first.status_code == 200
    assert second.status_code == 409
