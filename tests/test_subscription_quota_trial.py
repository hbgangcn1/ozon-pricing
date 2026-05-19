"""Trial-aware calculation quota tests (TDD red phase).

These tests verify that users in an active 7-day professional trial are
treated as "professional" for calculation limits, while expired trials fall
back to the original plan limits.
"""
import time

import pytest
from sqlalchemy import select

from db.subscription_quota import (
    decrement_user_calculations,
    reset_user_daily_calculations,
)
from models.user import User


async def _set_user_trial_state(
    session,
    user_id,
    *,
    subscription_type="free",
    remaining_calculations=0,
    trial_expires_at=0,
    trial_started_at=0,
    trial_used=0,
    last_calculations_reset_date="2020-01-01",
):
    user = await session.get(User, user_id)
    user.subscription_type = subscription_type
    user.remaining_calculations = remaining_calculations
    user.trial_expires_at = trial_expires_at
    user.trial_started_at = trial_started_at
    user.trial_used = trial_used
    user.last_calculations_reset_date = last_calculations_reset_date
    await session.commit()
    session.expire_all()


@pytest.mark.asyncio
async def test_trial_active_decrement_returns_true(db_session, test_user):
    uid = test_user["id"]
    now = int(time.time())
    await _set_user_trial_state(
        db_session,
        uid,
        subscription_type="free",
        remaining_calculations=0,
        trial_expires_at=now + 3600,
        trial_started_at=now - 3600,
        trial_used=1,
    )

    ok = await decrement_user_calculations(db_session, uid)
    await db_session.commit()

    assert ok is True
    fresh = await db_session.execute(
        select(User.remaining_calculations).where(User.id == uid)
    )
    assert fresh.scalar_one() == 0


@pytest.mark.asyncio
async def test_trial_expired_decrement_returns_false(db_session, test_user):
    uid = test_user["id"]
    now = int(time.time())
    await _set_user_trial_state(
        db_session,
        uid,
        subscription_type="free",
        remaining_calculations=0,
        trial_expires_at=now - 3600,
        trial_started_at=now - 86400 * 8,
        trial_used=1,
    )

    ok = await decrement_user_calculations(db_session, uid)
    await db_session.commit()

    assert ok is False


@pytest.mark.asyncio
async def test_real_professional_decrement_returns_true(db_session, test_user):
    uid = test_user["id"]
    await _set_user_trial_state(
        db_session,
        uid,
        subscription_type="professional",
        remaining_calculations=0,
        trial_expires_at=0,
        trial_started_at=0,
        trial_used=0,
    )

    ok = await decrement_user_calculations(db_session, uid)
    await db_session.commit()

    assert ok is True
    fresh = await db_session.execute(
        select(User.remaining_calculations).where(User.id == uid)
    )
    assert fresh.scalar_one() == 0


@pytest.mark.asyncio
async def test_trial_active_reset_skipped(db_session, test_user):
    uid = test_user["id"]
    now = int(time.time())
    await _set_user_trial_state(
        db_session,
        uid,
        subscription_type="free",
        remaining_calculations=3,
        trial_expires_at=now + 3600,
        trial_started_at=now - 3600,
        trial_used=1,
        last_calculations_reset_date="2020-01-01",
    )

    ok = await reset_user_daily_calculations(db_session, uid)

    assert ok is False
    fresh = await db_session.execute(
        select(User.remaining_calculations).where(User.id == uid)
    )
    assert fresh.scalar_one() == 3


@pytest.mark.asyncio
async def test_trial_expired_reset_applies(db_session, test_user):
    from tests.test_db_subscription_quota import _seed_plan

    await _seed_plan(db_session, "free", 10)
    uid = test_user["id"]
    now = int(time.time())
    await _set_user_trial_state(
        db_session,
        uid,
        subscription_type="free",
        remaining_calculations=0,
        trial_expires_at=now - 3600,
        trial_started_at=now - 86400 * 8,
        trial_used=1,
        last_calculations_reset_date="2020-01-01",
    )

    ok = await reset_user_daily_calculations(db_session, uid)

    assert ok is True
    fresh = await db_session.execute(
        select(User.remaining_calculations).where(User.id == uid)
    )
    assert fresh.scalar_one() == 10
