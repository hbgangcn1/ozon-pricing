import os
import time

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from api import dependencies
from api.main import app
from database import AsyncSessionLocal, get_db
from models.user import User


def _override_user(user_id: int):
    return lambda: user_id


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


async def _independent_get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def _post_logistics(user_id: int, name: str):
    app.dependency_overrides[dependencies.get_current_user_id] = _override_user(
        user_id
    )
    app.dependency_overrides[get_db] = _independent_get_db
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            return await ac.post("/api/logistics", json=_payload(name))
    finally:
        app.dependency_overrides.pop(dependencies.get_current_user_id, None)
        app.dependency_overrides.pop(get_db, None)


async def _create_high_id_user(db_session) -> int:
    worker = os.environ.get("PYTEST_XDIST_WORKER", "gw0")
    suffix = int("".join(ch for ch in worker if ch.isdigit()) or "0")
    user_id = 900000 + suffix
    db_session.add(
        User(
            id=user_id,
            username=f"test_lock_timeout_{worker}_{os.getpid()}",
            password="unused",
            role="user",
            user_type="permanent",
            subscription_type="pro",
            remaining_calculations=-1,
            created_at="2026-05-12 00:00:00",
            is_test_user=1,
        )
    )
    await db_session.commit()
    return user_id


@pytest.mark.asyncio
async def test_logistics_advisory_lock_normal_case_succeeds(db_session, test_user):
    _ = test_user
    user_id = await _create_high_id_user(db_session)

    response = await _post_logistics(user_id, "lock_timeout_normal")

    assert response.status_code == 201, response.text
    assert response.json()["name"] == "lock_timeout_normal"


@pytest.mark.asyncio
async def test_logistics_lock_contention_returns_503_within_timeout(
    db_session,
    test_user,
):
    _ = test_user
    user_id = await _create_high_id_user(db_session)

    async with AsyncSessionLocal() as lock_holder:
        await lock_holder.execute(
            text("SELECT pg_advisory_xact_lock(:lock_key)"),
            {"lock_key": user_id},
        )

        started = time.monotonic()
        response = await _post_logistics(user_id, "lock_timeout_contention")
        elapsed = time.monotonic() - started

        assert response.status_code == 503, response.text
        assert response.json()["detail"] == "资源繁忙，请稍后重试"
        assert elapsed < 6.5
