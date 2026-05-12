import asyncio

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from api import dependencies
from api.main import app
from database import AsyncSessionLocal, get_db
from models.logistics import Logistics
from models.user import User


def _override_user(user_id: int):
    return lambda: user_id


def _override_db(session):
    async def _get_db_override():
        yield session

    return _get_db_override


def _payload(name: str):
    return {
        "name": name,
        "type": "land",
        "min_days": 5,
        "max_days": 30,
        "base_fee": 10,
        "min_weight": 0,
        "max_weight": 30000,
        "max_sum_of_sides": 200,
        "max_longest_side": 100,
        "volume_mode": "longest_side",
        "longest_side_threshold": 60,
        "fee_mode": "first_continue",
        "first_fee": 10,
        "first_weight_g": 500,
        "continue_fee": 5,
        "continue_unit": "g",
        "fulfillment_type": "rfbs",
        "destination": "RU",
        "is_active": True,
    }


async def _seed_active_rules(db_session, user_id: int, count: int) -> None:
    for index in range(count):
        db_session.add(
            Logistics(
                user_id=user_id,
                name=f"seed_{user_id}_{index}",
                type="land",
                is_active=1,
                disabled_by_overflow=0,
            )
        )
    await db_session.commit()


async def _post_logistics(client, db_session, user_id: int, name: str):
    app.dependency_overrides[dependencies.get_current_user_id] = _override_user(
        user_id
    )
    app.dependency_overrides[get_db] = _override_db(db_session)
    try:
        return await client.post("/api/logistics", json=_payload(name))
    finally:
        app.dependency_overrides.pop(dependencies.get_current_user_id, None)
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_admin_can_create_logistics_beyond_free_limit(
    client,
    db_session,
    test_admin,
):
    admin = await db_session.get(User, test_admin["id"])
    admin.subscription_type = "free"
    admin.trial_expires_at = 0
    await db_session.commit()
    await _seed_active_rules(db_session, test_admin["id"], 1)

    response = await _post_logistics(
        client,
        db_session,
        test_admin["id"],
        "admin_over_free_limit",
    )

    assert response.status_code == 201, response.text
    assert response.json()["name"] == "admin_over_free_limit"


@pytest.mark.asyncio
async def test_free_user_cannot_create_logistics_beyond_free_limit(
    client,
    db_session,
    test_user,
):
    user = await db_session.get(User, test_user["id"])
    user.subscription_type = "free"
    user.trial_expires_at = 0
    await db_session.commit()
    await _seed_active_rules(db_session, test_user["id"], 1)

    response = await _post_logistics(
        client,
        db_session,
        test_user["id"],
        "free_over_limit",
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "已达到当前套餐物流规则上限（1）"


@pytest.mark.asyncio
async def test_concurrent_inserts_respect_plan_limit(db_session, test_user):
    """W8/W9 fix: pg_advisory_xact_lock serializes per-user limit checks.

    Without the lock, N concurrent POSTs all observe count<limit and insert,
    exceeding the plan cap. With the lock, exactly `limit` requests succeed.
    """
    user_id = test_user["id"]
    user = await db_session.get(User, user_id)
    user.subscription_type = "free"
    user.trial_expires_at = 0
    await db_session.commit()
    await db_session.rollback()

    async def _independent_get_db():
        async with AsyncSessionLocal() as s:
            try:
                yield s
                await s.commit()
            except Exception:
                await s.rollback()
                raise

    app.dependency_overrides[dependencies.get_current_user_id] = _override_user(
        user_id
    )
    app.dependency_overrides[get_db] = _independent_get_db

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            tasks = [
                ac.post("/api/logistics", json=_payload(f"concurrent_{i}"))
                for i in range(3)
            ]
            responses = await asyncio.gather(*tasks)
    finally:
        app.dependency_overrides.pop(dependencies.get_current_user_id, None)
        app.dependency_overrides.pop(get_db, None)

    statuses = sorted(r.status_code for r in responses)
    success_count = sum(1 for r in responses if r.status_code == 201)
    forbidden_count = sum(1 for r in responses if r.status_code == 403)
    assert success_count == 1, f"expected 1 success, got statuses={statuses}"
    assert forbidden_count == 2, f"expected 2 forbidden, got statuses={statuses}"

    async with AsyncSessionLocal() as verify:
        row_count = (
            await verify.execute(
                select(func.count())
                .select_from(Logistics)
                .where(Logistics.user_id == user_id)
            )
        ).scalar_one()
    assert row_count == 1, (
        f"DB row count {row_count} exceeds plan limit 1 — advisory lock failed"
    )
