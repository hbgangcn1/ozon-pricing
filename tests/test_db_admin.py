import time
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import select, text

from db.admin_helpers import (
    _build_users_filter,
    _format_audit_log_rows,
    _format_user_row,
    _subscription_expires_to_datetime,
)


class TestSubscriptionExpiresToDatetime:
    def test_none_returns_none(self):
        assert _subscription_expires_to_datetime(None) is None

    def test_int_returns_datetime(self):
        ts = int(time.time())
        result = _subscription_expires_to_datetime(ts)
        assert isinstance(result, datetime)

    def test_float_returns_datetime(self):
        ts = float(time.time())
        result = _subscription_expires_to_datetime(ts)
        assert isinstance(result, datetime)

    def test_overflow_int_returns_none(self):
        result = _subscription_expires_to_datetime(999999999999999)
        assert result is None

    def test_datetime_returns_same(self):
        dt = datetime(2025, 6, 15, 12, 0, 0)
        result = _subscription_expires_to_datetime(dt)
        assert result is dt

    def test_date_returns_datetime(self):
        d = date(2025, 6, 15)
        result = _subscription_expires_to_datetime(d)
        assert isinstance(result, datetime)
        assert result.year == 2025
        assert result.month == 6
        assert result.day == 15

    def test_str_iso_returns_datetime(self):
        result = _subscription_expires_to_datetime("2025-06-15T12:00:00")
        assert isinstance(result, datetime)
        assert result.year == 2025

    def test_str_date_format_returns_datetime(self):
        result = _subscription_expires_to_datetime("2025-06-15")
        assert isinstance(result, datetime)
        assert result.year == 2025
        assert result.month == 6
        assert result.day == 15

    def test_invalid_str_returns_none(self):
        result = _subscription_expires_to_datetime("not-a-date")
        assert result is None

    def test_other_type_list_returns_none(self):
        result = _subscription_expires_to_datetime([1, 2, 3])
        assert result is None

    def test_other_type_dict_returns_none(self):
        result = _subscription_expires_to_datetime({"ts": 123})
        assert result is None

    def test_zero_ts(self):
        result = _subscription_expires_to_datetime(0)
        assert result is None or isinstance(result, datetime)


class TestBuildUsersFilter:
    def test_no_args_returns_empty(self):
        conditions = _build_users_filter(None, None, None)
        assert conditions == []

    def test_search_adds_condition(self):
        conditions = _build_users_filter("alice", None, None)
        assert len(conditions) == 1

    def test_user_type_all_skipped(self):
        conditions = _build_users_filter(None, "all", None)
        assert len(conditions) == 0

    def test_user_type_specific_adds_condition(self):
        conditions = _build_users_filter(None, "premium", None)
        assert len(conditions) == 1

    def test_status_filter_expired(self):
        conditions = _build_users_filter(None, None, "expired")
        assert len(conditions) == 1

    def test_status_filter_expiring_soon(self):
        conditions = _build_users_filter(None, None, "expiring_soon")
        assert len(conditions) == 1

    def test_status_filter_active(self):
        conditions = _build_users_filter(None, None, "active")
        assert len(conditions) == 1

    def test_multiple_filters_combined(self):
        conditions = _build_users_filter("bob", "premium", "active")
        assert len(conditions) == 3

    def test_unknown_status_filter_no_condition(self):
        conditions = _build_users_filter(None, None, "unknown_status")
        assert len(conditions) == 0

    def test_empty_search_string_no_condition(self):
        conditions = _build_users_filter("", None, None)
        assert len(conditions) == 0


def _make_mock_user(**kwargs):
    defaults = {
        "id": 1,
        "username": "testuser",
        "email": "test@example.com",
        "role": "user",
        "user_type": "free",
        "subscription_start": None,
        "subscription_expires": None,
        "remaining_calculations": 10,
        "logistics_templates_limit": 5,
        "is_auto_renew": 0,
        "created_at": "2025-01-01 00:00:00",
        "last_login": None,
        "is_frozen": 0,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class TestFormatUserRow:
    def test_returns_dict_with_expected_keys(self):
        user = _make_mock_user()
        row = _format_user_row(user, {})  # type: ignore[arg-type]
        expected_keys = {
            "id",
            "username",
            "email",
            "role",
            "user_type",
            "subscription_start",
            "subscription_end",
            "remaining_days",
            "remaining_calculations",
            "logistics_templates_limit",
            "current_logistics_count",
            "is_auto_renew",
            "created_at",
            "last_login",
            "is_frozen",
        }
        assert expected_keys.issubset(set(row.keys()))

    def test_subscription_expires_none(self):
        user = _make_mock_user(subscription_expires=None)
        row = _format_user_row(user, {})  # type: ignore[arg-type]
        assert row["subscription_end"] is None
        assert row["remaining_days"] is None

    def test_subscription_expires_present(self):
        future_ts = int(time.time()) + 30 * 24 * 3600
        user = _make_mock_user(subscription_expires=future_ts)
        row = _format_user_row(user, {user.id: 3})  # type: ignore[arg-type]
        assert row["subscription_end"] is not None
        assert isinstance(row["remaining_days"], int)
        assert row["current_logistics_count"] == 3

    def test_logistics_count_default_zero(self):
        user = _make_mock_user()
        row = _format_user_row(user, {})  # type: ignore[arg-type]
        assert row["current_logistics_count"] == 0

    def test_logistics_count_from_dict(self):
        user = _make_mock_user(id=42)
        row = _format_user_row(user, {42: 7})  # type: ignore[arg-type]
        assert row["current_logistics_count"] == 7


class TestFormatAuditLogRows:
    def _make_row(self, **kwargs):
        defaults = {
            "id": 1,
            "admin_id": 10,
            "user_id": 20,
            "action": "freeze_user",
            "details": "some detail",
            "timestamp": datetime(2025, 1, 1, 12, 0, 0),
            "admin_username": "admin1",
            "user_username": "user1",
        }
        defaults.update(kwargs)
        return SimpleNamespace(**defaults)

    def test_empty_list_returns_empty(self):
        assert _format_audit_log_rows([]) == []

    def test_single_row_returns_list_with_dict(self):
        row = self._make_row()
        result = _format_audit_log_rows([row])
        assert len(result) == 1
        r = result[0]
        assert r["id"] == 1
        assert r["admin_id"] == 10
        assert r["user_id"] == 20
        assert r["action"] == "freeze_user"
        assert r["details"] == "some detail"
        assert r["admin_username"] == "admin1"
        assert r["user_username"] == "user1"

    def test_multiple_rows(self):
        rows = [self._make_row(id=i) for i in range(5)]
        result = _format_audit_log_rows(rows)
        assert len(result) == 5

    def test_row_without_username_attrs(self):
        row = SimpleNamespace(
            id=1, admin_id=10, user_id=20, action="test", details="d", timestamp=None
        )
        result = _format_audit_log_rows([row])
        assert result[0]["admin_username"] is None
        assert result[0]["user_username"] is None


class TestAuthenticateAdmin:
    async def test_success(self, db_session, test_admin):
        from db.admin import authenticate_admin

        result = await authenticate_admin(
            db_session, test_admin["username"], test_admin["password"]
        )
        assert result is not None
        assert result["username"] == test_admin["username"]
        assert result["role"] == "admin"
        assert "id" in result
        assert "email" in result

    async def test_wrong_password_returns_none(self, db_session, test_admin):
        from db.admin import authenticate_admin

        result = await authenticate_admin(
            db_session, test_admin["username"], "WrongPassword123"
        )
        assert result is None

    async def test_not_admin_role_returns_none(self, db_session, test_user):
        from db.admin import authenticate_admin

        result = await authenticate_admin(
            db_session, test_user["username"], test_user["password"]
        )
        assert result is None

    async def test_user_not_found_returns_none(self, db_session):
        from db.admin import authenticate_admin

        result = await authenticate_admin(
            db_session, "no_such_user_xyz_999", "password"
        )
        assert result is None

    async def test_bcrypt_value_error_returns_none(self, db_session, test_admin):
        from db.admin import authenticate_admin

        with patch("db.admin.bcrypt.checkpw", side_effect=ValueError("bad hash")):
            result = await authenticate_admin(
                db_session, test_admin["username"], test_admin["password"]
            )
        assert result is None


class TestGetAllUsers:
    async def test_returns_paginated_dict(self, db_session, test_user):
        from db.admin import get_all_users

        result = await get_all_users(db_session)
        assert "users" in result
        assert "total_count" in result
        assert "total_pages" in result
        assert "current_page" in result
        assert isinstance(result["users"], list)
        assert result["total_count"] >= 1

    async def test_search_filter(self, db_session, test_user):
        from db.admin import get_all_users

        result = await get_all_users(db_session, search=test_user["username"])
        usernames = [u["username"] for u in result["users"]]
        assert test_user["username"] in usernames

    async def test_search_no_match(self, db_session, test_user):
        from db.admin import get_all_users

        result = await get_all_users(db_session, search="zzz_impossible_xyz_9999")
        assert result["total_count"] == 0

    async def test_user_type_filter(self, db_session, test_user):
        from db.admin import get_all_users

        result = await get_all_users(db_session, user_type_filter="free")
        assert isinstance(result["users"], list)

    async def test_user_type_filter_all(self, db_session, test_user):
        from db.admin import get_all_users

        result = await get_all_users(db_session, user_type_filter="all")
        assert result["total_count"] >= 1

    async def test_pagination_page2(self, db_session, test_user):
        from db.admin import get_all_users

        result = await get_all_users(db_session, page=2, per_page=1)
        assert result["current_page"] == 2

    async def test_status_filter_expired(self, db_session, test_user):
        from db.admin import get_all_users

        result = await get_all_users(db_session, status_filter="expired")
        assert isinstance(result["users"], list)

    async def test_status_filter_active(self, db_session, test_user):
        from db.admin import get_all_users

        result = await get_all_users(db_session, status_filter="active")
        assert isinstance(result["users"], list)

    async def test_status_filter_expiring_soon(self, db_session, test_user):
        from db.admin import get_all_users

        result = await get_all_users(db_session, status_filter="expiring_soon")
        assert isinstance(result["users"], list)


class TestGetUserDetail:
    async def test_found_returns_dict(self, db_session, test_user):
        from db.admin import get_user_detail

        result = await get_user_detail(db_session, test_user["id"])
        assert result is not None
        assert result["id"] == test_user["id"]
        assert result["username"] == test_user["username"]

    async def test_not_found_returns_none(self, db_session):
        from db.admin import get_user_detail

        result = await get_user_detail(db_session, 999999999)
        assert result is None

    async def test_all_expected_keys(self, db_session, test_user):
        from db.admin import get_user_detail

        result = await get_user_detail(db_session, test_user["id"])
        expected = {
            "id",
            "username",
            "email",
            "role",
            "user_type",
            "subscription_start",
            "subscription_end",
            "remaining_days",
            "remaining_calculations",
            "logistics_templates_limit",
            "current_logistics_count",
            "products_count",
            "is_auto_renew",
            "created_at",
            "last_login",
            "is_frozen",
        }
        assert expected.issubset(set(result.keys()))

    async def test_subscription_expires_none(self, db_session, test_user):
        from db.admin import get_user_detail

        result = await get_user_detail(db_session, test_user["id"])
        assert result["subscription_end"] is None
        assert result["remaining_days"] is None

    async def test_subscription_expires_present(self, db_session, test_user):
        from db.admin import get_user_detail
        from models.user import User

        user = await db_session.get(User, test_user["id"])
        future_ts = int(time.time()) + 30 * 24 * 3600
        user.subscription_expires = future_ts
        await db_session.flush()
        result = await get_user_detail(db_session, test_user["id"])
        assert result["subscription_end"] is not None
        assert isinstance(result["remaining_days"], int)


class TestUpdateUserSubscriptionAdmin:
    async def test_success_with_allowed_field(self, db_session, test_user, test_admin):
        from db.admin import update_user_subscription_admin

        result = await update_user_subscription_admin(
            db_session,
            test_user["id"],
            {"remaining_calculations": 50},
            test_admin["id"],
        )
        assert result is True

    async def test_user_not_found(self, db_session, test_admin):
        from db.admin import update_user_subscription_admin

        result = await update_user_subscription_admin(
            db_session, 999999999, {"remaining_calculations": 50}, test_admin["id"]
        )
        assert result is False

    async def test_no_valid_changes(self, db_session, test_user, test_admin):
        from db.admin import update_user_subscription_admin

        result = await update_user_subscription_admin(
            db_session,
            test_user["id"],
            {"invalid_field": "value"},
            test_admin["id"],
        )
        assert result is False

    async def test_subscription_end_field(self, db_session, test_user, test_admin):
        from db.admin import update_user_subscription_admin

        result = await update_user_subscription_admin(
            db_session,
            test_user["id"],
            {"subscription_end": "2026-12-31"},
            test_admin["id"],
        )
        assert result is True

    async def test_subscription_end_invalid_value(
        self, db_session, test_user, test_admin
    ):
        from db.admin import update_user_subscription_admin

        result = await update_user_subscription_admin(
            db_session,
            test_user["id"],
            {"subscription_end": "not-a-date"},
            test_admin["id"],
        )
        assert result is False

    async def test_multiple_allowed_fields(self, db_session, test_user, test_admin):
        from db.admin import update_user_subscription_admin

        result = await update_user_subscription_admin(
            db_session,
            test_user["id"],
            {"user_type": "premium", "is_frozen": 0, "is_auto_renew": 1},
            test_admin["id"],
        )
        assert result is True


class TestFreezeUser:
    async def test_success(self, db_session, test_user, test_admin):
        from db.admin import freeze_user
        from models.user import User

        result = await freeze_user(db_session, test_user["id"], test_admin["id"])
        assert result is True
        user = await db_session.get(User, test_user["id"])
        assert user.is_frozen == 1

    async def test_not_found(self, db_session, test_admin):
        from db.admin import freeze_user

        result = await freeze_user(db_session, 999999999, test_admin["id"])
        assert result is False


class TestUnfreezeUser:
    async def test_success(self, db_session, test_user, test_admin):
        from db.admin import unfreeze_user
        from models.user import User

        result = await unfreeze_user(db_session, test_user["id"], test_admin["id"])
        assert result is True
        user = await db_session.get(User, test_user["id"])
        assert user.is_frozen == 0

    async def test_not_found(self, db_session, test_admin):
        from db.admin import unfreeze_user

        result = await unfreeze_user(db_session, 999999999, test_admin["id"])
        assert result is False


class TestDeleteUserAdmin:
    async def test_not_found(self, db_session, test_admin):
        from db.admin import delete_user_admin

        result = await delete_user_admin(db_session, 999999999, test_admin["id"])
        assert result is False

    async def test_admin_can_be_deleted(self, db_session, test_admin):
        from db.admin import delete_user_admin
        from models.user import User

        tmp_admin = User(
            username=f"tmp_admin_del_{int(time.time() * 1000)}",
            password="hashed",
            role="admin",
            user_type="free",
            subscription_type="free",
            remaining_calculations=10,
            created_at=time.strftime("%Y-%m-%d %H:%M:%S"),
            is_test_user=1,
        )
        db_session.add(tmp_admin)
        await db_session.flush()
        await db_session.commit()
        tmp_id = tmp_admin.id

        result = await delete_user_admin(db_session, tmp_id, test_admin["id"])
        assert result is True

    async def test_success_deletes_user(self, db_session, test_admin):
        from db.admin import delete_user_admin
        from models.user import User

        tmp_user = User(
            username=f"tmp_del_{int(time.time() * 1000)}",
            password="hashed",
            role="user",
            user_type="free",
            subscription_type="free",
            remaining_calculations=10,
            created_at=time.strftime("%Y-%m-%d %H:%M:%S"),
            is_test_user=1,
        )
        db_session.add(tmp_user)
        await db_session.flush()
        await db_session.commit()
        tmp_id = tmp_user.id

        result = await delete_user_admin(db_session, tmp_id, test_admin["id"])
        assert result is True


class TestAdjustCalculations:
    async def test_atomic_update_adds_delta(self, db_session, test_user):
        from db.admin import adjust_calculations
        from models.user import User

        user = await db_session.get(User, test_user["id"])
        user.remaining_calculations = 7
        await db_session.commit()

        ok = await adjust_calculations(db_session, test_user["id"], 5)
        await db_session.commit()

        assert ok is True
        value = (
            await db_session.execute(
                select(User.remaining_calculations)
                .where(User.id == test_user["id"])
            )
        ).scalar_one()
        assert value == 12

    async def test_atomic_update_floors_at_zero(self, db_session, test_user):
        from db.admin import adjust_calculations
        from models.user import User

        user = await db_session.get(User, test_user["id"])
        user.remaining_calculations = 3
        await db_session.commit()

        ok = await adjust_calculations(db_session, test_user["id"], -99)
        await db_session.commit()

        assert ok is True
        value = (
            await db_session.execute(
                select(User.remaining_calculations)
                .where(User.id == test_user["id"])
            )
        ).scalar_one()
        assert value == 0

    async def test_atomic_update_matches_raw_returning_sql(
        self,
        db_session,
        test_user,
    ):
        from models.user import User

        await db_session.execute(
            text(
                """
                UPDATE users
                SET remaining_calculations = 2
                WHERE id = :user_id
                """
            ),
            {"user_id": test_user["id"]},
        )
        await db_session.commit()

        result = await db_session.execute(
            text(
                """
                UPDATE users
                SET remaining_calculations = GREATEST(
                    0,
                    COALESCE(remaining_calculations, 0) + :delta
                )
                WHERE id = :user_id
                RETURNING remaining_calculations
                """
            ),
            {"user_id": test_user["id"], "delta": -5},
        )
        await db_session.commit()

        assert result.scalar_one() == 0

    async def test_missing_user_returns_false(self, db_session):
        from db.admin import adjust_calculations

        assert await adjust_calculations(db_session, 999999999, 1) is False


class TestBatchUpdateUsers:
    async def test_success_count(self, db_session, test_user, test_admin):
        from db.admin import batch_update_users

        count = await batch_update_users(
            db_session,
            [test_user["id"]],
            {"remaining_calculations": 99},
            test_admin["id"],
        )
        assert count == 1

    async def test_skips_missing_users(self, db_session, test_user, test_admin):
        from db.admin import batch_update_users

        count = await batch_update_users(
            db_session,
            [test_user["id"], 999999999],
            {"remaining_calculations": 88},
            test_admin["id"],
        )
        assert count == 1

    async def test_subscription_end_handling(self, db_session, test_user, test_admin):
        from db.admin import batch_update_users

        count = await batch_update_users(
            db_session,
            [test_user["id"]],
            {"subscription_end": "2027-01-01"},
            test_admin["id"],
        )
        assert count == 1

    async def test_no_valid_fields_count_zero(self, db_session, test_user, test_admin):
        from db.admin import batch_update_users

        count = await batch_update_users(
            db_session,
            [test_user["id"]],
            {"totally_invalid_field": "xyz"},
            test_admin["id"],
        )
        assert count == 0

    async def test_empty_user_ids(self, db_session, test_admin):
        from db.admin import batch_update_users

        count = await batch_update_users(
            db_session, [], {"remaining_calculations": 5}, test_admin["id"]
        )
        assert count == 0

    async def test_subscription_end_invalid_no_count(
        self, db_session, test_user, test_admin
    ):
        from db.admin import batch_update_users

        count = await batch_update_users(
            db_session,
            [test_user["id"]],
            {"subscription_end": "not-a-valid-date"},
            test_admin["id"],
        )
        assert count == 0


class TestGetAuditLogs:
    async def _create_audit_log(self, db_session, admin_id, user_id, action):
        from models.log import AuditLog

        log = AuditLog(
            admin_id=admin_id, user_id=user_id, action=action, details="test detail"
        )
        db_session.add(log)
        await db_session.flush()
        return log

    async def test_basic_returns_structure(self, db_session, test_admin, test_user):
        from db.admin import get_audit_logs

        await self._create_audit_log(
            db_session, test_admin["id"], test_user["id"], "test_action"
        )
        with patch("db.admin.format_audit_log_rows", return_value=[{"mocked": True}]):
            result = await get_audit_logs(db_session)
        assert "logs" in result
        assert "total_count" in result
        assert "total_pages" in result
        assert "current_page" in result
        assert isinstance(result["logs"], list)

    async def test_filter_by_admin_id(self, db_session, test_admin, test_user):
        from db.admin import get_audit_logs

        await self._create_audit_log(
            db_session, test_admin["id"], test_user["id"], "admin_filter_action"
        )
        with patch("db.admin.format_audit_log_rows", return_value=[]):
            result = await get_audit_logs(db_session, admin_id=test_admin["id"])
        assert result["total_count"] >= 1

    async def test_filter_by_user_id(self, db_session, test_admin, test_user):
        from db.admin import get_audit_logs

        await self._create_audit_log(
            db_session, test_admin["id"], test_user["id"], "user_filter_action"
        )
        with patch("db.admin.format_audit_log_rows", return_value=[]):
            result = await get_audit_logs(db_session, user_id=test_user["id"])
        assert result["total_count"] >= 1

    async def test_filter_by_action(self, db_session, test_admin, test_user):
        from db.admin import get_audit_logs

        await self._create_audit_log(
            db_session, test_admin["id"], test_user["id"], "unique_action_xyz"
        )
        with patch("db.admin.format_audit_log_rows", return_value=[]):
            result = await get_audit_logs(db_session, action="unique_action_xyz")
        assert result["total_count"] >= 1

    async def test_pagination(self, db_session, test_admin, test_user):
        from db.admin import get_audit_logs

        await self._create_audit_log(
            db_session, test_admin["id"], test_user["id"], "pagination_test_action"
        )
        with patch("db.admin.format_audit_log_rows", return_value=[]):
            result = await get_audit_logs(db_session, page=1, per_page=5)
        assert result["current_page"] == 1

    async def test_no_match_filter(self, db_session):
        from db.admin import get_audit_logs

        result = await get_audit_logs(db_session, action="no_such_action_zzz_999")
        assert result["total_count"] == 0
        assert result["logs"] == []


class TestResetUserPassword:
    async def test_success_returns_12_char_string(
        self, db_session, test_user, test_admin
    ):
        from db.admin import reset_user_password

        result = await reset_user_password(
            db_session, test_user["id"], test_admin["id"]
        )
        assert result is not None
        assert isinstance(result, str)
        assert len(result) == 12

    async def test_not_found_returns_none(self, db_session, test_admin):
        from db.admin import reset_user_password

        result = await reset_user_password(db_session, 999999999, test_admin["id"])
        assert result is None

    async def test_password_is_alphanumeric(self, db_session, test_user, test_admin):
        from db.admin import reset_user_password

        result = await reset_user_password(
            db_session, test_user["id"], test_admin["id"]
        )
        assert result.isalnum()

    async def test_new_password_hashed_in_db(self, db_session, test_user, test_admin):
        import bcrypt as _bcrypt
        from db.admin import reset_user_password
        from models.user import User

        new_pass = await reset_user_password(
            db_session, test_user["id"], test_admin["id"]
        )
        user = await db_session.get(User, test_user["id"])
        assert _bcrypt.checkpw(new_pass.encode("utf-8"), user.password.encode("utf-8"))
