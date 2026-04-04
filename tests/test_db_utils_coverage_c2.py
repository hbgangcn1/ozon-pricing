"""
tests/test_db_utils_coverage_c2.py

User detail, admin subscription, freeze/unfreeze, batch ops,
audit logs, password reset, and logging coverage tests.
Uses only unittest.mock - NO real database connections.
Split from test_db_utils_coverage_c.py (was >800 lines).
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
# get_user_detail
# ---------------------------------------------------------------------------


class TestGetUserDetail(unittest.TestCase):
    @patch("db_utils.get_db_connection")
    def test_user_not_found_returns_none(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        cur.fetchone.return_value = None
        with patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s):
            result = db_utils.get_user_detail(999)
        self.assertIsNone(result)

    @patch("db_utils.get_db_connection")
    def test_user_found_returns_dict(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
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
        # fetchone: user, logistics count, products count
        fetch_iter = iter([user_row, (3,), (7,)])
        cur.fetchone.side_effect = lambda: next(fetch_iter)
        with (
            patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s),
            patch.object(
                db_utils, "_subscription_expires_to_datetime", return_value=None
            ),
        ):
            result = db_utils.get_user_detail(1)
        self.assertIsNotNone(result)
        self.assertEqual(result["username"], "user1")
        self.assertEqual(result["current_logistics_count"], 3)
        self.assertEqual(result["products_count"], 7)


# ---------------------------------------------------------------------------
# update_user_subscription_admin
# ---------------------------------------------------------------------------


class TestUpdateUserSubscriptionAdmin(unittest.TestCase):
    @patch("db_utils.get_db_connection")
    def test_delete_user_exception_returns_false(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        exec_count = [0]

        def execute_side_eff(*args, **kwargs):
            exec_count[0] += 1
            if exec_count[0] == 3:
                raise Exception("DB error on login_attempts delete")

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

    @patch("db_utils.get_db_connection")
    def test_update_user_type_success(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        cur.rowcount = 1
        mock_gdc.return_value = ctx
        with (
            patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s),
            patch.object(db_utils, "adapt_sql", side_effect=lambda s: s),
            patch.object(db_utils, "get_placeholder", return_value="?"),
            patch.object(db_utils, "log_admin_action", return_value=True),
        ):
            result = db_utils.update_user_subscription_admin(
                1, {"user_type": "monthly"}, 10
            )
        self.assertTrue(result)

    @patch("db_utils.get_db_connection")
    def test_update_subscription_end(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        cur.rowcount = 1
        mock_gdc.return_value = ctx
        with (
            patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s),
            patch.object(db_utils, "adapt_sql", side_effect=lambda s: s),
            patch.object(db_utils, "get_placeholder", return_value="?"),
            patch.object(
                db_utils, "_serialize_subscription_expires", return_value=9999999
            ),
            patch.object(db_utils, "log_admin_action", return_value=True),
        ):
            result = db_utils.update_user_subscription_admin(
                1, {"subscription_end": "2025-01-01"}, 10
            )
        self.assertTrue(result)

    @patch("db_utils.get_db_connection")
    def test_no_rows_updated_returns_false(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        cur.rowcount = 0
        mock_gdc.return_value = ctx
        with (
            patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s),
            patch.object(db_utils, "adapt_sql", side_effect=lambda s: s),
            patch.object(db_utils, "get_placeholder", return_value="?"),
        ):
            result = db_utils.update_user_subscription_admin(
                999, {"user_type": "free"}, 10
            )
        self.assertFalse(result)

    @patch("db_utils.get_db_connection")
    def test_log_admin_action_exception_still_returns_true(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        cur.rowcount = 1
        mock_gdc.return_value = ctx
        with (
            patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s),
            patch.object(db_utils, "adapt_sql", side_effect=lambda s: s),
            patch.object(db_utils, "get_placeholder", return_value="?"),
            patch.object(
                db_utils, "log_admin_action", side_effect=Exception("log error")
            ),
        ):
            result = db_utils.update_user_subscription_admin(
                1, {"user_type": "monthly"}, 10
            )
        self.assertTrue(result)


# ---------------------------------------------------------------------------
# freeze_user / unfreeze_user
# ---------------------------------------------------------------------------


class TestFreezeUnfreezeUser(unittest.TestCase):
    @patch("db_utils.get_db_connection")
    def test_freeze_user_success(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        cur.rowcount = 1
        mock_gdc.return_value = ctx
        with (
            patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s),
            patch.object(db_utils, "_is_postgresql_connection", return_value=False),
            patch.object(db_utils, "log_admin_action", return_value=True),
        ):
            result = db_utils.freeze_user(5, 1)
        self.assertTrue(result)

    @patch("db_utils.get_db_connection")
    def test_freeze_user_no_rows_returns_false(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        cur.rowcount = 0
        mock_gdc.return_value = ctx
        with (
            patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s),
            patch.object(db_utils, "_is_postgresql_connection", return_value=False),
        ):
            result = db_utils.freeze_user(999, 1)
        self.assertFalse(result)

    @patch("db_utils.get_db_connection")
    def test_freeze_user_log_exception(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        cur.rowcount = 1
        mock_gdc.return_value = ctx
        with (
            patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s),
            patch.object(db_utils, "_is_postgresql_connection", return_value=False),
            patch.object(
                db_utils, "log_admin_action", side_effect=Exception("log fail")
            ),
        ):
            result = db_utils.freeze_user(5, 1)
        self.assertTrue(result)

    @patch("db_utils.get_db_connection")
    def test_unfreeze_user_success(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        cur.rowcount = 1
        mock_gdc.return_value = ctx
        with (
            patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s),
            patch.object(db_utils, "_is_postgresql_connection", return_value=False),
            patch.object(db_utils, "log_admin_action", return_value=True),
        ):
            result = db_utils.unfreeze_user(5, 1)
        self.assertTrue(result)

    @patch("db_utils.get_db_connection")
    def test_unfreeze_user_no_rows_returns_false(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        cur.rowcount = 0
        mock_gdc.return_value = ctx
        with (
            patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s),
            patch.object(db_utils, "_is_postgresql_connection", return_value=False),
        ):
            result = db_utils.unfreeze_user(999, 1)
        self.assertFalse(result)

    @patch("db_utils.get_db_connection")
    def test_unfreeze_user_log_exception(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        cur.rowcount = 1
        mock_gdc.return_value = ctx
        with (
            patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s),
            patch.object(db_utils, "_is_postgresql_connection", return_value=False),
            patch.object(
                db_utils, "log_admin_action", side_effect=Exception("log fail")
            ),
        ):
            result = db_utils.unfreeze_user(5, 1)
        self.assertTrue(result)

    @patch("db_utils.get_db_connection")
    def test_freeze_user_postgresql(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        cur.rowcount = 1
        mock_gdc.return_value = ctx
        with (
            patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s),
            patch.object(db_utils, "_is_postgresql_connection", return_value=True),
            patch.object(db_utils, "log_admin_action", return_value=True),
        ):
            result = db_utils.freeze_user(5, 1)
        self.assertTrue(result)


# ---------------------------------------------------------------------------
# delete_user_admin
# ---------------------------------------------------------------------------


class TestDeleteUserAdmin(unittest.TestCase):
    @patch("db_utils.get_db_connection")
    def test_admin_user_protected(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        with (
            patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s),
            patch.object(
                db_utils,
                "_safe_execute_fetchone",
                return_value=("admin", "admin_user"),
            ),
        ):
            result = db_utils.delete_user_admin(1, 10)
        self.assertFalse(result)

    @patch("db_utils.get_db_connection")
    def test_normal_user_deleted(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        cur.rowcount = 1
        mock_gdc.return_value = ctx
        fetch_iter = iter([("user", "normaluser"), ("normaluser",)])
        with (
            patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s),
            patch.object(
                db_utils,
                "_safe_execute_fetchone",
                side_effect=lambda *a, **kw: next(fetch_iter),
            ),
            patch.object(db_utils, "log_admin_action", return_value=True),
        ):
            result = db_utils.delete_user_admin(5, 10)
        self.assertTrue(result)

    @patch("db_utils.get_db_connection")
    def test_no_rows_deleted_returns_false(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        cur.rowcount = 0
        mock_gdc.return_value = ctx
        fetch_iter = iter([("user", "normaluser"), ("normaluser",)])
        with (
            patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s),
            patch.object(
                db_utils,
                "_safe_execute_fetchone",
                side_effect=lambda *a, **kw: next(fetch_iter),
            ),
        ):
            result = db_utils.delete_user_admin(99, 10)
        self.assertFalse(result)

    @patch("db_utils.get_db_connection")
    def test_log_exception_still_returns_true(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        cur.rowcount = 1
        mock_gdc.return_value = ctx
        fetch_iter = iter([None, None])
        with (
            patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s),
            patch.object(
                db_utils,
                "_safe_execute_fetchone",
                side_effect=lambda *a, **kw: next(fetch_iter),
            ),
            patch.object(
                db_utils,
                "log_admin_action",
                side_effect=Exception("log fail"),
            ),
        ):
            result = db_utils.delete_user_admin(5, 10)
        self.assertTrue(result)


# ---------------------------------------------------------------------------
# batch_update_users
# ---------------------------------------------------------------------------


class TestBatchUpdateUsers(unittest.TestCase):
    @patch("db_utils.get_db_connection")
    def test_batch_update_success(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        cur.rowcount = 1
        mock_gdc.return_value = ctx
        with (
            patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s),
            patch.object(db_utils, "adapt_sql", side_effect=lambda s: s),
            patch.object(db_utils, "get_placeholder", return_value="?"),
            patch.object(
                db_utils,
                "_serialize_subscription_expires",
                return_value=9999999,
            ),
        ):
            result = db_utils.batch_update_users(
                [1, 2, 3],
                {"user_type": "monthly", "subscription_end": "2025-01-01"},
                10,
            )
        self.assertEqual(result, 3)

    @patch("db_utils.get_db_connection")
    def test_batch_update_no_valid_fields(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        with patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s):
            result = db_utils.batch_update_users([1, 2], {}, 10)
        self.assertEqual(result, 0)

    @patch("db_utils.get_db_connection")
    def test_batch_update_partial_success(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        rowcount_iter = iter([1, 0, 1])
        type(cur).rowcount = property(lambda s: next(rowcount_iter, 0))
        mock_gdc.return_value = ctx
        with (
            patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s),
            patch.object(db_utils, "adapt_sql", side_effect=lambda s: s),
            patch.object(db_utils, "get_placeholder", return_value="?"),
        ):
            result = db_utils.batch_update_users([1, 2, 3], {"user_type": "free"}, 10)
        self.assertEqual(result, 2)


# ---------------------------------------------------------------------------
# get_audit_logs
# ---------------------------------------------------------------------------


class TestGetAuditLogs(unittest.TestCase):
    @patch("db_utils.get_db_connection")
    def test_returns_logs_no_filter(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        log_row = (
            1,
            1,
            2,
            "update_subscription",
            "details",
            "2024-01-01",
            "admin_user",
            "target_user",
        )
        cur.fetchone.return_value = (1,)
        cur.fetchall.return_value = [log_row]
        with patch.dict(
            "sys.modules",
            {"sql_security": MagicMock(build_where_clause=lambda wc, p: ("1=1", p))},
        ):
            result = db_utils.get_audit_logs()
        self.assertIn("logs", result)
        self.assertEqual(result["total_count"], 1)

    @patch("db_utils.get_db_connection")
    def test_returns_logs_with_filters(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        cur.fetchone.return_value = (0,)
        cur.fetchall.return_value = []
        with patch.dict(
            "sys.modules",
            {"sql_security": MagicMock(build_where_clause=lambda wc, p: ("1=1", p))},
        ):
            result = db_utils.get_audit_logs(
                admin_id=1, user_id=2, action="reset_password"
            )
        self.assertIn("logs", result)
        self.assertEqual(result["total_count"], 0)


# ---------------------------------------------------------------------------
# reset_user_password
# ---------------------------------------------------------------------------


class TestResetUserPassword(unittest.TestCase):
    @patch("db_utils.get_db_connection")
    def test_reset_success(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        cur.rowcount = 1
        mock_gdc.return_value = ctx
        with patch.object(db_utils, "log_admin_action", return_value=True):
            result = db_utils.reset_user_password(1, 10)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, str)
        self.assertEqual(len(result), 12)

    @patch("db_utils.get_db_connection")
    def test_reset_user_not_found_returns_none(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        cur.rowcount = 0
        mock_gdc.return_value = ctx
        result = db_utils.reset_user_password(999, 10)
        self.assertIsNone(result)

    @patch("db_utils.get_db_connection")
    def test_log_exception_still_returns_password(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        cur.rowcount = 1
        mock_gdc.return_value = ctx
        with patch.object(
            db_utils,
            "log_admin_action",
            side_effect=Exception("log fail"),
        ):
            result = db_utils.reset_user_password(1, 10)
        self.assertIsNotNone(result)


# ---------------------------------------------------------------------------
# log_user_login
# ---------------------------------------------------------------------------


class TestLogUserLogin(unittest.TestCase):
    @patch("db_utils.get_db_connection")
    def test_log_success(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        with patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s):
            result = db_utils.log_user_login(1, "127.0.0.1", "Mozilla/5.0")
        self.assertTrue(result)

    @patch("db_utils.get_db_connection")
    def test_log_mobile_device(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        with patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s):
            result = db_utils.log_user_login(
                1, "127.0.0.1", "Mozilla/5.0 Android Mobile"
            )
        self.assertTrue(result)

    @patch("db_utils.get_db_connection")
    def test_log_tablet_device(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        with patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s):
            result = db_utils.log_user_login(1, "127.0.0.1", "Mozilla/5.0 iPad Tablet")
        self.assertTrue(result)

    @patch("db_utils.get_db_connection")
    def test_duplicate_key_handled(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        cur.execute.side_effect = [
            Exception("duplicate key"),
            None,  # second execute (UPDATE) succeeds
        ]
        with patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s):
            result = db_utils.log_user_login(1, "127.0.0.1", None)
        self.assertTrue(result)

    @patch("db_utils.get_db_connection")
    def test_generic_exception_returns_false(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        cur.execute.side_effect = Exception("some other db error")
        with patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s):
            result = db_utils.log_user_login(1, "127.0.0.1", None)
        self.assertFalse(result)

    @patch("db_utils.get_db_connection")
    def test_no_user_agent_unknown_device(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        with patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s):
            result = db_utils.log_user_login(1)
        self.assertTrue(result)


# ---------------------------------------------------------------------------
# log_user_behavior
# ---------------------------------------------------------------------------


class TestLogUserBehavior(unittest.TestCase):
    @patch("db_utils.get_db_connection")
    def test_log_success(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        with patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s):
            result = db_utils.log_user_behavior(1, "calculation", "{}", "fast")
        self.assertTrue(result)

    @patch("db_utils.get_db_connection")
    def test_log_exception_returns_false(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        cur.execute.side_effect = Exception("DB error")
        with patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s):
            result = db_utils.log_user_behavior(1, "calculation")
        self.assertFalse(result)


# ---------------------------------------------------------------------------
# log_admin_action
# ---------------------------------------------------------------------------


class TestLogAdminAction(unittest.TestCase):
    @patch("db_utils.get_db_connection")
    def test_log_success(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        with patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s):
            result = db_utils.log_admin_action(
                admin_id=1,
                action_type="freeze_user",
                action_detail="froze user 5",
                target_user_id=5,
                target_type="user",
            )
        self.assertTrue(result)

    @patch("db_utils.get_db_connection")
    def test_log_exception_returns_false(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        cur.execute.side_effect = Exception("DB error")
        with patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s):
            result = db_utils.log_admin_action(
                admin_id=1, action_type="test", action_detail="d"
            )
        self.assertFalse(result)


# ---------------------------------------------------------------------------
# create_alert
# ---------------------------------------------------------------------------


class TestCreateAlert(unittest.TestCase):
    @patch("db_utils.get_db_connection")
    def test_create_alert_success(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        result = db_utils.create_alert(
            "high_error_rate",
            "critical",
            "Error rate exceeded 5%",
            threshold_value=5.0,
            actual_value=7.2,
        )
        self.assertTrue(result)

    @patch("db_utils.get_db_connection")
    def test_create_alert_exception_returns_false(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        cur.execute.side_effect = Exception("DB error")
        result = db_utils.create_alert("type", "level", "desc")
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
