from datetime import datetime, timezone

import pytest

from db.subscriptions import apply_paid_subscription
from models.user import User


def _epoch(dt: datetime) -> int:
    return int(dt.timestamp())


async def _set_subscription(session, user_id, plan, expires_at):
    user = await session.get(User, user_id)
    user.subscription_type = plan
    user.user_type = plan
    user.subscription_expires = expires_at
    await session.commit()


@pytest.mark.asyncio
async def test_early_renewal_preserves_remaining_days(db_session, test_user):
    now = datetime.now(timezone.utc)
    current_expires = _epoch(now) + 5 * 86400
    await _set_subscription(
        db_session, test_user["id"], "professional", current_expires,
    )

    await apply_paid_subscription(
        db_session,
        test_user["id"],
        "professional",
        subscription_expires=_epoch(now) + 30 * 86400,
        started_at=_epoch(now),
        source="w12r2_early_renewal",
    )
    await db_session.commit()

    user = await db_session.get(User, test_user["id"])
    assert user.subscription_expires == current_expires + 30 * 86400


@pytest.mark.asyncio
async def test_expired_paid_renewal_starts_from_now(db_session, test_user):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    expired_at = _epoch(now) - 3 * 86400
    await _set_subscription(
        db_session, test_user["id"], "professional", expired_at,
    )

    await apply_paid_subscription(
        db_session,
        test_user["id"],
        "professional",
        subscription_expires=_epoch(now) + 30 * 86400,
        started_at=_epoch(now),
        source="w12r2_expired_renewal",
    )
    await db_session.commit()

    user = await db_session.get(User, test_user["id"])
    assert user.subscription_expires == _epoch(now) + 30 * 86400


@pytest.mark.asyncio
async def test_free_user_first_purchase_starts_from_now(db_session, test_user):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    await _set_subscription(db_session, test_user["id"], "free", None)

    await apply_paid_subscription(
        db_session,
        test_user["id"],
        "efficiency",
        subscription_expires=_epoch(now) + 30 * 86400,
        started_at=_epoch(now),
        source="w12r2_first_purchase",
    )
    await db_session.commit()

    user = await db_session.get(User, test_user["id"])
    assert user.subscription_expires == _epoch(now) + 30 * 86400
