# -*- coding: utf-8 -*-
"""
Comprehensive tests for db/sessions_crud.py
Covers all 16 functions with all branches.
"""

import time
from uuid import uuid4

import pytest
from sqlalchemy import delete

from db.sessions_crud import (
    add_login_attempt,
    add_trusted_device,
    count_active_sessions,
    deactivate_all_sessions,
    deactivate_session,
    deactivate_trusted_device,
    get_lockout,
    get_login_attempts,
    get_oldest_active_session,
    get_session,
    get_session_with_user,
    get_trusted_device,
    insert_session,
    remove_lockout,
    set_lockout,
    update_session_activity,
)
from models.session import ActiveSession, LoginAttempt, TrustedDevice, UserLockout

_FLOAT_TOL = 64


def _sid():
    """Return a unique session_id string."""
    return uuid4().hex


def _now():
    return time.time()


async def _make_session(db_session, user_id, last_activity=None, session_id=None):
    """Insert an active session and flush."""
    sid = session_id or _sid()
    ts = last_activity if last_activity is not None else _now()
    await insert_session(
        db_session,
        session_id=sid,
        user_id=user_id,
        ip_address="127.0.0.1",
        user_agent="TestAgent/1.0",
        now=ts,
    )
    await db_session.flush()
    return sid


async def _cleanup_login_data(db_session, identifier):
    """Remove login_attempts and user_lockouts for identifier."""
    await db_session.execute(
        delete(LoginAttempt).where(LoginAttempt.identifier == identifier)
    )
    await db_session.execute(
        delete(UserLockout).where(UserLockout.identifier == identifier)
    )
    from sqlalchemy import text

    await db_session.execute(
        text(
            "SELECT setval('login_attempts_id_seq', "
            "COALESCE((SELECT MAX(id) FROM login_attempts), 0) + 1, false)"
        )
    )
    await db_session.flush()


async def _cleanup_trusted_devices(db_session, user_id):
    """Remove all trusted_devices for a user."""
    await db_session.execute(
        delete(TrustedDevice).where(TrustedDevice.user_id == user_id)
    )
    await db_session.flush()


# ===========================================================================
# 1. count_active_sessions
# ===========================================================================


async def test_count_active_sessions_zero(db_session, test_user):
    uid = test_user["id"]
    count = await count_active_sessions(db_session, uid)
    assert count == 0


async def test_count_active_sessions_one(db_session, test_user):
    uid = test_user["id"]
    await _make_session(db_session, uid)
    count = await count_active_sessions(db_session, uid)
    assert count == 1


async def test_count_active_sessions_multiple(db_session, test_user):
    uid = test_user["id"]
    for _ in range(3):
        await _make_session(db_session, uid)
    count = await count_active_sessions(db_session, uid)
    assert count == 3


async def test_count_active_sessions_excludes_inactive(db_session, test_user):
    uid = test_user["id"]
    sid = await _make_session(db_session, uid)
    await deactivate_session(db_session, sid)
    await db_session.flush()
    count = await count_active_sessions(db_session, uid)
    assert count == 0


# ===========================================================================
# 2. get_oldest_active_session
# ===========================================================================


async def test_get_oldest_active_session_none(db_session, test_user):
    uid = test_user["id"]
    result = await get_oldest_active_session(db_session, uid)
    assert result is None


async def test_get_oldest_active_session_returns_oldest(db_session, test_user):
    uid = test_user["id"]
    base = _now()
    sid_old = await _make_session(db_session, uid, last_activity=base - 1000)
    await _make_session(db_session, uid, last_activity=base)
    await _make_session(db_session, uid, last_activity=base + 1000)

    result = await get_oldest_active_session(db_session, uid)
    assert result is not None
    assert result.session_id == sid_old


async def test_get_oldest_active_session_single(db_session, test_user):
    uid = test_user["id"]
    sid = await _make_session(db_session, uid)
    result = await get_oldest_active_session(db_session, uid)
    assert result is not None
    assert result.session_id == sid


# ===========================================================================
# 3. deactivate_session
# ===========================================================================


async def test_deactivate_session_found(db_session, test_user):
    uid = test_user["id"]
    sid = await _make_session(db_session, uid)
    await deactivate_session(db_session, sid)
    await db_session.flush()
    record = await db_session.get(ActiveSession, sid)
    assert record is not None
    assert record.is_active is False


async def test_deactivate_session_not_found(db_session):
    await deactivate_session(db_session, "nonexistent_session_id_xyz")


async def test_deactivate_session_already_inactive(db_session, test_user):
    uid = test_user["id"]
    sid = await _make_session(db_session, uid)
    await deactivate_session(db_session, sid)
    await db_session.flush()
    await deactivate_session(db_session, sid)
    record = await db_session.get(ActiveSession, sid)
    assert record.is_active is False


# ===========================================================================
# 4. insert_session
# ===========================================================================


async def test_insert_session_creates_record(db_session, test_user):
    uid = test_user["id"]
    sid = _sid()
    now = _now()
    await insert_session(
        db_session,
        session_id=sid,
        user_id=uid,
        ip_address="10.0.0.1",
        user_agent="Mozilla/5.0",
        now=now,
    )
    await db_session.flush()
    record = await db_session.get(ActiveSession, sid)
    assert record is not None
    assert record.user_id == uid
    assert record.ip_address == "10.0.0.1"
    assert record.user_agent == "Mozilla/5.0"
    assert abs(record.created_at - now) < _FLOAT_TOL
    assert abs(record.last_activity - now) < _FLOAT_TOL
    assert abs(record.last_rotation - now) < _FLOAT_TOL
    assert record.is_active is True


# ===========================================================================
# 5. get_session
# ===========================================================================


async def test_get_session_found(db_session, test_user):
    uid = test_user["id"]
    sid = await _make_session(db_session, uid)
    result = await get_session(db_session, sid)
    assert result is not None
    assert result.session_id == sid
    assert result.user_id == uid


async def test_get_session_not_found(db_session):
    result = await get_session(db_session, "nonexistent_xyz_123")
    assert result is None


# ===========================================================================
# 6. get_session_with_user
# ===========================================================================


async def test_get_session_with_user_found(db_session, test_user):
    uid = test_user["id"]
    sid = await _make_session(db_session, uid)
    await db_session.flush()
    result = await get_session_with_user(db_session, sid)
    assert result is not None
    assert isinstance(result, dict)
    assert result["session_id"] == sid
    assert result["user_id"] == uid
    assert result["username"] == test_user["username"]
    assert "role" in result
    assert "is_frozen" in result
    assert "user_type" in result
    assert "is_active" in result
    assert "ip_address" in result
    assert "user_agent" in result
    assert "created_at" in result
    assert "last_activity" in result
    assert "last_rotation" in result


async def test_get_session_with_user_not_found(db_session):
    result = await get_session_with_user(db_session, "no_such_session_456")
    assert result is None


# ===========================================================================
# 7. update_session_activity
# ===========================================================================


async def test_update_session_activity_updates_timestamp(db_session, test_user):
    uid = test_user["id"]
    old_time = _now() - 10000
    sid = await _make_session(db_session, uid, last_activity=old_time)

    new_time = _now()
    await update_session_activity(db_session, sid, new_time)
    await db_session.flush()

    db_session.expire_all()
    record = await db_session.get(ActiveSession, sid)
    assert abs(record.last_activity - new_time) < _FLOAT_TOL


async def test_update_session_activity_nonexistent(db_session):
    await update_session_activity(db_session, "nonexistent_sid", _now())


# ===========================================================================
# 8. deactivate_all_sessions
# ===========================================================================


async def test_deactivate_all_sessions_without_exclude(db_session, test_user):
    uid = test_user["id"]
    sids = [await _make_session(db_session, uid) for _ in range(3)]
    await db_session.flush()

    await deactivate_all_sessions(db_session, uid)
    await db_session.flush()

    db_session.expire_all()
    for sid in sids:
        record = await db_session.get(ActiveSession, sid)
        assert record.is_active is False


async def test_deactivate_all_sessions_with_exclude(db_session, test_user):
    uid = test_user["id"]
    sid_keep = await _make_session(db_session, uid)
    sid_others = [await _make_session(db_session, uid) for _ in range(2)]
    await db_session.flush()

    await deactivate_all_sessions(db_session, uid, exclude_session_id=sid_keep)
    await db_session.flush()

    db_session.expire_all()
    kept = await db_session.get(ActiveSession, sid_keep)
    assert kept.is_active is True

    for sid in sid_others:
        record = await db_session.get(ActiveSession, sid)
        assert record.is_active is False


async def test_deactivate_all_sessions_no_active_sessions(db_session, test_user):
    uid = test_user["id"]
    await deactivate_all_sessions(db_session, uid)


# ===========================================================================
# 9. get_login_attempts
# ===========================================================================


async def test_get_login_attempts_empty(db_session, test_user):
    identifier = test_user["username"]
    await _cleanup_login_data(db_session, identifier)

    since = _now() - 3600
    result = await get_login_attempts(db_session, identifier, since)
    assert len(result) == 0


async def test_get_login_attempts_with_records(db_session, test_user):
    identifier = test_user["username"]
    await _cleanup_login_data(db_session, identifier)

    since = _now() - 3600
    for success in [True, False, False]:
        record = LoginAttempt(
            identifier=identifier,
            ip_address="127.0.0.1",
            timestamp=_now(),
            success=success,
            user_agent="TestAgent",
        )
        db_session.add(record)
    await db_session.flush()

    result = await get_login_attempts(db_session, identifier, since)
    assert len(result) == 3


async def test_get_login_attempts_filters_old(db_session, test_user):
    identifier = test_user["username"]
    await _cleanup_login_data(db_session, identifier)

    old_record = LoginAttempt(
        identifier=identifier,
        ip_address="127.0.0.1",
        timestamp=_now() - 7200,
        success=False,
        user_agent="TestAgent",
    )
    db_session.add(old_record)
    new_record = LoginAttempt(
        identifier=identifier,
        ip_address="127.0.0.1",
        timestamp=_now(),
        success=True,
        user_agent="TestAgent",
    )
    db_session.add(new_record)
    await db_session.flush()

    since = _now() - 3600
    result = await get_login_attempts(db_session, identifier, since)
    assert len(result) == 1
    assert result[0].success is True


# ===========================================================================
# 10. add_login_attempt
# ===========================================================================


async def test_add_login_attempt_creates_record(db_session, test_user):
    identifier = test_user["username"]
    await _cleanup_login_data(db_session, identifier)

    since = _now() - _FLOAT_TOL - 10
    await add_login_attempt(
        db_session,
        identifier=identifier,
        ip_address="192.168.1.1",
        success=False,
        user_agent="TestBrowser/2.0",
    )
    await db_session.flush()

    result = await get_login_attempts(db_session, identifier, since)
    assert len(result) == 1
    assert result[0].identifier == identifier
    assert result[0].ip_address == "192.168.1.1"
    assert result[0].success is False
    assert result[0].user_agent == "TestBrowser/2.0"


async def test_add_login_attempt_success_flag(db_session, test_user):
    identifier = test_user["username"]
    await _cleanup_login_data(db_session, identifier)

    since = _now() - _FLOAT_TOL - 10
    await add_login_attempt(
        db_session,
        identifier=identifier,
        ip_address="10.0.0.1",
        success=True,
        user_agent="TestBrowser/3.0",
    )
    await db_session.flush()

    result = await get_login_attempts(db_session, identifier, since)
    assert len(result) == 1
    assert result[0].success is True


# ===========================================================================
# 11. get_lockout
# ===========================================================================


async def test_get_lockout_not_found(db_session, test_user):
    identifier = test_user["username"]
    await _cleanup_login_data(db_session, identifier)
    result = await get_lockout(db_session, identifier)
    assert result is None


async def test_get_lockout_found(db_session, test_user):
    identifier = test_user["username"]
    await _cleanup_login_data(db_session, identifier)

    locked_until = _now() + 3600
    await set_lockout(db_session, identifier, locked_until, 5)
    await db_session.flush()

    result = await get_lockout(db_session, identifier)
    assert result is not None
    assert result.identifier == identifier
    assert abs(result.locked_until - locked_until) < _FLOAT_TOL
    assert result.attempt_count == 5


# ===========================================================================
# 12. set_lockout
# ===========================================================================


async def test_set_lockout_creates_new(db_session, test_user):
    identifier = test_user["username"]
    await _cleanup_login_data(db_session, identifier)

    locked_until = _now() + 600
    await set_lockout(db_session, identifier, locked_until, 3)
    await db_session.flush()

    record = await get_lockout(db_session, identifier)
    assert record is not None
    assert record.attempt_count == 3
    assert abs(record.locked_until - locked_until) < _FLOAT_TOL


async def test_set_lockout_updates_existing(db_session, test_user):
    identifier = test_user["username"]
    await _cleanup_login_data(db_session, identifier)

    first_time = _now() + 600
    await set_lockout(db_session, identifier, first_time, 3)
    await db_session.flush()

    second_time = _now() + 1200
    await set_lockout(db_session, identifier, second_time, 7)
    await db_session.flush()

    db_session.expire_all()
    record = await get_lockout(db_session, identifier)
    assert record is not None
    assert record.attempt_count == 7
    assert abs(record.locked_until - second_time) < _FLOAT_TOL


# ===========================================================================
# 13. remove_lockout
# ===========================================================================


async def test_remove_lockout_removes_record(db_session, test_user):
    identifier = test_user["username"]
    await _cleanup_login_data(db_session, identifier)

    await set_lockout(db_session, identifier, _now() + 3600, 5)
    await db_session.flush()

    assert await get_lockout(db_session, identifier) is not None

    await remove_lockout(db_session, identifier)
    await db_session.flush()

    assert await get_lockout(db_session, identifier) is None


async def test_remove_lockout_nonexistent_is_safe(db_session, test_user):
    identifier = test_user["username"]
    await _cleanup_login_data(db_session, identifier)
    await remove_lockout(db_session, identifier)


# ===========================================================================
# 14. get_trusted_device
# ===========================================================================


async def test_get_trusted_device_not_found(db_session, test_user):
    uid = test_user["id"]
    result = await get_trusted_device(db_session, uid, "nonexistent_fp_xyz")
    assert result is None


async def test_get_trusted_device_found(db_session, test_user):
    uid = test_user["id"]
    fp = uuid4().hex
    await _cleanup_trusted_devices(db_session, uid)

    await add_trusted_device(
        db_session,
        user_id=uid,
        fingerprint=fp,
        ip_address="10.0.0.5",
        user_agent="Chrome/100",
    )
    await db_session.flush()

    result = await get_trusted_device(db_session, uid, fp)
    assert result is not None
    assert result.device_fingerprint == fp
    assert result.user_id == uid


async def test_get_trusted_device_wrong_fingerprint(db_session, test_user):
    uid = test_user["id"]
    fp = uuid4().hex
    await _cleanup_trusted_devices(db_session, uid)

    await add_trusted_device(
        db_session,
        user_id=uid,
        fingerprint=fp,
        ip_address="10.0.0.5",
        user_agent="Chrome/100",
    )
    await db_session.flush()

    result = await get_trusted_device(db_session, uid, "wrong_fp")
    assert result is None


# ===========================================================================
# 15. add_trusted_device
# ===========================================================================


async def test_add_trusted_device_creates_record(db_session, test_user):
    uid = test_user["id"]
    fp = uuid4().hex
    await _cleanup_trusted_devices(db_session, uid)

    before = _now() - _FLOAT_TOL
    await add_trusted_device(
        db_session,
        user_id=uid,
        fingerprint=fp,
        ip_address="172.16.0.1",
        user_agent="Safari/15.0",
    )
    await db_session.flush()

    record = await get_trusted_device(db_session, uid, fp)
    assert record is not None
    assert record.user_id == uid
    assert record.device_fingerprint == fp
    assert record.ip_address == "172.16.0.1"
    assert record.user_agent == "Safari/15.0"
    assert record.is_active is True
    assert record.trusted_at >= before
    assert record.last_used >= before


# ===========================================================================
# 16. deactivate_trusted_device
# ===========================================================================


async def test_deactivate_trusted_device_found(db_session, test_user):
    uid = test_user["id"]
    fp = uuid4().hex
    await _cleanup_trusted_devices(db_session, uid)

    await add_trusted_device(
        db_session,
        user_id=uid,
        fingerprint=fp,
        ip_address="10.0.0.1",
        user_agent="Firefox/90",
    )
    await db_session.flush()

    await deactivate_trusted_device(db_session, uid, fp)
    await db_session.flush()

    db_session.expire_all()
    record = await get_trusted_device(db_session, uid, fp)
    assert record is not None
    assert record.is_active is False


async def test_deactivate_trusted_device_not_found(db_session, test_user):
    uid = test_user["id"]
    await deactivate_trusted_device(db_session, uid, "does_not_exist_fp")


async def test_deactivate_trusted_device_already_inactive(db_session, test_user):
    uid = test_user["id"]
    fp = uuid4().hex
    await _cleanup_trusted_devices(db_session, uid)

    await add_trusted_device(
        db_session,
        user_id=uid,
        fingerprint=fp,
        ip_address="10.0.0.1",
        user_agent="Edge/99",
    )
    await db_session.flush()

    await deactivate_trusted_device(db_session, uid, fp)
    await db_session.flush()
    await deactivate_trusted_device(db_session, uid, fp)


# ===========================================================================
# Additional edge-case / integration tests
# ===========================================================================


async def test_insert_and_count_and_deactivate_flow(db_session, test_user):
    uid = test_user["id"]

    assert await count_active_sessions(db_session, uid) == 0

    sid1 = await _make_session(db_session, uid)
    sid2 = await _make_session(db_session, uid)
    assert await count_active_sessions(db_session, uid) == 2

    await deactivate_session(db_session, sid1)
    await db_session.flush()
    assert await count_active_sessions(db_session, uid) == 1

    await deactivate_session(db_session, sid2)
    await db_session.flush()
    assert await count_active_sessions(db_session, uid) == 0


async def test_deactivate_all_sessions_then_count(db_session, test_user):
    uid = test_user["id"]
    for _ in range(4):
        await _make_session(db_session, uid)
    await db_session.flush()

    assert await count_active_sessions(db_session, uid) == 4

    await deactivate_all_sessions(db_session, uid)
    await db_session.flush()

    assert await count_active_sessions(db_session, uid) == 0


async def test_get_session_with_user_is_active_field(db_session, test_user):
    uid = test_user["id"]
    sid = await _make_session(db_session, uid)
    await db_session.flush()

    result = await get_session_with_user(db_session, sid)
    assert result is not None
    assert result["is_active"] is True


async def test_get_login_attempts_different_identifier_isolated(db_session, test_user):
    identifier = test_user["username"]
    other_identifier = uuid4().hex
    await _cleanup_login_data(db_session, identifier)

    since = _now() - _FLOAT_TOL - 10
    await add_login_attempt(db_session, identifier, "1.2.3.4", False, "UA")
    await add_login_attempt(db_session, other_identifier, "1.2.3.4", True, "UA")
    await db_session.flush()

    result = await get_login_attempts(db_session, identifier, since)
    assert len(result) == 1
    assert result[0].identifier == identifier

    await db_session.execute(
        delete(LoginAttempt).where(LoginAttempt.identifier == other_identifier)
    )
    await db_session.flush()


async def test_set_lockout_then_remove_then_get(db_session, test_user):
    identifier = test_user["username"]
    await _cleanup_login_data(db_session, identifier)

    await set_lockout(db_session, identifier, _now() + 3600, 10)
    await db_session.flush()

    record = await get_lockout(db_session, identifier)
    assert record is not None

    await remove_lockout(db_session, identifier)
    await db_session.flush()

    record_after = await get_lockout(db_session, identifier)
    assert record_after is None


async def test_update_session_activity_reflects_in_get_session(db_session, test_user):
    uid = test_user["id"]
    old_ts = _now() - 10000
    sid = await _make_session(db_session, uid, last_activity=old_ts)

    new_ts = _now()
    await update_session_activity(db_session, sid, new_ts)
    await db_session.flush()
    db_session.expire_all()

    record = await get_session(db_session, sid)
    assert record is not None
    assert abs(record.last_activity - new_ts) < _FLOAT_TOL


async def test_oldest_session_ignores_inactive(db_session, test_user):
    uid = test_user["id"]
    base = _now()

    sid_old = await _make_session(db_session, uid, last_activity=base - 10000)
    await deactivate_session(db_session, sid_old)

    sid_new = await _make_session(db_session, uid, last_activity=base)
    await db_session.flush()

    result = await get_oldest_active_session(db_session, uid)
    assert result is not None
    assert result.session_id == sid_new


async def test_trusted_device_add_then_deactivate_then_get(db_session, test_user):
    uid = test_user["id"]
    fp = uuid4().hex
    await _cleanup_trusted_devices(db_session, uid)

    await add_trusted_device(db_session, uid, fp, "1.2.3.4", "UA")
    await db_session.flush()

    device = await get_trusted_device(db_session, uid, fp)
    assert device is not None
    assert device.is_active is True

    await deactivate_trusted_device(db_session, uid, fp)
    await db_session.flush()
    db_session.expire_all()

    device_after = await get_trusted_device(db_session, uid, fp)
    assert device_after is not None
    assert device_after.is_active is False
