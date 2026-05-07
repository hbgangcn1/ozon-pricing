"""Integration tests for scripts/trial_check.py (Task 5.1 / 7.7).

Covers:
  - --dry-run produces zero writes (user.trial_plan_at_start unchanged,
    no auto-trim, no window close)
  - normal run trims overflow + clears trial_plan_at_start
  - re-run after a normal run is a no-op (0 processed, idempotent)
  - close_expired_windows path: a past-deadline open window gets closed
    with close_reason='expired'
"""
import time

import pytest
from sqlalchemy import select

from database import AsyncSessionLocal
from models.logistics import Logistics
from models.trial_overflow_window import TrialOverflowWindow
from models.user import User
from scripts.trial_check import run as trial_check_run


async def _seed_expired_trial_user_with_overflow(user_id: int, n_rules: int):
    async with AsyncSessionLocal() as s:
        u = await s.get(User, user_id)
        u.subscription_type = "free"
        u.trial_used = 1
        u.trial_started_at = int(time.time()) - 8 * 24 * 3600
        u.trial_expires_at = int(time.time()) - 3600
        u.trial_plan_at_start = "professional"
        for i in range(n_rules):
            s.add(Logistics(
                user_id=user_id,
                name=f"rule_{i}",
                is_active=1,
                disabled_by_overflow=0,
                last_used_at=int(time.time()) - i * 60,
            ))
        await s.commit()


async def _get_user_marker(user_id: int) -> str:
    async with AsyncSessionLocal() as s:
        u = await s.get(User, user_id)
        return u.trial_plan_at_start


async def _count_disabled(user_id: int) -> int:
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(
            select(Logistics).where(
                Logistics.user_id == user_id,
                Logistics.disabled_by_overflow == 1,
            )
        )).scalars().all()
        return len(rows)


@pytest.mark.asyncio
async def test_dry_run_produces_zero_writes(test_user):
    user_id = test_user["id"]
    await _seed_expired_trial_user_with_overflow(user_id, n_rules=3)

    await trial_check_run(dry_run=True)

    assert await _get_user_marker(user_id) == "professional"
    assert await _count_disabled(user_id) == 0


@pytest.mark.asyncio
async def test_normal_run_trims_and_clears_marker(test_user):
    user_id = test_user["id"]
    await _seed_expired_trial_user_with_overflow(user_id, n_rules=3)

    await trial_check_run(dry_run=False)

    assert await _get_user_marker(user_id) == ""
    assert await _count_disabled(user_id) == 2


@pytest.mark.asyncio
async def test_rerun_is_idempotent_no_changes(test_user):
    user_id = test_user["id"]
    await _seed_expired_trial_user_with_overflow(user_id, n_rules=3)

    await trial_check_run(dry_run=False)
    disabled_after_first = await _count_disabled(user_id)
    marker_after_first = await _get_user_marker(user_id)

    await trial_check_run(dry_run=False)

    assert await _count_disabled(user_id) == disabled_after_first
    assert await _get_user_marker(user_id) == marker_after_first == ""


@pytest.mark.asyncio
async def test_close_expired_windows_marks_closed(test_user):
    user_id = test_user["id"]
    now = int(time.time())
    async with AsyncSessionLocal() as s:
        s.add(TrialOverflowWindow(
            user_id=user_id,
            opened_at=now - 50 * 3600,
            expires_at=now - 3600,
            closed_at=0,
            close_reason="",
        ))
        await s.commit()

    await trial_check_run(dry_run=False)

    async with AsyncSessionLocal() as s:
        win = (await s.execute(
            select(TrialOverflowWindow).where(
                TrialOverflowWindow.user_id == user_id
            )
        )).scalars().first()
        assert win.closed_at > 0
        assert win.close_reason == "expired"
