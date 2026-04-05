import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from db.exchange import get_exchange_rate_fallback, update_exchange_rate_fallback
from db.logging_utils import (
    log_user_login,
    log_user_behavior,
    log_admin_action,
    create_alert,
)


def _make_mock_session():
    session = MagicMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()
    return session


# ---------------------------------------------------------------------------
# db/exchange.py — get_exchange_rate_fallback
# ---------------------------------------------------------------------------


async def test_get_exchange_rate_fallback_found():
    """Scalar result is a float → returns that float."""
    session = _make_mock_session()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = 7.25
    session.execute.return_value = mock_result

    result = await get_exchange_rate_fallback(session, "USD/CNY")
    assert result == pytest.approx(7.25)
    assert isinstance(result, float)


async def test_get_exchange_rate_fallback_not_found():
    """scalar_one_or_none returns None → returns None."""
    session = _make_mock_session()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_result

    result = await get_exchange_rate_fallback(session, "NONEXISTENT/PAIR")
    assert result is None


async def test_get_exchange_rate_fallback_exception():
    """Session.execute raises → returns None, no exception propagated."""
    session = _make_mock_session()
    session.execute.side_effect = RuntimeError("db error")

    result = await get_exchange_rate_fallback(session, "USD/CNY")
    assert result is None


# ---------------------------------------------------------------------------
# db/exchange.py — update_exchange_rate_fallback
# ---------------------------------------------------------------------------


async def test_update_exchange_rate_fallback_insert_new():
    """No existing record → session.add called with new ExchangeRate."""
    from models.config import ExchangeRate

    session = _make_mock_session()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_result

    await update_exchange_rate_fallback(session, "EUR/CNY", 7.80, source="api")

    session.add.assert_called_once()
    added = session.add.call_args[0][0]
    assert isinstance(added, ExchangeRate)
    assert added.currency_pair == "EUR/CNY"
    assert added.rate == pytest.approx(7.80)
    assert added.source == "api"


async def test_update_exchange_rate_fallback_update_existing():
    """Existing record found → rate, source, last_updated mutated in place."""
    from models.config import ExchangeRate
    from datetime import datetime, timezone

    existing = ExchangeRate(
        currency_pair="GBP/CNY",
        rate=9.00,
        last_updated=datetime.now(timezone.utc),
        source="old_source",
    )

    session = _make_mock_session()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing
    session.execute.return_value = mock_result

    await update_exchange_rate_fallback(session, "GBP/CNY", 9.50, source="new_source")

    assert existing.rate == pytest.approx(9.50)
    assert existing.source == "new_source"
    session.add.assert_not_called()


async def test_update_exchange_rate_fallback_default_source():
    """Default source argument is empty string when not provided."""
    from models.config import ExchangeRate

    session = _make_mock_session()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_result

    await update_exchange_rate_fallback(session, "JPY/CNY", 0.048)

    added = session.add.call_args[0][0]
    assert isinstance(added, ExchangeRate)
    assert added.source == ""


async def test_update_exchange_rate_fallback_exception():
    """Session.execute raises → no exception propagated (silently logs)."""
    session = _make_mock_session()
    session.execute.side_effect = Exception("boom")

    await update_exchange_rate_fallback(session, "X/Y", 1.0)


# ---------------------------------------------------------------------------
# db/logging_utils.py — log_user_login
# ---------------------------------------------------------------------------


async def test_log_user_login_with_explicit_device_type(db_session, test_user):
    """Explicit device_type bypasses UA detection."""
    from models.log import UserLoginLog
    from sqlalchemy import select

    uid = test_user["id"]
    await log_user_login(
        db_session,
        uid,
        ip_address="1.2.3.4",
        user_agent="SomeBrowser/1.0",
        device_type="tablet",
    )
    await db_session.flush()

    stmt = select(UserLoginLog).where(UserLoginLog.user_id == uid)
    result = await db_session.execute(stmt)
    records = result.scalars().all()
    assert any(r.device_type == "tablet" for r in records)


async def test_log_user_login_mobile_ua(db_session, test_user):
    """UA containing 'mobile' → device_type set to 'mobile'."""
    from models.log import UserLoginLog
    from sqlalchemy import select

    uid = test_user["id"]
    await log_user_login(
        db_session,
        uid,
        ip_address="5.5.5.5",
        user_agent="Mozilla/5.0 (Linux; Android 10; Mobile)",
    )
    await db_session.flush()

    stmt = select(UserLoginLog).where(UserLoginLog.user_id == uid)
    result = await db_session.execute(stmt)
    records = result.scalars().all()
    assert any(r.device_type == "mobile" for r in records)


async def test_log_user_login_android_ua(db_session, test_user):
    """UA containing 'android' (without 'mobile') → device_type set to 'mobile'."""
    from models.log import UserLoginLog
    from sqlalchemy import select

    uid = test_user["id"]
    await log_user_login(
        db_session,
        uid,
        ip_address="6.6.6.6",
        user_agent="Mozilla/5.0 (Android 11; Tablet)",
    )
    await db_session.flush()

    stmt = select(UserLoginLog).where(UserLoginLog.user_id == uid)
    result = await db_session.execute(stmt)
    records = result.scalars().all()
    assert any(r.device_type == "mobile" for r in records)


async def test_log_user_login_tablet_ua(db_session, test_user):
    """UA containing 'tablet' → device_type set to 'tablet'."""
    from models.log import UserLoginLog
    from sqlalchemy import select

    uid = test_user["id"]
    await log_user_login(
        db_session,
        uid,
        ip_address="7.7.7.7",
        user_agent="Mozilla/5.0 (Tablet; Linux)",
    )
    await db_session.flush()

    stmt = select(UserLoginLog).where(UserLoginLog.user_id == uid)
    result = await db_session.execute(stmt)
    records = result.scalars().all()
    assert any(r.device_type == "tablet" for r in records)


async def test_log_user_login_ipad_ua(db_session, test_user):
    """UA containing 'ipad' → device_type set to 'tablet'."""
    from models.log import UserLoginLog
    from sqlalchemy import select

    uid = test_user["id"]
    await log_user_login(
        db_session,
        uid,
        ip_address="8.8.8.8",
        user_agent="Mozilla/5.0 (iPad; CPU OS 14_0)",
    )
    await db_session.flush()

    stmt = select(UserLoginLog).where(UserLoginLog.user_id == uid)
    result = await db_session.execute(stmt)
    records = result.scalars().all()
    assert any(r.device_type == "tablet" for r in records)


async def test_log_user_login_desktop_ua(db_session, test_user):
    """UA not matching mobile/tablet → device_type set to 'desktop'."""
    from models.log import UserLoginLog
    from sqlalchemy import select

    uid = test_user["id"]
    await log_user_login(
        db_session,
        uid,
        ip_address="9.9.9.9",
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/100",
    )
    await db_session.flush()

    stmt = select(UserLoginLog).where(UserLoginLog.user_id == uid)
    result = await db_session.execute(stmt)
    records = result.scalars().all()
    assert any(r.device_type == "desktop" for r in records)


async def test_log_user_login_no_ua(db_session, test_user):
    """Empty user_agent → device_type stays empty string."""
    from models.log import UserLoginLog
    from sqlalchemy import select

    uid = test_user["id"]
    await log_user_login(db_session, uid, ip_address="10.0.0.1", user_agent="")
    await db_session.flush()

    stmt = select(UserLoginLog).where(UserLoginLog.user_id == uid)
    result = await db_session.execute(stmt)
    records = result.scalars().all()
    assert any(r.device_type == "" for r in records)


async def test_log_user_login_exception(db_session, test_user):
    """session.add raises → no exception propagated."""
    uid = test_user["id"]
    with patch.object(db_session, "add", side_effect=Exception("add error")):
        await log_user_login(db_session, uid, ip_address="1.1.1.1")


# ---------------------------------------------------------------------------
# db/logging_utils.py — log_user_behavior
# ---------------------------------------------------------------------------


async def test_log_user_behavior_success(db_session, test_user):
    """Inserts a UserBehaviorLog row."""
    from models.log import UserBehaviorLog
    from sqlalchemy import select

    uid = test_user["id"]
    await log_user_behavior(
        db_session,
        uid,
        behavior_type="search",
        behavior_detail="searched for shoes",
        calculation_mode="standard",
    )
    await db_session.flush()

    stmt = select(UserBehaviorLog).where(UserBehaviorLog.user_id == uid)
    result = await db_session.execute(stmt)
    records = result.scalars().all()
    assert len(records) >= 1
    assert any(r.behavior_type == "search" for r in records)


async def test_log_user_behavior_defaults(db_session, test_user):
    """behavior_detail and calculation_mode default to empty string."""
    from models.log import UserBehaviorLog
    from sqlalchemy import select

    uid = test_user["id"]
    await log_user_behavior(db_session, uid, behavior_type="click")
    await db_session.flush()

    stmt = select(UserBehaviorLog).where(UserBehaviorLog.user_id == uid)
    result = await db_session.execute(stmt)
    records = result.scalars().all()
    assert any(r.behavior_type == "click" and r.behavior_detail == "" for r in records)


async def test_log_user_behavior_exception(db_session, test_user):
    """session.add raises → no exception propagated."""
    uid = test_user["id"]
    with patch.object(db_session, "add", side_effect=RuntimeError("fail")):
        await log_user_behavior(db_session, uid, behavior_type="error_test")


# ---------------------------------------------------------------------------
# db/logging_utils.py — log_admin_action
# ---------------------------------------------------------------------------


async def test_log_admin_action_with_target_user_id(db_session, test_admin, test_user):
    """Inserts AdminActionLog with target_user_id set."""
    from models.log import AdminActionLog
    from sqlalchemy import select

    admin_id = test_admin["id"]
    target_id = test_user["id"]
    await log_admin_action(
        db_session,
        admin_id=admin_id,
        action_type="ban",
        action_detail="banned user",
        target_user_id=target_id,
        target_type="user",
        ip_address="192.168.1.1",
    )
    await db_session.flush()

    stmt = select(AdminActionLog).where(AdminActionLog.admin_id == admin_id)
    result = await db_session.execute(stmt)
    records = result.scalars().all()
    assert any(r.target_user_id == target_id for r in records)


async def test_log_admin_action_without_target_user_id(db_session, test_admin):
    """Inserts AdminActionLog with target_user_id = None."""
    from models.log import AdminActionLog
    from sqlalchemy import select

    admin_id = test_admin["id"]
    await log_admin_action(
        db_session,
        admin_id=admin_id,
        action_type="config_change",
        action_detail="updated settings",
    )
    await db_session.flush()

    stmt = select(AdminActionLog).where(AdminActionLog.admin_id == admin_id)
    result = await db_session.execute(stmt)
    records = result.scalars().all()
    assert any(r.target_user_id is None for r in records)


async def test_log_admin_action_default_fields(db_session, test_admin):
    """Default optional fields are empty strings / None."""
    from models.log import AdminActionLog
    from sqlalchemy import select

    admin_id = test_admin["id"]
    await log_admin_action(db_session, admin_id=admin_id, action_type="view")
    await db_session.flush()

    stmt = select(AdminActionLog).where(AdminActionLog.admin_id == admin_id)
    result = await db_session.execute(stmt)
    records = result.scalars().all()
    assert any(
        r.action_type == "view" and r.action_detail == "" and r.ip_address == ""
        for r in records
    )


async def test_log_admin_action_exception(db_session, test_admin):
    """session.add raises → no exception propagated."""
    admin_id = test_admin["id"]
    with patch.object(db_session, "add", side_effect=Exception("err")):
        await log_admin_action(db_session, admin_id=admin_id, action_type="test")


# ---------------------------------------------------------------------------
# db/logging_utils.py — create_alert
# ---------------------------------------------------------------------------


async def test_create_alert_success_returns_int(db_session):
    """create_alert inserts AlertRecord and returns its integer id."""
    result = await create_alert(
        db_session,
        alert_type="rate_spike",
        alert_level="high",
        description="Rate exceeded threshold",
        threshold_value=8.0,
        actual_value=9.5,
    )
    assert result is not None
    assert isinstance(result, int)
    assert result > 0


async def test_create_alert_minimal_fields(db_session):
    """create_alert with only required fields (no threshold/actual)."""
    result = await create_alert(
        db_session,
        alert_type="system",
        alert_level="low",
        description="System check",
    )
    assert result is not None
    assert isinstance(result, int)


async def test_create_alert_stores_correct_values(db_session):
    """Verify AlertRecord fields match what was passed."""
    from models.log import AlertRecord
    from sqlalchemy import select

    result_id = await create_alert(
        db_session,
        alert_type="price_alert",
        alert_level="medium",
        description="Price above limit",
        threshold_value=100.0,
        actual_value=120.5,
    )
    assert result_id is not None

    stmt = select(AlertRecord).where(AlertRecord.id == result_id)
    result = await db_session.execute(stmt)
    record = result.scalar_one_or_none()
    assert record is not None
    assert record.alert_type == "price_alert"
    assert record.alert_level == "medium"
    assert record.description == "Price above limit"
    assert record.threshold_value == pytest.approx(100.0)
    assert record.actual_value == pytest.approx(120.5)


async def test_create_alert_exception_returns_none(db_session):
    """session.flush raises → returns None, no exception propagated."""
    with patch.object(
        db_session,
        "flush",
        new_callable=AsyncMock,
        side_effect=Exception("flush error"),
    ):
        result = await create_alert(
            db_session,
            alert_type="fail",
            alert_level="critical",
            description="This will fail",
        )
    assert result is None


async def test_create_alert_add_exception_returns_none(db_session):
    """session.add raises → returns None, no exception propagated."""
    with patch.object(db_session, "add", side_effect=Exception("add error")):
        result = await create_alert(
            db_session,
            alert_type="fail2",
            alert_level="high",
            description="Also fails",
        )
    assert result is None
