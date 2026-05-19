"""Quota matrix invariants for db.subscription_quota.

Guards against accidental regressions to the unlimited-plan whitelist,
the atomic decrement floor for free/monthly users, and the daily reset
behaviour that powers the cron jobs.
"""
import pytest
from sqlalchemy import select, text

from db.subscription_quota import (
    decrement_user_calculations,
    reset_free_users_daily_calculations,
    reset_user_daily_calculations,
)
from models.user import Plan, User


UNLIMITED_PLANS = [
    "permanent",
    "enterprise",
    "gratitude",
    "efficiency",
    "professional",
    "test",
]


async def _seed_plan(session, plan_code, calc_limit):
    existing = await session.execute(
        select(Plan).where(Plan.plan_code == plan_code)
    )
    if existing.scalar_one_or_none() is not None:
        return
    session.add(Plan(
        plan_code=plan_code,
        plan_name=plan_code,
        display_price_month=0.0,
        display_price_year=0.0,
        actual_price_month=0.0,
        actual_price_year=0.0,
        test_price_month=0.0,
        test_price_year=0.0,
        calc_limit=calc_limit,
        logistics_limit=1,
        is_active=1,
        sort_order=0,
    ))
    await session.commit()


async def _set_user(session, user_id, *, role=None, user_type=None,
                    subscription_type=None, remaining=None):
    user = await session.get(User, user_id)
    if role is not None:
        user.role = role
    if user_type is not None:
        user.user_type = user_type
    if subscription_type is not None:
        user.subscription_type = subscription_type
    if remaining is not None:
        user.remaining_calculations = remaining
    await session.commit()


@pytest.mark.asyncio
async def test_admin_role_never_decrements(db_session, test_admin):
    uid = test_admin["id"]
    await _set_user(db_session, uid, role="admin", remaining=5)

    ok = await decrement_user_calculations(db_session, uid)
    await db_session.commit()

    assert ok is True
    user = await db_session.get(User, uid)
    assert user.remaining_calculations == 5


@pytest.mark.parametrize("plan", UNLIMITED_PLANS)
@pytest.mark.asyncio
async def test_unlimited_plans_never_decrement(db_session, test_user, plan):
    uid = test_user["id"]
    await _set_user(db_session, uid, role="user", subscription_type=plan,
                    remaining=3)

    ok = await decrement_user_calculations(db_session, uid)
    await db_session.commit()

    assert ok is True
    user = await db_session.get(User, uid)
    assert user.remaining_calculations == 3


@pytest.mark.asyncio
async def test_free_decrements_when_above_zero(db_session, test_user):
    uid = test_user["id"]
    await _set_user(db_session, uid, role="user", subscription_type="free",
                    remaining=2)

    ok = await decrement_user_calculations(db_session, uid)
    await db_session.commit()

    assert ok is True
    fresh = await db_session.execute(
        select(User.remaining_calculations).where(User.id == uid)
    )
    assert fresh.scalar_one() == 1


@pytest.mark.asyncio
async def test_free_returns_false_when_at_zero(db_session, test_user):
    uid = test_user["id"]
    await _set_user(db_session, uid, role="user", subscription_type="free",
                    remaining=0)

    ok = await decrement_user_calculations(db_session, uid)
    await db_session.commit()

    assert ok is False
    user = await db_session.get(User, uid)
    assert user.remaining_calculations == 0


@pytest.mark.asyncio
async def test_monthly_decrements_when_above_zero(db_session, test_user):
    uid = test_user["id"]
    await _set_user(db_session, uid, role="user", subscription_type="monthly",
                    remaining=10)

    ok = await decrement_user_calculations(db_session, uid)
    await db_session.commit()

    assert ok is True
    fresh = await db_session.execute(
        select(User.remaining_calculations).where(User.id == uid)
    )
    assert fresh.scalar_one() == 9


@pytest.mark.asyncio
async def test_monthly_returns_false_when_at_zero(db_session, test_user):
    uid = test_user["id"]
    await _set_user(db_session, uid, role="user", subscription_type="monthly",
                    remaining=0)

    ok = await decrement_user_calculations(db_session, uid)
    await db_session.commit()

    assert ok is False


@pytest.mark.asyncio
async def test_unknown_user_returns_false(db_session):
    ok = await decrement_user_calculations(db_session, 999_999_999)
    assert ok is False


@pytest.mark.asyncio
async def test_unknown_user_type_fallback_to_free(db_session, test_user):
    uid = test_user["id"]
    await _set_user(db_session, uid, role="user",
                    subscription_type="some_unknown_plan", remaining=5)

    ok = await decrement_user_calculations(db_session, uid)
    await db_session.commit()

    assert ok is True
    fresh = await db_session.execute(
        select(User.remaining_calculations).where(User.id == uid)
    )
    assert fresh.scalar_one() == 4


@pytest.mark.asyncio
async def test_reset_free_users_daily_only_targets_free(
    db_session, test_user, test_admin
):
    free_uid = test_user["id"]
    other_uid = test_admin["id"]
    await _set_user(db_session, free_uid, user_type="free", remaining=0)
    await _set_user(db_session, other_uid, user_type="professional",
                    remaining=2)

    count = await reset_free_users_daily_calculations(db_session)
    await db_session.commit()

    assert count >= 1
    free_user = await db_session.get(User, free_uid)
    other_user = await db_session.get(User, other_uid)
    assert free_user.remaining_calculations == 10
    assert other_user.remaining_calculations == 2


@pytest.mark.asyncio
async def test_reset_user_daily_skips_unlimited_plan(db_session, test_user):
    await _seed_plan(db_session, "enterprise", -1)
    uid = test_user["id"]
    await _set_user(db_session, uid, subscription_type="enterprise",
                    remaining=42)

    ok = await reset_user_daily_calculations(db_session, uid)

    assert ok is False
    user = await db_session.get(User, uid)
    assert user.remaining_calculations == 42


@pytest.mark.asyncio
async def test_reset_user_daily_skips_when_already_reset_today(
    db_session, test_user
):
    from datetime import date

    await _seed_plan(db_session, "free", 10)
    uid = test_user["id"]
    user = await db_session.get(User, uid)
    user.subscription_type = "free"
    user.remaining_calculations = 5
    user.last_calculations_reset_date = date.today().isoformat()
    await db_session.commit()
    db_session.expire_all()

    ok = await reset_user_daily_calculations(db_session, uid)

    assert ok is False
    fresh = await db_session.execute(
        select(User.remaining_calculations).where(User.id == uid)
    )
    assert fresh.scalar_one() == 5


@pytest.mark.asyncio
async def test_reset_user_daily_resets_free_user_first_time_today(
    db_session, test_user
):
    await _seed_plan(db_session, "free", 10)
    uid = test_user["id"]
    user = await db_session.get(User, uid)
    user.subscription_type = "free"
    user.remaining_calculations = 0
    user.last_calculations_reset_date = "2020-01-01"
    await db_session.commit()

    ok = await reset_user_daily_calculations(db_session, uid)

    assert ok is True
    fresh = await db_session.execute(
        select(User.remaining_calculations).where(User.id == uid)
    )
    assert fresh.scalar_one() == 10


@pytest.mark.asyncio
async def test_reset_user_daily_flushes_without_commit(db_session, test_user):
    await _seed_plan(db_session, "free", 10)
    uid = test_user["id"]
    await db_session.execute(
        text(
            """
            UPDATE users
            SET subscription_type = 'free',
                remaining_calculations = 0,
                last_calculations_reset_date = '2020-01-01'
            WHERE id = :uid
            """
        ),
        {"uid": uid},
    )
    await db_session.commit()
    # Raw SQL bypasses ORM identity map; expire so the function re-reads from DB.
    db_session.expire_all()

    ok = await reset_user_daily_calculations(db_session, uid)

    assert ok is True
    in_txn_value = (
        await db_session.execute(
            select(User.remaining_calculations).where(User.id == uid)
        )
    ).scalar_one()
    assert in_txn_value == 10
    await db_session.rollback()
    rolled_back = (
        await db_session.execute(
            select(User.remaining_calculations).where(User.id == uid)
        )
    ).scalar_one()
    assert rolled_back == 0
