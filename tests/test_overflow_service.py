"""Tests for services.overflow_service.

QA spec (task 2.3): cover
  - MRU order assertion (5 rules with known last_used_at, limit=3, kept set)
  - last_used_at=0 -> id DESC fallback
  - reselect rejects others' IDs (ids_not_owned)
  - reselect rejects > limit (exceeds_limit)
  - mark_logistics_used 60s throttle (second call within 60s = 0 rows)
  - close_expired_windows idempotent + only closes past expires_at
  - restore_all_overflow re-enables all + closes window with reason
  - auto_trim_user_rules no-op when within limit; idempotent open-window reuse
"""
import time

import pytest
from sqlalchemy import select, text

from database import AsyncSessionLocal
from models.logistics import Logistics
from models.trial_overflow_window import TrialOverflowWindow
from services.overflow_service import (
    MARK_USED_THROTTLE_SECONDS,
    WINDOW_DURATION_SECONDS,
    auto_trim_user_rules,
    close_expired_windows,
    mark_logistics_used,
    reselect_kept_rules,
    restore_all_overflow,
)


async def _seed_rules(session, user_id, specs):
    """Insert logistics rows; specs = list of (name, last_used_at)."""
    rows = [
        Logistics(
            user_id=user_id,
            name=name,
            is_active=1,
            disabled_by_overflow=0,
            last_used_at=lua,
        )
        for name, lua in specs
    ]
    session.add_all(rows)
    await session.commit()
    ids = [r.id for r in rows]
    return ids


async def _list_disabled(session, user_id):
    res = await session.execute(
        select(Logistics.id).where(
            Logistics.user_id == user_id,
            Logistics.disabled_by_overflow == 1,
        )
    )
    return {r[0] for r in res.all()}


async def _open_window(session, user_id):
    res = await session.execute(
        select(TrialOverflowWindow).where(
            TrialOverflowWindow.user_id == user_id,
            TrialOverflowWindow.closed_at == 0,
        )
    )
    return res.scalar_one_or_none()


@pytest.mark.asyncio
async def test_auto_trim_keeps_top_n_by_mru(db_session, test_user):
    uid = test_user["id"]
    now = int(time.time())
    ids = await _seed_rules(
        db_session,
        uid,
        [
            ("r0", now - 500),
            ("r1", now - 100),
            ("r2", now - 300),
            ("r3", now - 50),
            ("r4", now - 200),
        ],
    )
    name_to_id = dict(zip(["r0", "r1", "r2", "r3", "r4"], ids))

    result = await auto_trim_user_rules(db_session, uid, limit=3)
    await db_session.commit()

    assert result.trimmed_count == 2
    # MRU desc: r3(-50), r1(-100), r4(-200), r2(-300), r0(-500) -> top 3
    expected_kept = {name_to_id["r3"], name_to_id["r1"], name_to_id["r4"]}
    assert set(result.kept_ids) == expected_kept
    expected_disabled = {name_to_id["r2"], name_to_id["r0"]}
    assert set(result.disabled_ids) == expected_disabled

    disabled = await _list_disabled(db_session, uid)
    assert disabled == expected_disabled

    win = await _open_window(db_session, uid)
    assert win is not None
    assert win.expires_at == win.opened_at + WINDOW_DURATION_SECONDS


@pytest.mark.asyncio
async def test_auto_trim_id_desc_fallback_when_last_used_at_zero(
    db_session, test_user
):
    uid = test_user["id"]
    ids = await _seed_rules(
        db_session,
        uid,
        [("a", 0), ("b", 0), ("c", 0), ("d", 0)],
    )

    result = await auto_trim_user_rules(db_session, uid, limit=2)
    await db_session.commit()

    assert set(result.kept_ids) == {ids[3], ids[2]}
    assert set(result.disabled_ids) == {ids[1], ids[0]}


@pytest.mark.asyncio
async def test_auto_trim_no_op_when_within_limit(db_session, test_user):
    uid = test_user["id"]
    await _seed_rules(db_session, uid, [("a", 0), ("b", 0)])

    result = await auto_trim_user_rules(db_session, uid, limit=10)
    await db_session.commit()

    assert result.trimmed_count == 0
    assert result.window_id == 0
    win = await _open_window(db_session, uid)
    assert win is None


@pytest.mark.asyncio
async def test_auto_trim_unlimited_limit_negative_one(db_session, test_user):
    uid = test_user["id"]
    await _seed_rules(db_session, uid, [("a", 0), ("b", 0), ("c", 0)])

    result = await auto_trim_user_rules(db_session, uid, limit=-1)
    await db_session.commit()

    assert result.trimmed_count == 0
    assert await _open_window(db_session, uid) is None


@pytest.mark.asyncio
async def test_auto_trim_reuses_existing_open_window(db_session, test_user):
    uid = test_user["id"]
    ids = await _seed_rules(
        db_session,
        uid,
        [("a", 1), ("b", 2), ("c", 3), ("d", 4), ("e", 5)],
    )

    r1 = await auto_trim_user_rules(db_session, uid, limit=3)
    await db_session.commit()
    first_window_id = r1.window_id

    from sqlalchemy import update as _upd
    await db_session.execute(
        _upd(Logistics)
        .where(Logistics.id.in_(ids))
        .values(disabled_by_overflow=0)
    )
    await db_session.commit()

    r2 = await auto_trim_user_rules(db_session, uid, limit=2)
    await db_session.commit()
    assert r2.window_id == first_window_id


@pytest.mark.asyncio
async def test_reselect_happy_path(db_session, test_user):
    uid = test_user["id"]
    ids = await _seed_rules(
        db_session,
        uid,
        [("a", 1), ("b", 2), ("c", 3), ("d", 4), ("e", 5)],
    )
    await auto_trim_user_rules(db_session, uid, limit=3)
    await db_session.commit()

    keep = {ids[0], ids[1]}
    result = await reselect_kept_rules(db_session, uid, keep, limit=3)
    await db_session.commit()

    assert result.status == "ok"
    assert set(result.enabled_ids) == keep
    assert set(result.disabled_ids) == set(ids) - keep

    disabled = await _list_disabled(db_session, uid)
    assert disabled == set(ids) - keep

    win = await _open_window(db_session, uid)
    assert win is None


@pytest.mark.asyncio
async def test_reselect_exceeds_limit(db_session, test_user):
    uid = test_user["id"]
    ids = await _seed_rules(db_session, uid, [("a", 1), ("b", 2), ("c", 3)])

    result = await reselect_kept_rules(
        db_session, uid, set(ids), limit=2
    )
    assert result.status == "exceeds_limit"


@pytest.mark.asyncio
async def test_reselect_rejects_others_ids(db_session, test_user):
    uid = test_user["id"]
    ids = await _seed_rules(db_session, uid, [("a", 1), ("b", 2)])
    await auto_trim_user_rules(db_session, uid, limit=1)
    await db_session.commit()

    result = await reselect_kept_rules(
        db_session, uid, {ids[0], 99_999_999}, limit=2
    )
    assert result.status == "ids_not_owned"


@pytest.mark.asyncio
async def test_reselect_no_open_window(db_session, test_user):
    uid = test_user["id"]
    ids = await _seed_rules(db_session, uid, [("a", 1), ("b", 2)])

    result = await reselect_kept_rules(db_session, uid, {ids[0]}, limit=2)
    assert result.status == "no_open_window"


@pytest.mark.asyncio
async def test_restore_all_overflow_re_enables_and_closes_window(
    db_session, test_user
):
    uid = test_user["id"]
    await _seed_rules(
        db_session, uid, [("a", 1), ("b", 2), ("c", 3), ("d", 4)]
    )
    await auto_trim_user_rules(db_session, uid, limit=2)
    await db_session.commit()

    restored = await restore_all_overflow(db_session, uid, reason="upgraded")
    await db_session.commit()

    assert restored == 2
    assert await _list_disabled(db_session, uid) == set()

    win = await _open_window(db_session, uid)
    assert win is None
    res = await db_session.execute(
        select(TrialOverflowWindow).where(
            TrialOverflowWindow.user_id == uid
        )
    )
    closed = res.scalars().all()
    assert len(closed) == 1
    assert closed[0].close_reason == "upgraded"
    assert closed[0].closed_at > 0


@pytest.mark.asyncio
async def test_mark_logistics_used_throttle(db_session, test_user):
    uid = test_user["id"]
    ids = await _seed_rules(db_session, uid, [("a", 0), ("b", 0)])

    now = int(time.time())
    n1 = await mark_logistics_used(db_session, uid, ids, now=now)
    await db_session.commit()
    assert n1 == 2

    # Second call within throttle window — should write 0 rows
    n2 = await mark_logistics_used(
        db_session, uid, ids, now=now + (MARK_USED_THROTTLE_SECONDS - 1)
    )
    await db_session.commit()
    assert n2 == 0

    # After throttle window — writes again
    n3 = await mark_logistics_used(
        db_session, uid, ids, now=now + MARK_USED_THROTTLE_SECONDS + 1
    )
    await db_session.commit()
    assert n3 == 2


@pytest.mark.asyncio
async def test_close_expired_windows_only_past_due(db_session, test_user):
    uid = test_user["id"]
    now = int(time.time())

    # Partial unique idx allows only ONE open window per user.
    # Test idempotency + selective closure with a single past-due window.
    past = TrialOverflowWindow(
        user_id=uid,
        opened_at=now - 10000,
        expires_at=now - 100,
        closed_at=0,
        close_reason="",
    )
    db_session.add(past)
    await db_session.commit()

    closed = await close_expired_windows(db_session, now=now)
    await db_session.commit()
    assert closed == 1

    # Re-running is idempotent
    closed_again = await close_expired_windows(db_session, now=now)
    await db_session.commit()
    assert closed_again == 0

    await db_session.refresh(past)
    assert past.closed_at == now
    assert past.close_reason == "expired"

    # Now open a future-dated window; close_expired should leave it alone
    future = TrialOverflowWindow(
        user_id=uid,
        opened_at=now,
        expires_at=now + 10000,
        closed_at=0,
        close_reason="",
    )
    db_session.add(future)
    await db_session.commit()

    closed_future = await close_expired_windows(db_session, now=now)
    await db_session.commit()
    assert closed_future == 0
    await db_session.refresh(future)
    assert future.closed_at == 0
