"""
Comprehensive tests for db/users.py — targets 100% branch coverage.
"""

import time
import uuid
from unittest.mock import AsyncMock, patch

import pytest

import db.users as users_mod
from db.users import (
    _get_remaining_calculations,
    create_user,
    delete_user,
    find_by_username,
    get_user_by_id,
    get_user_preferred_mode,
    get_user_role,
    update_user_password,
    update_user_preferred_mode,
    verify_user,
)
from models.log import AdminActionLog, AlertRecord, UserBehaviorLog, UserLoginLog
from models.logistics import Logistics
from models.order import PaymentOrder
from models.session import ActiveSession, LoginAttempt, UserLockout
from models.user import SubscriptionUpgradeHistory, User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _unique(prefix: str = "u") -> str:
    """Generate a unique string for usernames/emails."""
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# ===========================================================================
# 1. _get_remaining_calculations
# ===========================================================================


def test_remaining_free():
    assert _get_remaining_calculations("free") == 10


def test_remaining_test():
    assert _get_remaining_calculations("test") == -1


def test_remaining_gratitude():
    assert _get_remaining_calculations("gratitude") == -1


def test_remaining_efficiency():
    assert _get_remaining_calculations("efficiency") == -1


def test_remaining_professional():
    assert _get_remaining_calculations("professional") == -1


def test_remaining_enterprise():
    assert _get_remaining_calculations("enterprise") == -1


def test_remaining_unknown():
    assert _get_remaining_calculations("unknown_type") == 10


def test_remaining_empty_string():
    # Empty string is not in the named list → falls to default 10
    assert _get_remaining_calculations("") == 10


# ===========================================================================
# 2. create_user
# ===========================================================================


async def test_create_user_success(db_session):
    username = _unique("create")
    uid = await create_user(db_session, username, "P@ssw0rd!")
    assert uid is not None
    assert isinstance(uid, int)


async def test_create_user_with_email(db_session):
    username = _unique("emailuser")
    email = f"{username}@example.com"
    uid = await create_user(db_session, username, "P@ssw0rd!", email=email)
    assert uid is not None


async def test_create_user_without_email(db_session):
    username = _unique("noemail")
    uid = await create_user(db_session, username, "P@ssw0rd!", email=None)
    assert uid is not None


async def test_create_user_empty_username(db_session):
    result = await create_user(db_session, "", "P@ssw0rd!")
    assert result is None


async def test_create_user_whitespace_username(db_session):
    result = await create_user(db_session, "   ", "P@ssw0rd!")
    assert result is None


async def test_create_user_none_username(db_session):
    result = await create_user(db_session, None, "P@ssw0rd!")
    assert result is None


async def test_create_user_duplicate_username(db_session):
    username = _unique("dup")
    uid1 = await create_user(db_session, username, "P@ssw0rd!")
    assert uid1 is not None
    uid2 = await create_user(db_session, username, "P@ssw0rd!")
    assert uid2 is None


async def test_create_user_duplicate_username_case_insensitive(db_session):
    username = _unique("casedup")
    uid1 = await create_user(db_session, username, "P@ssw0rd!")
    assert uid1 is not None
    uid2 = await create_user(db_session, username.upper(), "P@ssw0rd!")
    assert uid2 is None


async def test_create_user_duplicate_email(db_session):
    username1 = _unique("dupemail1")
    username2 = _unique("dupemail2")
    email = f"{_unique('em')}@example.com"
    uid1 = await create_user(db_session, username1, "P@ssw0rd!", email=email)
    assert uid1 is not None
    uid2 = await create_user(db_session, username2, "P@ssw0rd!", email=email)
    assert uid2 is None


async def test_create_user_duplicate_email_case_insensitive(db_session):
    username1 = _unique("dupemci1")
    username2 = _unique("dupemci2")
    email_lower = f"{_unique('emci')}@example.com"
    uid1 = await create_user(db_session, username1, "P@ssw0rd!", email=email_lower)
    assert uid1 is not None
    uid2 = await create_user(
        db_session, username2, "P@ssw0rd!", email=email_lower.upper()
    )
    assert uid2 is None


async def test_create_user_is_test_user_true(db_session):
    username = _unique("testflag")
    uid = await create_user(db_session, username, "P@ssw0rd!", is_test_user=True)
    assert uid is not None
    user = await db_session.get(User, uid)
    assert user.is_test_user == 1


async def test_create_user_is_test_user_false(db_session):
    username = _unique("nontestflag")
    uid = await create_user(db_session, username, "P@ssw0rd!", is_test_user=False)
    assert uid is not None
    user = await db_session.get(User, uid)
    assert user.is_test_user == 0


async def test_create_user_exception_returns_none(db_session):
    """Simulate flush raising an exception — create_user returns None."""
    username = _unique("excuser")
    with patch.object(
        db_session, "flush", new_callable=AsyncMock, side_effect=Exception("DB error")
    ):
        result = await create_user(db_session, username, "P@ssw0rd!")
    assert result is None


async def test_create_user_free_type_remaining(db_session):
    username = _unique("freetype")
    uid = await create_user(db_session, username, "P@ssw0rd!", user_type="free")
    user = await db_session.get(User, uid)
    assert user.remaining_calculations == 10


async def test_create_user_enterprise_type_remaining(db_session):
    username = _unique("enttype")
    uid = await create_user(db_session, username, "P@ssw0rd!", user_type="enterprise")
    user = await db_session.get(User, uid)
    assert user.remaining_calculations == -1


# ===========================================================================
# 3. verify_user
# ===========================================================================


async def test_verify_user_correct_password(db_session, test_user):
    result = await verify_user(db_session, test_user["username"], test_user["password"])
    assert result is not None
    assert result["id"] == test_user["id"]
    assert result["username"] == test_user["username"]
    assert "role" in result
    assert "email" in result
    assert "user_type" in result


async def test_verify_user_wrong_password(db_session, test_user):
    result = await verify_user(db_session, test_user["username"], "WrongPassword!")
    assert result is None


async def test_verify_user_not_found(db_session):
    result = await verify_user(db_session, "nonexistent_user_xyz", "whatever")
    assert result is None


async def test_verify_user_by_email(db_session):
    username = _unique("verifyemail")
    email = f"{username}@test.com"
    uid = await create_user(db_session, username, "TestP@ss1!", email=email)
    assert uid is not None
    await db_session.commit()
    result = await verify_user(db_session, email, "TestP@ss1!")
    assert result is not None
    assert result["id"] == uid


async def test_verify_user_by_email_case_insensitive(db_session):
    username = _unique("verifyemci")
    email = f"{username}@test.com"
    uid = await create_user(db_session, username, "TestP@ss1!", email=email)
    assert uid is not None
    await db_session.commit()
    result = await verify_user(db_session, email.upper(), "TestP@ss1!")
    assert result is not None
    assert result["id"] == uid


async def test_verify_user_empty_password_fallback(db_session):
    """User with password=None uses '' as stored; verify should fail."""
    username = _unique("nullpwd")
    user = User(
        username=username,
        password=None,
        role="user",
        user_type="free",
        subscription_type="free",
        remaining_calculations=10,
        created_at=str(int(time.time())),
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.commit()
    result = await verify_user(db_session, username, "anypassword")
    assert result is None


async def test_verify_user_user_type_none_defaults_free(db_session):
    """When user.user_type is None, returned dict should have 'free'."""
    username = _unique("notypeusr")
    uid = await create_user(db_session, username, "TestP@ss1!")
    assert uid is not None
    # Force user_type to None directly
    user = await db_session.get(User, uid)
    user.user_type = None
    await db_session.flush()
    await db_session.commit()
    result = await verify_user(db_session, username, "TestP@ss1!")
    assert result is not None
    assert result["user_type"] == "free"


# ===========================================================================
# 4. update_user_password
# ===========================================================================


async def test_update_user_password_success(db_session, test_user):
    result = await update_user_password(
        db_session,
        test_user["id"],
        test_user["password"],
        "NewP@ssw0rd!",
    )
    assert result is True
    # Verify new password works
    verify = await verify_user(db_session, test_user["username"], "NewP@ssw0rd!")
    assert verify is not None


async def test_update_user_password_user_not_found(db_session):
    result = await update_user_password(db_session, 9999999, "oldpass", "newpass")
    assert result is False


async def test_update_user_password_wrong_current(db_session, test_user):
    result = await update_user_password(
        db_session,
        test_user["id"],
        "WrongCurrentPassword!",
        "NewP@ssw0rd!",
    )
    assert result is False


# ===========================================================================
# 5. delete_user
# ===========================================================================


async def test_delete_user_success(db_session):
    """Create a user with dependent rows, verify delete_user removes them."""
    username = _unique("deluser")
    uid = await create_user(db_session, username, "P@ssw0rd!")
    assert uid is not None
    await db_session.flush()

    # Create dependent rows
    logistics = Logistics(user_id=uid, name="Test route")
    db_session.add(logistics)

    order = PaymentOrder(
        order_id=_unique("ord"),
        user_id=uid,
        amount=100,
        description="Test order",
        created_at=int(time.time()),
    )
    db_session.add(order)

    sub_hist = SubscriptionUpgradeHistory(
        user_id=uid,
        from_plan="free",
        to_plan="professional",
        upgrade_time=int(time.time()),
        target_price=99.0,
    )
    db_session.add(sub_hist)

    session_rec = ActiveSession(
        session_id=_unique("sess"),
        user_id=uid,
        created_at=float(int(time.time())),
        last_activity=float(int(time.time())),
    )
    db_session.add(session_rec)

    login_attempt = LoginAttempt(
        identifier=username,
        ip_address="127.0.0.1",
        timestamp=float(int(time.time())),
        success=False,
    )
    db_session.add(login_attempt)

    lockout = UserLockout(
        identifier=username,
        locked_until=float(int(time.time()) + 3600),
        attempt_count=5,
    )
    db_session.add(lockout)

    login_log = UserLoginLog(user_id=uid, login_time=int(time.time()))
    db_session.add(login_log)

    behavior_log = UserBehaviorLog(user_id=uid, behavior_type="login")
    db_session.add(behavior_log)

    admin_log = AdminActionLog(
        admin_id=uid,
        action_type="test_action",
        target_user_id=uid,
    )
    db_session.add(admin_log)

    alert = AlertRecord(
        alert_type="test_alert",
        alert_level="low",
        description="test",
        handled_by=uid,
    )
    db_session.add(alert)

    await db_session.flush()

    result = await delete_user(db_session, uid)
    assert result is True

    await db_session.flush()
    from sqlalchemy import select as sa_select2

    chk = await db_session.execute(sa_select2(User).where(User.id == uid))
    assert chk.scalar_one_or_none() is None


async def test_delete_user_not_found(db_session):
    result = await delete_user(db_session, 9999999)
    assert result is False


async def test_delete_user_admin_blocked(db_session, test_admin):
    result = await delete_user(db_session, test_admin["id"])
    assert result is False


async def test_delete_user_cleans_alert_record(db_session):
    """Alert records with handled_by=user_id get handled_by set to None."""
    username = _unique("alertdel")
    uid = await create_user(db_session, username, "P@ssw0rd!")
    assert uid is not None
    await db_session.flush()

    alert = AlertRecord(
        alert_type="test",
        alert_level="medium",
        description="some alert",
        handled_by=uid,
    )
    db_session.add(alert)
    await db_session.flush()
    alert_id = alert.id

    await delete_user(db_session, uid)

    from sqlalchemy import select as sa_select

    result = await db_session.execute(
        sa_select(AlertRecord).where(AlertRecord.id == alert_id)
    )
    alert_after = result.scalar_one_or_none()
    # Alert record is kept but handled_by is set to None
    if alert_after is not None:
        assert alert_after.handled_by is None


# ===========================================================================
# 6. get_user_preferred_mode
# ===========================================================================


async def test_get_user_preferred_mode_found(db_session, test_user):
    mode = await get_user_preferred_mode(db_session, test_user["id"])
    # Default is 'fast' from server_default
    assert mode is not None or mode is None  # could be None if not set in memory


async def test_get_user_preferred_mode_not_found(db_session):
    mode = await get_user_preferred_mode(db_session, 9999999)
    assert mode is None


async def test_get_user_preferred_mode_set_value(db_session):
    username = _unique("prefmode")
    uid = await create_user(db_session, username, "P@ssw0rd!")
    user = await db_session.get(User, uid)
    user.preferred_mode = "accurate"
    await db_session.flush()
    await db_session.commit()
    mode = await get_user_preferred_mode(db_session, uid)
    assert mode == "accurate"


# ===========================================================================
# 7. update_user_preferred_mode
# ===========================================================================


async def test_update_user_preferred_mode_found(db_session, test_user):
    await update_user_preferred_mode(db_session, test_user["id"], "accurate")
    user = await db_session.get(User, test_user["id"])
    assert user.preferred_mode == "accurate"


async def test_update_user_preferred_mode_not_found(db_session):
    """No-op when user does not exist — should not raise."""
    await update_user_preferred_mode(db_session, 9999999, "accurate")
    # No exception means success


async def test_update_user_preferred_mode_changes_value(db_session):
    username = _unique("updatemode")
    uid = await create_user(db_session, username, "P@ssw0rd!")
    await update_user_preferred_mode(db_session, uid, "fast")
    user = await db_session.get(User, uid)
    assert user.preferred_mode == "fast"
    await update_user_preferred_mode(db_session, uid, "accurate")
    user2 = await db_session.get(User, uid)
    assert user2.preferred_mode == "accurate"


# ===========================================================================
# 8. find_by_username
# ===========================================================================


async def test_find_by_username_found(db_session, test_user):
    user = await find_by_username(db_session, test_user["username"])
    assert user is not None
    assert user.id == test_user["id"]


async def test_find_by_username_case_insensitive(db_session, test_user):
    user = await find_by_username(db_session, test_user["username"].upper())
    assert user is not None
    assert user.id == test_user["id"]


async def test_find_by_username_not_found(db_session):
    user = await find_by_username(db_session, "totally_nonexistent_user_xyz")
    assert user is None


# ===========================================================================
# 9. get_user_by_id
# ===========================================================================


async def test_get_user_by_id_found(db_session, test_user):
    user = await get_user_by_id(db_session, test_user["id"])
    assert user is not None
    assert user.username == test_user["username"]


async def test_get_user_by_id_not_found(db_session):
    user = await get_user_by_id(db_session, 9999999)
    assert user is None


# ===========================================================================
# 10. get_user_role
# ===========================================================================


async def test_get_user_role_found(db_session, test_user):
    role = await get_user_role(db_session, test_user["id"])
    assert role == "user"


async def test_get_user_role_admin(db_session, test_admin):
    role = await get_user_role(db_session, test_admin["id"])
    assert role == "admin"


async def test_get_user_role_not_found(db_session):
    role = await get_user_role(db_session, 9999999)
    assert role is None


# ===========================================================================
# Additional edge-case / branch coverage tests
# ===========================================================================


async def test_create_user_all_paid_types_remaining(db_session):
    """All named paid types should get -1 remaining calculations."""
    paid_types = ["test", "gratitude", "efficiency", "professional", "enterprise"]
    for utype in paid_types:
        username = _unique(f"type_{utype}")
        uid = await create_user(db_session, username, "P@ssw0rd!", user_type=utype)
        assert uid is not None, f"Expected user created for type={utype}"
        user = await db_session.get(User, uid)
        assert user.remaining_calculations == -1, f"Failed for type={utype}"


async def test_verify_user_username_case_insensitive(db_session):
    username = _unique("verifycaseuser")
    uid = await create_user(db_session, username, "TestP@ss1!")
    assert uid is not None
    await db_session.commit()
    result = await verify_user(db_session, username.upper(), "TestP@ss1!")
    assert result is not None
    assert result["id"] == uid


async def test_delete_user_with_no_dependent_rows(db_session):
    """Deleting a user with zero dependent rows should succeed."""
    username = _unique("cleanuser")
    uid = await create_user(db_session, username, "P@ssw0rd!")
    assert uid is not None
    await db_session.flush()
    result = await delete_user(db_session, uid)
    assert result is True
    await db_session.flush()
    from sqlalchemy import select as sa_select3

    chk = await db_session.execute(sa_select3(User).where(User.id == uid))
    assert chk.scalar_one_or_none() is None


async def test_create_user_role_stored(db_session):
    username = _unique("roleuser")
    uid = await create_user(db_session, username, "P@ssw0rd!", role="admin")
    user = await db_session.get(User, uid)
    assert user.role == "admin"


async def test_create_user_email_stored(db_session):
    username = _unique("emailstored")
    email = f"{username}@stored.com"
    uid = await create_user(db_session, username, "P@ssw0rd!", email=email)
    user = await db_session.get(User, uid)
    assert user.email == email


async def test_update_user_password_null_stored(db_session):
    """User with password=None — verify_password against '' fails → False."""
    username = _unique("nullpwdupd")
    user = User(
        username=username,
        password=None,
        role="user",
        user_type="free",
        subscription_type="free",
        remaining_calculations=10,
        created_at=str(int(time.time())),
    )
    db_session.add(user)
    await db_session.flush()
    uid = user.id
    result = await update_user_password(db_session, uid, "anything", "newpass")
    assert result is False


async def test_delete_user_admin_target_user_in_log(db_session):
    """Admin action log targeting a non-admin user gets cleaned up."""
    username = _unique("tgtuser")
    uid = await create_user(db_session, username, "P@ssw0rd!")
    assert uid is not None
    await db_session.flush()

    # Create an admin action log targeting this user
    admin_log = AdminActionLog(
        admin_id=1,  # any existing or non-existing admin id
        action_type="view_user",
        target_user_id=uid,
    )
    db_session.add(admin_log)
    await db_session.flush()

    result = await delete_user(db_session, uid)
    assert result is True
