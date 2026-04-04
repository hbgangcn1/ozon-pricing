"""
tests/test_db_utils_coverage_c.py

Admin functions, user management, and logging coverage tests.
Uses only unittest.mock - NO real database connections.
Target lines: 2148-3360 of db_utils.py
"""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock, call
from contextlib import contextmanager

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _make_ctx(conn=None, cursor=None):
    """Helper: build a context manager returning (conn, cursor)."""
    if conn is None:
        conn = MagicMock()
    if cursor is None:
        cursor = MagicMock()
    conn.commit = MagicMock()
    conn.rollback = MagicMock()
    cursor.rowcount = 1

    @contextmanager
    def _ctx():
        yield conn, cursor

    return _ctx(), conn, cursor


# ---------------------------------------------------------------------------
# decrement_user_calculations
# ---------------------------------------------------------------------------


class TestDecrementUserCalculations(unittest.TestCase):
    @patch("db_utils.get_db_connection")
    def test_user_not_found_returns_false(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        with (
            patch.object(db_utils, "_safe_execute_fetchone", return_value=None),
            patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s),
        ):
            result = db_utils.decrement_user_calculations(999)
        self.assertFalse(result)

    @patch("db_utils.get_db_connection")
    def test_admin_user_returns_true(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        with (
            patch.object(
                db_utils, "_safe_execute_fetchone", return_value=("user", "admin", 100)
            ),
            patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s),
        ):
            result = db_utils.decrement_user_calculations(1)
        self.assertTrue(result)

    @patch("db_utils.get_db_connection")
    def test_permanent_user_returns_true(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        with (
            patch.object(
                db_utils,
                "_safe_execute_fetchone",
                return_value=("user", "permanent", 0),
            ),
            patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s),
        ):
            result = db_utils.decrement_user_calculations(1)
        self.assertTrue(result)

    @patch("db_utils.get_db_connection")
    def test_test_user_returns_true(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        with (
            patch.object(
                db_utils, "_safe_execute_fetchone", return_value=("user", "test", 5)
            ),
            patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s),
        ):
            result = db_utils.decrement_user_calculations(1)
        self.assertTrue(result)

    @patch("db_utils.get_db_connection")
    def test_free_user_no_remaining_returns_false(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        with (
            patch.object(
                db_utils, "_safe_execute_fetchone", return_value=("free", "free", 0)
            ),
            patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s),
        ):
            result = db_utils.decrement_user_calculations(1)
        self.assertFalse(result)

    @patch("db_utils.get_db_connection")
    def test_free_user_with_remaining_decrements(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        cur.rowcount = 1
        with (
            patch.object(
                db_utils, "_safe_execute_fetchone", return_value=("free", "free", 5)
            ),
            patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s),
        ):
            result = db_utils.decrement_user_calculations(1)
        self.assertTrue(result)

    @patch("db_utils.get_db_connection")
    def test_monthly_user_no_remaining_returns_false(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        with (
            patch.object(
                db_utils,
                "_safe_execute_fetchone",
                return_value=("monthly", "monthly", 0),
            ),
            patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s),
        ):
            result = db_utils.decrement_user_calculations(1)
        self.assertFalse(result)

    @patch("db_utils.get_db_connection")
    def test_monthly_user_with_remaining_decrements(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        cur.rowcount = 1
        with (
            patch.object(
                db_utils,
                "_safe_execute_fetchone",
                return_value=("monthly", "monthly", 3),
            ),
            patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s),
        ):
            result = db_utils.decrement_user_calculations(1)
        self.assertTrue(result)

    @patch("db_utils.get_db_connection")
    def test_unknown_user_type_returns_false(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        with (
            patch.object(
                db_utils,
                "_safe_execute_fetchone",
                return_value=("unknown_type", None, 5),
            ),
            patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s),
        ):
            result = db_utils.decrement_user_calculations(1)
        self.assertFalse(result)


# ---------------------------------------------------------------------------
# reset_free_users_daily_calculations
# ---------------------------------------------------------------------------


class TestResetFreeUsersDailyCalculations(unittest.TestCase):
    @patch("db_utils.get_db_connection")
    def test_reset_success(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        cur.rowcount = 5
        mock_gdc.return_value = ctx
        mock_logger_mod = MagicMock()
        mock_logger_mod.logger = MagicMock()
        with patch.dict("sys.modules", {"logger_config": mock_logger_mod}):
            result = db_utils.reset_free_users_daily_calculations()
        self.assertEqual(result, 5)

    @patch("db_utils.get_db_connection")
    def test_reset_exception_returns_zero(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        cur.execute.side_effect = Exception("DB error")
        mock_gdc.return_value = ctx
        mock_logger_mod = MagicMock()
        with patch.dict("sys.modules", {"logger_config": mock_logger_mod}):
            result = db_utils.reset_free_users_daily_calculations()
        self.assertEqual(result, 0)


# ---------------------------------------------------------------------------
# update_user_password
# ---------------------------------------------------------------------------


class TestUpdateUserPassword(unittest.TestCase):
    @patch("db_utils.get_db_connection")
    def test_user_not_found_returns_false(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        with (
            patch.object(db_utils, "_safe_execute_fetchone", return_value=None),
            patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s),
        ):
            result = db_utils.update_user_password(999, "oldpw", "newpw")
        self.assertFalse(result)

    @patch("db_utils.get_db_connection")
    def test_wrong_bcrypt_password_returns_false(self, mock_gdc):
        import db_utils
        import bcrypt

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        real_hash = bcrypt.hashpw(b"correct", bcrypt.gensalt()).decode("utf-8")
        with (
            patch.object(db_utils, "_safe_execute_fetchone", return_value=(real_hash,)),
            patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s),
        ):
            result = db_utils.update_user_password(1, "wrongpw", "newpw")
        self.assertFalse(result)

    @patch("db_utils.get_db_connection")
    def test_correct_bcrypt_password_updates(self, mock_gdc):
        import db_utils
        import bcrypt

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        real_hash = bcrypt.hashpw(b"correct", bcrypt.gensalt()).decode("utf-8")
        with (
            patch.object(db_utils, "_safe_execute_fetchone", return_value=(real_hash,)),
            patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s),
        ):
            result = db_utils.update_user_password(1, "correct", "NewPass123!")
        self.assertTrue(result)

    @patch("db_utils.get_db_connection")
    def test_sha256_password_wrong_returns_false(self, mock_gdc):
        import db_utils
        import hashlib

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        sha_hash = hashlib.sha256(b"correct").hexdigest()
        with (
            patch.object(db_utils, "_safe_execute_fetchone", return_value=(sha_hash,)),
            patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s),
        ):
            result = db_utils.update_user_password(1, "wrong", "newpw")
        self.assertFalse(result)

    @patch("db_utils.get_db_connection")
    def test_sha256_password_correct_updates(self, mock_gdc):
        import db_utils
        import hashlib

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        sha_hash = hashlib.sha256(b"correct").hexdigest()
        with (
            patch.object(db_utils, "_safe_execute_fetchone", return_value=(sha_hash,)),
            patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s),
        ):
            result = db_utils.update_user_password(1, "correct", "NewPass123!")
        self.assertTrue(result)


# ---------------------------------------------------------------------------
# delete_user
# ---------------------------------------------------------------------------


class TestDeleteUser(unittest.TestCase):
    @patch("db_utils.get_db_connection")
    def test_user_not_found_returns_false(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        with patch.object(db_utils, "_safe_execute_fetchone", return_value=None):
            result = db_utils.delete_user(999)
        self.assertFalse(result)

    @patch("db_utils.get_db_connection")
    def test_admin_user_not_deleted(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        with patch.object(
            db_utils, "_safe_execute_fetchone", return_value=(1, "admin_user", "admin")
        ):
            result = db_utils.delete_user(1)
        self.assertFalse(result)

    @patch("db_utils.get_db_connection")
    def test_normal_user_deleted_successfully(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        cur.rowcount = 1
        with (
            patch.object(
                db_utils,
                "_safe_execute_fetchone",
                return_value=(5, "normal_user", "user"),
            ),
            patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s),
            patch.object(db_utils, "get_placeholder", return_value="?"),
        ):
            result = db_utils.delete_user(5)
        self.assertTrue(result)

    @patch("db_utils.get_db_connection")
    def test_delete_user_exception_returns_false(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        exec_count = [0]

        def execute_side_eff(*args, **kwargs):
            exec_count[0] += 1
            if exec_count[0] == 4:
                raise Exception("DB error mid-delete")

        cur.execute.side_effect = execute_side_eff

        with (
            patch.object(
                db_utils,
                "_safe_execute_fetchone",
                return_value=(5, "normal_user", "user"),
            ),
            patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s),
            patch.object(db_utils, "get_placeholder", return_value="?"),
        ):
            result = db_utils.delete_user(5)
        self.assertFalse(result)


# ---------------------------------------------------------------------------
# get_user_preferred_mode
# ---------------------------------------------------------------------------


class TestGetUserPreferredMode(unittest.TestCase):
    @patch("db_utils.get_db_connection")
    def test_returns_none_when_cursor_none(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx

        @contextmanager
        def ctx_none_cursor():
            yield conn, None

        mock_gdc.return_value = ctx_none_cursor()
        result = db_utils.get_user_preferred_mode(1)
        self.assertIsNone(result)

    @patch("db_utils.get_db_connection")
    def test_user_not_found_returns_none(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        cur.fetchone.return_value = None
        mock_gdc.return_value = ctx
        with patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s):
            result = db_utils.get_user_preferred_mode(999)
        self.assertIsNone(result)

    @patch("db_utils.get_db_connection")
    def test_returns_mode_from_tuple(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        cur.fetchone.return_value = ("fast",)
        mock_gdc.return_value = ctx
        with patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s):
            result = db_utils.get_user_preferred_mode(1)
        self.assertEqual(result, "fast")

    @patch("db_utils.get_db_connection")
    def test_returns_mode_from_dict(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        cur.fetchone.return_value = {"preferred_mode": "complete"}
        mock_gdc.return_value = ctx
        with patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s):
            result = db_utils.get_user_preferred_mode(1)
        self.assertEqual(result, "complete")


# ---------------------------------------------------------------------------
# update_user_preferred_mode
# ---------------------------------------------------------------------------


class TestUpdateUserPreferredMode(unittest.TestCase):
    @patch("db_utils.get_db_connection")
    def test_update_succeeds(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        with patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s):
            db_utils.update_user_preferred_mode(1, "complete")
        cur.execute.assert_called_once()
        conn.commit.assert_called_once()


# ---------------------------------------------------------------------------
# migrate_user_preferences
# ---------------------------------------------------------------------------


class TestMigrateUserPreferences(unittest.TestCase):
    @patch("db_utils.get_db_connection")
    def test_column_already_exists_updates_nulls(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        # _get_table_columns returns list that includes 'preferred_mode'
        with patch.object(
            db_utils,
            "_get_table_columns",
            return_value=["id", "username", "preferred_mode"],
        ):
            # COUNT(*) returns 3 null users
            cur.fetchone.return_value = (3,)
            db_utils.migrate_user_preferences()
        conn.commit.assert_called()

    @patch("db_utils.get_db_connection")
    def test_column_missing_adds_column(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        with patch.object(
            db_utils, "_get_table_columns", return_value=["id", "username"]
        ):
            cur.fetchone.return_value = (0,)
            db_utils.migrate_user_preferences()
        # ALTER TABLE executed
        cur.execute.assert_called()

    @patch("db_utils.get_db_connection")
    def test_exception_handled(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        with patch.object(
            db_utils, "_get_table_columns", side_effect=Exception("error")
        ):
            # Should not raise
            db_utils.migrate_user_preferences()
        conn.rollback.assert_called()


# ---------------------------------------------------------------------------
# authenticate_admin
# ---------------------------------------------------------------------------


class TestAuthenticateAdmin(unittest.TestCase):
    @patch("db_utils.get_db_connection")
    def test_wrong_password_returns_none(self, mock_gdc):
        import db_utils
        import bcrypt

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        real_hash = bcrypt.hashpw(b"correct", bcrypt.gensalt()).decode("utf-8")
        cur.fetchone.return_value = (1, "admin", real_hash, "admin", "a@b.com")
        with (
            patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s),
            patch.object(db_utils, "_is_postgresql_connection", return_value=False),
        ):
            result = db_utils.authenticate_admin("admin", "wrong")
        self.assertIsNone(result)

    @patch("db_utils.get_db_connection")
    def test_no_user_returns_none(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        cur.fetchone.return_value = None
        with patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s):
            result = db_utils.authenticate_admin("nouser", "pw")
        self.assertIsNone(result)

    @patch("db_utils.get_db_connection")
    def test_correct_password_returns_dict(self, mock_gdc):
        import db_utils
        import bcrypt

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        real_hash = bcrypt.hashpw(b"correct", bcrypt.gensalt()).decode("utf-8")
        cur.fetchone.return_value = (1, "admin", real_hash, "admin", "a@b.com")
        with (
            patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s),
            patch.object(db_utils, "_is_postgresql_connection", return_value=False),
        ):
            result = db_utils.authenticate_admin("admin", "correct")
        self.assertIsNotNone(result)
        self.assertEqual(result["username"], "admin")


# ---------------------------------------------------------------------------
# get_all_users
# ---------------------------------------------------------------------------


class TestGetAllUsers(unittest.TestCase):
    @patch("db_utils.get_db_connection")
    def test_returns_users_list(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        # Count query returns 1
        # logistics count returns 0
        # users query returns 1 row
        from datetime import datetime

        user_row = (
            1,
            "user1",
            "u@e.com",
            "user",
            "free",
            "2024-01-01",
            None,
            5,
            10,
            0,
            "2024-01-01",
            None,
            0,
        )
        fetch_returns = iter(
            [
                (1,),  # total_count
                user_row,  # users fetchall -> use side_effect
                (0,),  # logistics count
            ]
        )

        cur.fetchone.side_effect = lambda: next(fetch_returns)
        cur.fetchall.return_value = [user_row]

        with (
            patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s),
            patch.object(
                db_utils,
                "_get_table_columns",
                return_value=["id", "username", "logistics_templates_limit"],
            ),
            patch.object(
                db_utils, "_subscription_expires_to_datetime", return_value=None
            ),
            patch("db_utils.build_where_clause", return_value=("1=1", []), create=True),
        ):
            try:
                from sql_security import build_where_clause
            except ImportError:
                pass
            with patch.dict(
                "sys.modules",
                {
                    "sql_security": MagicMock(
                        build_where_clause=lambda wc, p: ("1=1", p)
                    )
                },
            ):
                result = db_utils.get_all_users(page=1, per_page=20)
        self.assertIn("users", result)
        self.assertIn("total_count", result)

    @patch("db_utils.get_db_connection")
    def test_with_search_filter(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        cur.fetchone.return_value = (0,)
        cur.fetchall.return_value = []

        with (
            patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s),
            patch.object(
                db_utils, "_get_table_columns", return_value=["id", "username"]
            ),
            patch.dict(
                "sys.modules",
                {
                    "sql_security": MagicMock(
                        build_where_clause=lambda wc, p: ("1=1", p)
                    )
                },
            ),
        ):
            result = db_utils.get_all_users(
                search="test", user_type_filter="free", status_filter="expired"
            )
        self.assertIn("users", result)

    @patch("db_utils.get_db_connection")
    def test_with_expiring_soon_filter(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        cur.fetchone.return_value = (0,)
        cur.fetchall.return_value = []

        with (
            patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s),
            patch.object(
                db_utils, "_get_table_columns", return_value=["id", "username"]
            ),
            patch.dict(
                "sys.modules",
                {
                    "sql_security": MagicMock(
                        build_where_clause=lambda wc, p: ("1=1", p)
                    )
                },
            ),
        ):
            result = db_utils.get_all_users(status_filter="expiring_soon")
        self.assertIn("users", result)

    @patch("db_utils.get_db_connection")
    def test_with_active_filter(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        cur.fetchone.return_value = (0,)
        cur.fetchall.return_value = []

        with (
            patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s),
            patch.object(
                db_utils, "_get_table_columns", return_value=["id", "username"]
            ),
            patch.dict(
                "sys.modules",
                {
                    "sql_security": MagicMock(
                        build_where_clause=lambda wc, p: ("1=1", p)
                    )
                },
            ),
        ):
            result = db_utils.get_all_users(status_filter="active")
        self.assertIn("users", result)


if __name__ == "__main__":
    unittest.main()
