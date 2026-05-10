"""Tests for services.trial_service.

QA spec (task 2.2): cover
  - claim happy path: free user -> claimed, user row updated
  - re-claim same user -> already_used
  - professional user -> ineligible_plan
  - non-existent user -> user_not_found
  - concurrent two claims -> exactly one claimed (race safety)
  - get_trial_status branches (eligible / in_trial / used / expired)
"""
import asyncio
import time

import pytest
from sqlalchemy import text

from database import AsyncSessionLocal
from services.trial_service import (
    ELIGIBLE_PLANS_FOR_TRIAL,
    TRIAL_DURATION_SECONDS,
    claim_trial,
    get_trial_status,
)


async def _set_subscription(session, user_id, sub_type):
    await session.execute(
        text("UPDATE users SET subscription_type = :st WHERE id = :uid"),
        {"st": sub_type, "uid": user_id},
    )
    await session.commit()
    session.expire_all()


async def _read_user_trial(session, user_id):
    row = (
        await session.execute(
            text(
                "SELECT trial_used, trial_started_at, trial_expires_at,"
                " trial_plan_at_start FROM users WHERE id = :uid"
            ),
            {"uid": user_id},
        )
    ).fetchone()
    return row


@pytest.mark.asyncio
async def test_claim_trial_happy_path(db_session, test_user):
    uid = test_user["id"]
    # test_user fixture creates subscription_type='free', trial_used default 0
    result = await claim_trial(db_session, uid)
    assert result.status == "claimed"
    assert result.trial_started_at > 0
    assert result.trial_expires_at == result.trial_started_at + TRIAL_DURATION_SECONDS

    # Verify DB state via fresh session (claim_trial committed)
    async with AsyncSessionLocal() as s:
        row = await _read_user_trial(s, uid)
    assert row is not None
    assert row[0] == 1  # trial_used
    assert row[1] == result.trial_started_at
    assert row[2] == result.trial_expires_at
    assert row[3] == "free"  # trial_plan_at_start


@pytest.mark.asyncio
async def test_claim_trial_already_used_on_second_call(db_session, test_user):
    uid = test_user["id"]
    first = await claim_trial(db_session, uid)
    assert first.status == "claimed"

    second = await claim_trial(db_session, uid)
    assert second.status == "already_used"


@pytest.mark.asyncio
async def test_claim_trial_ineligible_plan(db_session, test_user):
    uid = test_user["id"]
    await _set_subscription(db_session, uid, "professional")

    result = await claim_trial(db_session, uid)
    assert result.status == "ineligible_plan"

    async with AsyncSessionLocal() as s:
        row = await _read_user_trial(s, uid)
    assert row[0] == 0  # trial_used unchanged


@pytest.mark.asyncio
async def test_claim_trial_user_not_found(db_session):
    result = await claim_trial(db_session, 999_999_999)
    assert result.status == "user_not_found"


@pytest.mark.asyncio
async def test_claim_trial_efficiency_plan_is_eligible(db_session, test_user):
    uid = test_user["id"]
    await _set_subscription(db_session, uid, "efficiency")

    result = await claim_trial(db_session, uid)
    assert result.status == "claimed"

    async with AsyncSessionLocal() as s:
        row = await _read_user_trial(s, uid)
    assert row[3] == "efficiency"  # trial_plan_at_start preserved


@pytest.mark.asyncio
async def test_claim_trial_concurrent_exactly_one_winner(test_user):
    """Race: 5 concurrent claims; conditional UPDATE ensures only one wins."""
    uid = test_user["id"]

    async def _one_claim():
        async with AsyncSessionLocal() as s:
            return await claim_trial(s, uid)

    results = await asyncio.gather(*[_one_claim() for _ in range(5)])
    statuses = [r.status for r in results]
    claimed = [s for s in statuses if s == "claimed"]
    already = [s for s in statuses if s == "already_used"]
    assert len(claimed) == 1, f"expected exactly 1 winner, got {statuses}"
    assert len(already) == 4, f"expected 4 losers, got {statuses}"


# --- get_trial_status branches ---

class _U:
    def __init__(
        self,
        subscription_type="free",
        trial_used=0,
        trial_started_at=0,
        trial_expires_at=0,
        role=None,
    ):
        self.subscription_type = subscription_type
        self.trial_used = trial_used
        self.trial_started_at = trial_started_at
        self.trial_expires_at = trial_expires_at
        self.role = role


def test_get_trial_status_eligible_never_claimed():
    u = _U(subscription_type="free", trial_used=0)
    s = get_trial_status(u)
    assert s.eligible is True
    assert s.in_trial is False
    assert s.trial_used is False
    assert s.remaining_seconds == 0


def test_get_trial_status_in_trial_active():
    expires = int(time.time()) + 3600
    u = _U(
        subscription_type="free",
        trial_used=1,
        trial_started_at=int(time.time()) - 100,
        trial_expires_at=expires,
    )
    s = get_trial_status(u)
    assert s.in_trial is True
    assert s.trial_used is True
    assert s.eligible is False  # trial_used=1 disqualifies
    assert 0 < s.remaining_seconds <= 3600
    assert s.trial_expires_at == expires


def test_get_trial_status_expired_trial():
    u = _U(
        subscription_type="free",
        trial_used=1,
        trial_started_at=int(time.time()) - 10 * 24 * 3600,
        trial_expires_at=int(time.time()) - 3600,
    )
    s = get_trial_status(u)
    assert s.in_trial is False
    assert s.trial_used is True
    assert s.eligible is False
    assert s.remaining_seconds == 0


def test_get_trial_status_ineligible_plan_even_if_unused():
    u = _U(subscription_type="professional", trial_used=0)
    s = get_trial_status(u)
    assert s.eligible is False  # plan not in ELIGIBLE_PLANS_FOR_TRIAL
    assert s.in_trial is False


def test_eligible_plans_constant_unchanged():
    """Sentinel: tests below assume free+efficiency are the only eligible plans."""
    assert ELIGIBLE_PLANS_FOR_TRIAL == ("free", "efficiency")


def test_get_trial_status_admin_role_short_circuits_to_inert():
    now = int(time.time())
    u = _U(
        role="admin",
        subscription_type="free",
        trial_used=1,
        trial_started_at=now - 3600,
        trial_expires_at=now + 7 * 86400,
    )
    s = get_trial_status(u)
    assert s.eligible is False
    assert s.in_trial is False
    assert s.trial_used is False
    assert s.remaining_seconds == 0
    assert s.trial_expires_at == 0
    assert s.trial_started_at == 0


def test_get_trial_status_admin_role_case_insensitive():
    u = _U(role="ADMIN", subscription_type="free", trial_used=0)
    s = get_trial_status(u)
    assert s.eligible is False
    assert s.in_trial is False
