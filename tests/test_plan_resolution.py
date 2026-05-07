"""Tests for services.plan_resolution.

QA spec (task 2.1): at least 3 tests passing covering:
  - in_trial user -> professional regardless of subscription_type
  - trial expired -> falls back to subscription_type (trial_plan_at_start)
  - professional user (no trial) -> professional
Plus count_user_active_rules excluding disabled_by_overflow.
"""
import time

import pytest

from services.plan_resolution import (
    count_user_active_rules,
    get_effective_logistics_limit,
    get_effective_plan,
    is_in_trial,
)


class _U:
    def __init__(self, subscription_type="free", trial_expires_at=0):
        self.subscription_type = subscription_type
        self.trial_expires_at = trial_expires_at


def test_in_trial_user_resolves_to_professional():
    u = _U(subscription_type="free", trial_expires_at=int(time.time()) + 3600)
    assert is_in_trial(u) is True
    assert get_effective_plan(u) == "professional"


def test_trial_expired_falls_back_to_subscription_type():
    u = _U(subscription_type="efficiency", trial_expires_at=int(time.time()) - 3600)
    assert is_in_trial(u) is False
    assert get_effective_plan(u) == "efficiency"


def test_no_trial_returns_subscription_type():
    u = _U(subscription_type="professional", trial_expires_at=0)
    assert is_in_trial(u) is False
    assert get_effective_plan(u) == "professional"


def test_no_trial_unset_user_defaults_free():
    u = _U(subscription_type=None, trial_expires_at=0)
    assert get_effective_plan(u) == "free"


@pytest.mark.asyncio
async def test_get_effective_logistics_limit_uses_plans_table(db_session):
    u = _U(subscription_type="professional", trial_expires_at=0)
    limit = await get_effective_logistics_limit(db_session, u)
    assert limit == 10


@pytest.mark.asyncio
async def test_get_effective_logistics_limit_trial_overlay(db_session):
    u = _U(
        subscription_type="free",
        trial_expires_at=int(time.time()) + 3600,
    )
    limit = await get_effective_logistics_limit(db_session, u)
    assert limit == 10


@pytest.mark.asyncio
async def test_count_user_active_rules_excludes_overflow_disabled(
    db_session, test_user
):
    from models.logistics import Logistics

    uid = test_user["id"]
    rows = [
        Logistics(user_id=uid, name="r1", is_active=1, disabled_by_overflow=0),
        Logistics(user_id=uid, name="r2", is_active=1, disabled_by_overflow=0),
        Logistics(user_id=uid, name="r3", is_active=1, disabled_by_overflow=1),
        Logistics(user_id=uid, name="r4", is_active=0, disabled_by_overflow=0),
    ]
    db_session.add_all(rows)
    await db_session.commit()

    count = await count_user_active_rules(db_session, uid)
    assert count == 2
