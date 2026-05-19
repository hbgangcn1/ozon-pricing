import time
from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from models.user import User
from db.subscriptions import (
    _check_enterprise_status,
    _check_monthly_status,
    _check_new_tier_free,
    _check_test_status,
    _get_days_remaining_from_info,
    _parse_expiry_date,
    check_user_subscription_status,
    decrement_user_calculations,
    get_user_subscription_info,
    reset_free_users_daily_calculations,
    reset_user_daily_calculations,
    update_user_subscription,
)


async def test_get_subscription_info_returns_all_fields(db_session, test_user):
    result = await get_user_subscription_info(db_session, test_user["id"])
    assert result is not None
    assert result["id"] == test_user["id"]
    assert result["username"] == test_user["username"]
    for key in (
        "user_type",
        "expiry_date",
        "remaining_calculations",
        "first_login_date",
        "test_days_remaining",
        "role",
        "subscription_type",
        "subscription_expires",
    ):
        assert key in result


async def test_get_subscription_info_nonexistent_returns_none(db_session):
    assert await get_user_subscription_info(db_session, 999999999) is None


async def test_update_subscription_success(db_session, test_user):
    assert (
        await update_user_subscription(
            db_session, test_user["id"], {"remaining_calculations": 5}
        )
        is True
    )
    info = await get_user_subscription_info(db_session, test_user["id"])
    assert info["remaining_calculations"] == 5


async def test_update_subscription_multiple_fields(db_session, test_user):
    assert (
        await update_user_subscription(
            db_session,
            test_user["id"],
            {"subscription_type": "monthly", "expiry_date": "2099-12-31"},
        )
        is True
    )
    info = await get_user_subscription_info(db_session, test_user["id"])
    assert info["subscription_type"] == "monthly"
    assert info["expiry_date"] == "2099-12-31"


async def test_update_subscription_nonexistent_returns_false(db_session):
    assert (
        await update_user_subscription(
            db_session, 999999999, {"remaining_calculations": 5}
        )
        is False
    )


async def test_update_subscription_unknown_field_ignored(db_session, test_user):
    assert (
        await update_user_subscription(
            db_session, test_user["id"], {"nonexistent_field_xyz": "val"}
        )
        is True
    )


async def test_check_status_admin(db_session, test_admin):
    result = await check_user_subscription_status(db_session, test_admin["id"])
    assert result["valid"] is True
    assert result["user_type"] == "admin"
    assert result["role"] == "admin"


async def test_check_status_nonexistent(db_session):
    result = await check_user_subscription_status(db_session, 999999999)
    assert result["valid"] is False
    assert "用户不存在" in result["message"]


async def test_check_status_permanent(db_session, test_user):
    await update_user_subscription(
        db_session,
        test_user["id"],
        {"subscription_type": "permanent", "user_type": "permanent"},
    )
    result = await check_user_subscription_status(db_session, test_user["id"])
    assert result["valid"] is True
    assert "永久用户" in result["message"]


async def test_check_status_test_no_first_login(db_session, test_user):
    await update_user_subscription(
        db_session,
        test_user["id"],
        {"subscription_type": "test", "user_type": "test", "first_login_date": None},
    )
    result = await check_user_subscription_status(db_session, test_user["id"])
    assert result["valid"] is True
    assert "未开始计时" in result["message"]


async def test_check_status_test_valid_days_remaining(db_session, test_user):
    first_login = (datetime.now() - timedelta(days=3)).isoformat()
    await update_user_subscription(
        db_session,
        test_user["id"],
        {
            "subscription_type": "test",
            "user_type": "test",
            "first_login_date": first_login,
        },
    )
    result = await check_user_subscription_status(db_session, test_user["id"])
    assert result["valid"] is True
    assert result["remaining_days"] > 0


async def test_check_status_test_expired(db_session, test_user):
    first_login = (datetime.now() - timedelta(days=10)).isoformat()
    await update_user_subscription(
        db_session,
        test_user["id"],
        {
            "subscription_type": "test",
            "user_type": "test",
            "first_login_date": first_login,
        },
    )
    result = await check_user_subscription_status(db_session, test_user["id"])
    assert result["valid"] is False


async def test_check_status_monthly_valid_unlimited(db_session, test_user):
    future = (date.today() + timedelta(days=30)).strftime("%Y-%m-%d")
    await update_user_subscription(
        db_session,
        test_user["id"],
        {
            "subscription_type": "monthly",
            "user_type": "monthly",
            "expiry_date": future,
            "remaining_calculations": -1,
        },
    )
    result = await check_user_subscription_status(db_session, test_user["id"])
    assert result["valid"] is True
    assert "无限次" in result["message"]


async def test_check_status_monthly_valid_limited(db_session, test_user):
    future = (date.today() + timedelta(days=15)).strftime("%Y-%m-%d")
    await update_user_subscription(
        db_session,
        test_user["id"],
        {
            "subscription_type": "monthly",
            "user_type": "monthly",
            "expiry_date": future,
            "remaining_calculations": 20,
        },
    )
    result = await check_user_subscription_status(db_session, test_user["id"])
    assert result["valid"] is True
    assert result["remaining_calculations"] == 20


async def test_check_status_monthly_expired(db_session, test_user):
    past = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
    await update_user_subscription(
        db_session,
        test_user["id"],
        {"subscription_type": "monthly", "user_type": "monthly", "expiry_date": past},
    )
    result = await check_user_subscription_status(db_session, test_user["id"])
    assert result["valid"] is False


async def test_check_status_monthly_no_expiry(db_session, test_user):
    await update_user_subscription(
        db_session,
        test_user["id"],
        {"subscription_type": "monthly", "user_type": "monthly", "expiry_date": None},
    )
    result = await check_user_subscription_status(db_session, test_user["id"])
    assert result["valid"] is False


async def test_check_status_enterprise_old_style_valid(db_session, test_user):
    future = (date.today() + timedelta(days=60)).strftime("%Y-%m-%d")
    await update_user_subscription(
        db_session,
        test_user["id"],
        {"subscription_type": None, "user_type": "enterprise", "expiry_date": future},
    )
    result = await check_user_subscription_status(db_session, test_user["id"])
    assert result["valid"] is True
    assert "remaining_days" in result


async def test_check_status_enterprise_old_style_expired(db_session, test_user):
    past = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
    await update_user_subscription(
        db_session,
        test_user["id"],
        {"subscription_type": None, "user_type": "enterprise", "expiry_date": past},
    )
    result = await check_user_subscription_status(db_session, test_user["id"])
    assert result["valid"] is False


async def test_check_status_enterprise_old_style_no_expiry(db_session, test_user):
    await update_user_subscription(
        db_session,
        test_user["id"],
        {"subscription_type": None, "user_type": "enterprise", "expiry_date": None},
    )
    result = await check_user_subscription_status(db_session, test_user["id"])
    assert result["valid"] is False


async def test_check_status_free_normal(db_session, test_user):
    await update_user_subscription(
        db_session,
        test_user["id"],
        {"subscription_type": "free", "user_type": "free", "remaining_calculations": 5},
    )
    result = await check_user_subscription_status(db_session, test_user["id"])
    assert result["valid"] is True
    assert result["remaining_calculations"] == 5


async def test_check_status_free_minus_one_resets_to_10(db_session, test_user):
    await update_user_subscription(
        db_session,
        test_user["id"],
        {
            "subscription_type": "free",
            "user_type": "free",
            "remaining_calculations": -1,
        },
    )
    result = await check_user_subscription_status(db_session, test_user["id"])
    assert result["valid"] is True
    assert result["remaining_calculations"] == 10


async def test_check_status_gratitude(db_session, test_user):
    await update_user_subscription(
        db_session,
        test_user["id"],
        {"subscription_type": "gratitude", "user_type": "gratitude"},
    )
    result = await check_user_subscription_status(db_session, test_user["id"])
    assert result["valid"] is True
    assert result["remaining_days"] == -1
    assert result["remaining_calculations"] == -1


async def test_check_status_efficiency_valid(db_session, test_user):
    future_ts = int(time.time()) + 30 * 24 * 3600
    await update_user_subscription(
        db_session,
        test_user["id"],
        {
            "subscription_type": "efficiency",
            "user_type": "efficiency",
            "subscription_expires": future_ts,
            "remaining_calculations": 100,
        },
    )
    result = await check_user_subscription_status(db_session, test_user["id"])
    assert result["valid"] is True
    assert result["remaining_days"] > 0


async def test_check_status_efficiency_expired(db_session, test_user):
    past_ts = int(time.time()) - 30 * 24 * 3600
    await update_user_subscription(
        db_session,
        test_user["id"],
        {
            "subscription_type": "efficiency",
            "user_type": "efficiency",
            "subscription_expires": past_ts,
            "remaining_calculations": 0,
        },
    )
    result = await check_user_subscription_status(db_session, test_user["id"])
    assert result["valid"] is False
    assert result["remaining_days"] == 0


async def test_check_status_professional_valid_expiry_date(db_session, test_user):
    future = (datetime.now() + timedelta(days=20)).isoformat()
    await update_user_subscription(
        db_session,
        test_user["id"],
        {
            "subscription_type": "professional",
            "user_type": "professional",
            "subscription_expires": None,
            "expiry_date": future,
            "remaining_calculations": 50,
        },
    )
    result = await check_user_subscription_status(db_session, test_user["id"])
    assert result["valid"] is True
    assert result["remaining_days"] > 0


async def test_check_status_professional_no_dates(db_session, test_user):
    await update_user_subscription(
        db_session,
        test_user["id"],
        {
            "subscription_type": "professional",
            "user_type": "professional",
            "subscription_expires": None,
            "expiry_date": None,
        },
    )
    result = await check_user_subscription_status(db_session, test_user["id"])
    assert result["valid"] is False


async def test_check_status_enterprise_new_tier_valid(db_session, test_user):
    future = (date.today() + timedelta(days=30)).strftime("%Y-%m-%d")
    await update_user_subscription(
        db_session,
        test_user["id"],
        {
            "subscription_type": "enterprise",
            "user_type": "enterprise",
            "expiry_date": future,
            "remaining_calculations": 100,
        },
    )
    result = await check_user_subscription_status(db_session, test_user["id"])
    assert result["valid"] is True
    assert result["remaining_days"] > 0


async def test_check_status_enterprise_new_tier_expired(db_session, test_user):
    past = (date.today() - timedelta(days=2)).strftime("%Y-%m-%d")
    await update_user_subscription(
        db_session,
        test_user["id"],
        {
            "subscription_type": "enterprise",
            "user_type": "enterprise",
            "expiry_date": past,
            "remaining_calculations": 0,
        },
    )
    result = await check_user_subscription_status(db_session, test_user["id"])
    assert result["valid"] is False
    assert result["remaining_days"] == 0


async def test_check_status_enterprise_new_tier_no_dates(db_session, test_user):
    await update_user_subscription(
        db_session,
        test_user["id"],
        {
            "subscription_type": "enterprise",
            "user_type": "enterprise",
            "subscription_expires": None,
            "expiry_date": None,
        },
    )
    result = await check_user_subscription_status(db_session, test_user["id"])
    assert result["valid"] is False


async def test_check_status_unknown_type(db_session, test_user):
    await update_user_subscription(
        db_session,
        test_user["id"],
        {"subscription_type": "alien_tier", "user_type": "alien_tier"},
    )
    result = await check_user_subscription_status(db_session, test_user["id"])
    assert result["valid"] is False
    assert "未知用户类型" in result["message"]


async def test_check_status_fallback_user_type_permanent(db_session, test_user):
    await update_user_subscription(
        db_session,
        test_user["id"],
        {"subscription_type": None, "user_type": "permanent"},
    )
    result = await check_user_subscription_status(db_session, test_user["id"])
    assert result["valid"] is True
    assert "永久用户" in result["message"]


async def test_decrement_nonexistent_user(db_session):
    assert await decrement_user_calculations(db_session, 999999999) is False


async def test_decrement_admin_no_change(db_session, test_admin):
    await update_user_subscription(
        db_session, test_admin["id"], {"subscription_type": "admin"}
    )
    assert await decrement_user_calculations(db_session, test_admin["id"]) is True


async def test_decrement_permanent_no_change(db_session, test_user):
    await update_user_subscription(
        db_session,
        test_user["id"],
        {"subscription_type": "permanent", "user_type": "permanent"},
    )
    assert await decrement_user_calculations(db_session, test_user["id"]) is True


async def test_decrement_enterprise_no_change(db_session, test_user):
    await update_user_subscription(
        db_session,
        test_user["id"],
        {"subscription_type": "enterprise", "user_type": "enterprise"},
    )
    assert await decrement_user_calculations(db_session, test_user["id"]) is True


async def test_decrement_gratitude_no_change(db_session, test_user):
    await update_user_subscription(
        db_session,
        test_user["id"],
        {"subscription_type": "gratitude", "user_type": "gratitude"},
    )
    assert await decrement_user_calculations(db_session, test_user["id"]) is True


async def test_decrement_efficiency_no_change(db_session, test_user):
    await update_user_subscription(
        db_session,
        test_user["id"],
        {"subscription_type": "efficiency", "user_type": "efficiency"},
    )
    assert await decrement_user_calculations(db_session, test_user["id"]) is True


async def test_decrement_professional_no_change(db_session, test_user):
    await update_user_subscription(
        db_session,
        test_user["id"],
        {"subscription_type": "professional", "user_type": "professional"},
    )
    assert await decrement_user_calculations(db_session, test_user["id"]) is True


async def test_decrement_test_user_no_change(db_session, test_user):
    await update_user_subscription(
        db_session, test_user["id"], {"subscription_type": "test", "user_type": "test"}
    )
    assert await decrement_user_calculations(db_session, test_user["id"]) is True


async def test_decrement_free_user_with_remaining(db_session, test_user):
    await update_user_subscription(
        db_session,
        test_user["id"],
        {"subscription_type": "free", "user_type": "free", "remaining_calculations": 5},
    )
    assert await decrement_user_calculations(db_session, test_user["id"]) is True


async def test_decrement_free_user_zero_remaining(db_session, test_user):
    await update_user_subscription(
        db_session,
        test_user["id"],
        {"subscription_type": "free", "user_type": "free", "remaining_calculations": 0},
    )
    assert await decrement_user_calculations(db_session, test_user["id"]) is False


async def test_decrement_monthly_user_with_remaining(db_session, test_user):
    await update_user_subscription(
        db_session,
        test_user["id"],
        {
            "subscription_type": "monthly",
            "user_type": "monthly",
            "remaining_calculations": 3,
        },
    )
    assert await decrement_user_calculations(db_session, test_user["id"]) is True


async def test_decrement_monthly_user_zero_remaining(db_session, test_user):
    await update_user_subscription(
        db_session,
        test_user["id"],
        {
            "subscription_type": "monthly",
            "user_type": "monthly",
            "remaining_calculations": 0,
        },
    )
    assert await decrement_user_calculations(db_session, test_user["id"]) is False


async def test_decrement_unknown_type_fallback_to_free(db_session, test_user):
    from sqlalchemy import select
    from models.user import User

    await update_user_subscription(
        db_session,
        test_user["id"],
        {"subscription_type": "unknown_xyz", "user_type": "unknown_xyz"},
    )
    ok = await decrement_user_calculations(db_session, test_user["id"])
    await db_session.commit()
    assert ok is True
    fresh = await db_session.execute(
        select(User.remaining_calculations).where(User.id == test_user["id"])
    )
    assert fresh.scalar_one() == 9


async def test_reset_free_users_returns_int(db_session):
    result = await reset_free_users_daily_calculations(db_session)
    assert isinstance(result, int)
    assert result >= 0


def test_parse_expiry_date_datetime_passthrough():
    dt = datetime(2025, 6, 15, 10, 30)
    assert _parse_expiry_date(dt) == dt


def test_parse_expiry_date_date_object():
    d = date(2025, 6, 15)
    result = _parse_expiry_date(d)
    assert isinstance(result, datetime)
    assert (result.year, result.month, result.day) == (2025, 6, 15)


def test_parse_expiry_date_string_with_T():
    result = _parse_expiry_date("2025-06-15T10:30:00")
    assert isinstance(result, datetime)
    assert result.year == 2025


def test_parse_expiry_date_string_with_T_and_Z():
    result = _parse_expiry_date("2025-06-15T10:30:00Z")
    assert isinstance(result, datetime)
    assert result.year == 2025


def test_parse_expiry_date_string_without_T():
    result = _parse_expiry_date("2025-06-15")
    assert isinstance(result, datetime)
    assert (result.year, result.month, result.day) == (2025, 6, 15)


def test_parse_expiry_date_invalid_type_raises():
    with pytest.raises(ValueError):
        _parse_expiry_date(12345)


def test_parse_expiry_date_list_raises():
    with pytest.raises(ValueError):
        _parse_expiry_date([2025, 6, 15])


def test_check_test_status_no_first_login():
    result = _check_test_status({"first_login_date": None}, "test")
    assert result["valid"] is True
    assert "未开始计时" in result["message"]


def test_check_test_status_valid_days_remaining():
    first_login = (datetime.now() - timedelta(days=3)).isoformat()
    result = _check_test_status({"first_login_date": first_login}, "test")
    assert result["valid"] is True
    assert result["remaining_days"] > 0


def test_check_test_status_expired():
    first_login = (datetime.now() - timedelta(days=10)).isoformat()
    result = _check_test_status({"first_login_date": first_login}, "test")
    assert result["valid"] is False
    assert "过期" in result["message"]


def test_check_test_status_exactly_7_days_expired():
    first_login = (datetime.now() - timedelta(days=7)).isoformat()
    result = _check_test_status({"first_login_date": first_login}, "test")
    assert result["valid"] is False


def test_check_test_status_parse_error_returns_valid():
    result = _check_test_status({"first_login_date": "not-a-valid-date!!!"}, "test")
    assert result["valid"] is True
    assert result["user_type"] == "test"


def test_check_monthly_status_no_expiry():
    result = _check_monthly_status(
        {"expiry_date": None, "remaining_calculations": 5}, "monthly"
    )
    assert result["valid"] is False
    assert "不完整" in result["message"]


def test_check_monthly_status_expired():
    past = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
    result = _check_monthly_status(
        {"expiry_date": past, "remaining_calculations": 5}, "monthly"
    )
    assert result["valid"] is False
    assert result["remaining_days"] == 0


def test_check_monthly_status_valid_unlimited():
    future = (date.today() + timedelta(days=15)).strftime("%Y-%m-%d")
    result = _check_monthly_status(
        {"expiry_date": future, "remaining_calculations": -1}, "monthly"
    )
    assert result["valid"] is True
    assert "无限次" in result["message"]


def test_check_monthly_status_valid_limited():
    future = (date.today() + timedelta(days=15)).strftime("%Y-%m-%d")
    result = _check_monthly_status(
        {"expiry_date": future, "remaining_calculations": 10}, "monthly"
    )
    assert result["valid"] is True
    assert result["remaining_calculations"] == 10
    assert "10次" in result["message"]


def test_check_monthly_status_parse_error():
    result = _check_monthly_status(
        {"expiry_date": "bad-date!!!", "remaining_calculations": 5}, "monthly"
    )
    assert result["valid"] is False
    assert "错误" in result["message"]


def test_check_enterprise_status_no_expiry():
    result = _check_enterprise_status({"expiry_date": None}, "enterprise")
    assert result["valid"] is False
    assert "不完整" in result["message"]


def test_check_enterprise_status_expired():
    past = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
    result = _check_enterprise_status({"expiry_date": past}, "enterprise")
    assert result["valid"] is False
    assert result["remaining_days"] == 0


def test_check_enterprise_status_valid():
    future = (date.today() + timedelta(days=30)).strftime("%Y-%m-%d")
    result = _check_enterprise_status({"expiry_date": future}, "enterprise")
    assert result["valid"] is True
    assert result["remaining_days"] > 0


def test_check_enterprise_status_parse_error():
    result = _check_enterprise_status({"expiry_date": "garbage-value"}, "enterprise")
    assert result["valid"] is False
    assert "错误" in result["message"]


async def test_check_new_tier_free_normal(db_session, test_user):
    result = await _check_new_tier_free(
        db_session,
        {"remaining_calculations": 7, "id": test_user["id"]},
        "free",
        test_user["id"],
    )
    assert result["valid"] is True
    assert result["remaining_calculations"] == 7
    assert "7次" in result["message"]


async def test_check_new_tier_free_minus_one_resets(db_session, test_user):
    result = await _check_new_tier_free(
        db_session,
        {"remaining_calculations": -1, "id": test_user["id"]},
        "free",
        test_user["id"],
    )
    assert result["valid"] is True
    assert result["remaining_calculations"] == 10
    assert "10次" in result["message"]


def test_get_days_remaining_subscription_expires_future():
    future_ts = int(time.time()) + 10 * 24 * 3600
    user_info = {
        "subscription_expires": future_ts,
        "expiry_date": None,
        "remaining_calculations": 50,
    }
    days, calcs, err = _get_days_remaining_from_info(user_info, "efficiency")
    assert err is None
    assert days > 0
    assert calcs == 50


def test_get_days_remaining_subscription_expires_past():
    past_ts = int(time.time()) - 10 * 24 * 3600
    user_info = {
        "subscription_expires": past_ts,
        "expiry_date": None,
        "remaining_calculations": 0,
    }
    days, calcs, err = _get_days_remaining_from_info(user_info, "efficiency")
    assert err is None
    assert days <= 0


def test_get_days_remaining_expiry_date_string_future():
    future = (datetime.now() + timedelta(days=20)).isoformat()
    user_info = {
        "subscription_expires": None,
        "expiry_date": future,
        "remaining_calculations": 30,
    }
    days, calcs, err = _get_days_remaining_from_info(user_info, "professional")
    assert err is None
    assert days > 0
    assert calcs == 30


def test_get_days_remaining_expiry_date_parse_error():
    user_info = {
        "subscription_expires": None,
        "expiry_date": "totally-invalid",
        "remaining_calculations": 10,
    }
    days, calcs, err = _get_days_remaining_from_info(user_info, "efficiency")
    assert days is None
    assert err is not None
    assert err["valid"] is False
    assert "错误" in err["message"]


def test_get_days_remaining_no_dates():
    user_info = {
        "subscription_expires": None,
        "expiry_date": None,
        "remaining_calculations": 5,
    }
    days, calcs, err = _get_days_remaining_from_info(user_info, "professional")
    assert days is None
    assert err is not None
    assert "不完整" in err["message"]


@pytest.mark.asyncio
async def test_reset_user_daily_first_login_of_day(db_session, test_user):
    """Scenario: First login of the day for limited user"""
    with patch("db.subscriptions.get_plan_by_code", new_callable=AsyncMock) as mock_get_plan:
        mock_get_plan.return_value = {"calc_limit": 100, "plan_code": "free"}

        result = await reset_user_daily_calculations(db_session, test_user["id"])
        assert result is True

        info = await get_user_subscription_info(db_session, test_user["id"])
        assert info["remaining_calculations"] == 100
        today = date.today().isoformat()
        user = await db_session.get(User, test_user["id"])
        assert user.last_calculations_reset_date == today


@pytest.mark.asyncio
async def test_reset_user_daily_subsequent_login_same_day(db_session, test_user):
    """Scenario: Subsequent login same day - should NOT reset"""
    today = date.today().isoformat()

    with patch("db.subscriptions.get_plan_by_code", new_callable=AsyncMock) as mock_get_plan:
        mock_get_plan.return_value = {"calc_limit": 100, "plan_code": "free"}

        user = await db_session.get(User, test_user["id"])
        user.last_calculations_reset_date = today
        user.remaining_calculations = 50
        await db_session.commit()

        result = await reset_user_daily_calculations(db_session, test_user["id"])
        assert result is False

        info = await get_user_subscription_info(db_session, test_user["id"])
        assert info["remaining_calculations"] == 50


@pytest.mark.asyncio
async def test_reset_user_daily_unlimited_plan(db_session, test_user):
    """Scenario: Login for unlimited plan user - should NOT reset"""
    with patch("db.subscriptions.get_plan_by_code", new_callable=AsyncMock) as mock_get_plan:
        mock_get_plan.return_value = {"calc_limit": -1, "plan_code": "enterprise"}

        user = await db_session.get(User, test_user["id"])
        user.subscription_type = "enterprise"
        user.remaining_calculations = -1
        await db_session.commit()

        result = await reset_user_daily_calculations(db_session, test_user["id"])
        assert result is False


@pytest.mark.asyncio
async def test_reset_user_daily_after_date_changes(db_session, test_user):
    """Scenario: Login after date changes - should reset"""
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    with patch("db.subscriptions.get_plan_by_code", new_callable=AsyncMock) as mock_get_plan:
        mock_get_plan.return_value = {"calc_limit": 100, "plan_code": "free"}

        user = await db_session.get(User, test_user["id"])
        user.last_calculations_reset_date = yesterday
        user.remaining_calculations = 5
        await db_session.commit()

        result = await reset_user_daily_calculations(db_session, test_user["id"])
        assert result is True

        info = await get_user_subscription_info(db_session, test_user["id"])
        assert info["remaining_calculations"] == 100
        today = date.today().isoformat()
        user = await db_session.get(User, test_user["id"])
        assert user.last_calculations_reset_date == today
