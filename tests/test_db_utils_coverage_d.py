import sys
import os
import json
import unittest
from unittest.mock import patch, MagicMock
from contextlib import contextmanager
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _make_ctx(conn=None, cursor=None):
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


class TestConvertDecimalToFloat(unittest.TestCase):
    def test_decimal_converted(self):
        import db_utils

        result = db_utils._convert_decimal_to_float(Decimal("3.14"))
        self.assertAlmostEqual(result, 3.14)
        self.assertIsInstance(result, float)

    def test_dict_converted(self):
        import db_utils

        result = db_utils._convert_decimal_to_float({"a": Decimal("1.5"), "b": 2})
        self.assertAlmostEqual(result["a"], 1.5)
        self.assertEqual(result["b"], 2)

    def test_list_converted(self):
        import db_utils

        result = db_utils._convert_decimal_to_float([Decimal("1"), Decimal("2")])
        self.assertEqual(result, [1.0, 2.0])

    def test_tuple_converted(self):
        import db_utils

        result = db_utils._convert_decimal_to_float((Decimal("5"),))
        self.assertEqual(result, (5.0,))

    def test_plain_value_unchanged(self):
        import db_utils

        self.assertEqual(db_utils._convert_decimal_to_float(42), 42)
        self.assertEqual(db_utils._convert_decimal_to_float("hello"), "hello")
        self.assertIsNone(db_utils._convert_decimal_to_float(None))

    def test_nested_dict_list(self):
        import db_utils

        data = {"values": [Decimal("1"), Decimal("2")]}
        result = db_utils._convert_decimal_to_float(data)
        self.assertEqual(result["values"], [1.0, 2.0])


class TestGetStatisticsCache(unittest.TestCase):
    @patch("db_utils.get_db_connection")
    def test_cache_hit_returns_data(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        cache_data = {"key": "value", "count": 5}
        with (
            patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s),
            patch.object(
                db_utils,
                "_safe_execute_fetchone",
                return_value=(json.dumps(cache_data),),
            ),
        ):
            result = db_utils.get_statistics_cache("test_key")
        self.assertEqual(result, cache_data)

    @patch("db_utils.get_db_connection")
    def test_cache_miss_returns_none(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        with (
            patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s),
            patch.object(db_utils, "_safe_execute_fetchone", return_value=None),
        ):
            result = db_utils.get_statistics_cache("missing_key")
        self.assertIsNone(result)

    @patch("db_utils.get_db_connection")
    def test_exception_returns_none(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        with patch.object(
            db_utils, "_safe_adapt_sql", side_effect=Exception("DB error")
        ):
            result = db_utils.get_statistics_cache("key")
        self.assertIsNone(result)


class TestSetStatisticsCache(unittest.TestCase):
    @patch("db_utils.get_db_connection")
    def test_set_sqlite_success(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        with patch.object(db_utils, "_is_postgresql_connection", return_value=False):
            result = db_utils.set_statistics_cache(
                "my_key", {"a": 1, "b": 2.5}, ttl=300
            )
        self.assertTrue(result)

    @patch("db_utils.get_db_connection")
    def test_set_postgresql_success(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        with patch.object(db_utils, "_is_postgresql_connection", return_value=True):
            result = db_utils.set_statistics_cache(
                "pg_key", {"x": Decimal("1.5")}, ttl=600
            )
        self.assertTrue(result)

    @patch("db_utils.get_db_connection")
    def test_set_exception_returns_false(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        cur.execute.side_effect = Exception("DB error")
        with patch.object(db_utils, "_is_postgresql_connection", return_value=False):
            result = db_utils.set_statistics_cache("key", {"a": 1})
        self.assertFalse(result)


class TestClearExpiredCache(unittest.TestCase):
    @patch("db_utils.get_db_connection")
    def test_clears_and_returns_count(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        cur.rowcount = 3
        mock_gdc.return_value = ctx
        result = db_utils.clear_expired_cache()
        self.assertEqual(result, 3)

    @patch("db_utils.get_db_connection")
    def test_exception_returns_zero(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        cur.execute.side_effect = Exception("DB error")
        result = db_utils.clear_expired_cache()
        self.assertEqual(result, 0)


class TestClearAllStatisticsCache(unittest.TestCase):
    @patch("db_utils.get_db_connection")
    def test_clears_all(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        cur.rowcount = 10
        mock_gdc.return_value = ctx
        with patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s):
            result = db_utils.clear_all_statistics_cache()
        self.assertEqual(result, 10)

    @patch("db_utils.get_db_connection")
    def test_exception_returns_zero(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        with patch.object(
            db_utils, "_safe_adapt_sql", side_effect=Exception("DB error")
        ):
            result = db_utils.clear_all_statistics_cache()
        self.assertEqual(result, 0)


class TestGetDashboardStats(unittest.TestCase):
    @patch("db_utils.get_db_connection")
    @patch("db_utils.get_statistics_cache")
    def test_returns_cached_data(self, mock_cache, mock_gdc):
        import db_utils

        cached = {"active_users_today": 5, "cached": True}
        mock_cache.return_value = cached
        result = db_utils.get_dashboard_stats()
        self.assertEqual(result, cached)
        mock_gdc.assert_not_called()

    @patch("db_utils.set_statistics_cache")
    @patch("db_utils.get_statistics_cache")
    @patch("db_utils.get_db_connection")
    def test_fetches_data_from_db(self, mock_gdc, mock_cache_get, mock_cache_set):
        import db_utils

        mock_cache_get.return_value = None
        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx

        fetch_returns = iter(
            [
                (3,),
                (2,),
                (100,),
                (500.0,),
                (50.0,),
                (45.0,),
                (200.0,),
                (1,),
            ]
        )
        cur.fetchone.side_effect = lambda: next(fetch_returns)

        with (
            patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s),
            patch.object(db_utils, "_is_postgresql_connection", return_value=False),
            patch.object(
                db_utils,
                "_build_safe_timestamp_expr",
                return_value="created_at",
                create=True,
            ),
        ):
            result = db_utils.get_dashboard_stats()

        self.assertIn("active_users_today", result)
        self.assertIn("total_users", result)
        mock_cache_set.assert_called_once()

    @patch("db_utils.set_statistics_cache")
    @patch("db_utils.get_statistics_cache")
    @patch("db_utils.get_db_connection")
    def test_exception_returns_empty_dict(
        self, mock_gdc, mock_cache_get, mock_cache_set
    ):
        import db_utils

        mock_cache_get.return_value = None
        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        cur.execute.side_effect = Exception("DB error")
        with (
            patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s),
            patch.object(db_utils, "_is_postgresql_connection", return_value=False),
        ):
            result = db_utils.get_dashboard_stats()
        self.assertEqual(result, {})

    @patch("db_utils.set_statistics_cache")
    @patch("db_utils.get_statistics_cache")
    @patch("db_utils.get_db_connection")
    def test_fetches_postgresql_path(self, mock_gdc, mock_cache_get, mock_cache_set):
        import db_utils

        mock_cache_get.return_value = None
        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx

        fetch_returns = iter(
            [
                (3,),
                (2,),
                (100,),
                (500.0,),
                (50.0,),
                (45.0,),
                (200.0,),
                (1,),
            ]
        )
        cur.fetchone.side_effect = lambda: next(fetch_returns)

        with (
            patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s),
            patch.object(db_utils, "_is_postgresql_connection", return_value=True),
            patch.object(
                db_utils,
                "_build_safe_timestamp_expr",
                return_value="CAST(EXTRACT(EPOCH FROM created_at) AS BIGINT)",
                create=True,
            ),
        ):
            result = db_utils.get_dashboard_stats()

        self.assertIn("active_users_today", result)


class TestGetPlans(unittest.TestCase):
    @patch("db_utils.get_db_connection")
    def test_returns_all_plans(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        cur.description = [("id",), ("plan_code",), ("plan_name",)]
        cur.fetchall.return_value = [
            (1, "free", "Free Plan"),
            (2, "monthly", "Monthly"),
        ]
        result = db_utils.get_plans()
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["plan_code"], "free")

    @patch("db_utils.get_db_connection")
    def test_active_only_filter(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        cur.description = [("id",), ("plan_code",)]
        cur.fetchall.return_value = [(2, "monthly")]
        result = db_utils.get_plans(active_only=True)
        self.assertEqual(len(result), 1)

    @patch("db_utils.get_db_connection")
    def test_exclude_free(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        cur.description = [("id",), ("plan_code",)]
        cur.fetchall.return_value = [(2, "monthly")]
        result = db_utils.get_plans(include_free=False)
        self.assertEqual(len(result), 1)

    @patch("db_utils.get_db_connection")
    def test_exception_returns_empty_list(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        cur.execute.side_effect = Exception("DB error")
        result = db_utils.get_plans()
        self.assertEqual(result, [])


class TestGetPlanByCode(unittest.TestCase):
    @patch("db_utils.get_db_connection")
    def test_plan_found(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        cur.description = [("id",), ("plan_code",), ("plan_name",)]
        cur.fetchone.return_value = (1, "monthly", "Monthly Plan")
        with patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s):
            result = db_utils.get_plan_by_code("monthly")
        self.assertIsNotNone(result)
        self.assertEqual(result["plan_code"], "monthly")

    @patch("db_utils.get_db_connection")
    def test_plan_not_found_returns_none(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        cur.fetchone.return_value = None
        with patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s):
            result = db_utils.get_plan_by_code("nonexistent")
        self.assertIsNone(result)

    @patch("db_utils.get_db_connection")
    def test_exception_returns_none(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        with patch.object(
            db_utils, "_safe_adapt_sql", side_effect=Exception("DB error")
        ):
            result = db_utils.get_plan_by_code("monthly")
        self.assertIsNone(result)


class TestGetPlanById(unittest.TestCase):
    @patch("db_utils.get_db_connection")
    def test_plan_found(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        cur.description = [("id",), ("plan_code",)]
        cur.fetchone.return_value = (1, "monthly")
        with patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s):
            result = db_utils.get_plan_by_id(1)
        self.assertIsNotNone(result)

    @patch("db_utils.get_db_connection")
    def test_plan_not_found_returns_none(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        cur.fetchone.return_value = None
        with patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s):
            result = db_utils.get_plan_by_id(999)
        self.assertIsNone(result)

    @patch("db_utils.get_db_connection")
    def test_exception_returns_none(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        with patch.object(
            db_utils, "_safe_adapt_sql", side_effect=Exception("DB error")
        ):
            result = db_utils.get_plan_by_id(1)
        self.assertIsNone(result)


class TestCreatePlan(unittest.TestCase):
    @patch("db_utils.get_db_connection")
    def test_create_success(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        cur.execute.return_value = MagicMock(fetchone=lambda: None)
        cur.fetchone.return_value = None
        result = db_utils.create_plan(
            plan_code="enterprise",
            plan_name="Enterprise Plan",
            display_price_month=99.0,
            display_price_year=999.0,
            actual_price_month=79.0,
            actual_price_year=799.0,
        )
        self.assertTrue(result)

    @patch("db_utils.get_db_connection")
    def test_duplicate_code_returns_false(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        existing_mock = MagicMock()
        existing_mock.fetchone.return_value = (1,)
        cur.execute.return_value = existing_mock
        result = db_utils.create_plan(
            plan_code="free",
            plan_name="Free Plan",
            display_price_month=0.0,
            display_price_year=0.0,
            actual_price_month=0.0,
            actual_price_year=0.0,
        )
        self.assertFalse(result)

    @patch("db_utils.get_db_connection")
    def test_exception_returns_false(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        cur.execute.side_effect = Exception("DB error")
        result = db_utils.create_plan(
            plan_code="new",
            plan_name="New",
            display_price_month=1.0,
            display_price_year=10.0,
            actual_price_month=1.0,
            actual_price_year=10.0,
        )
        self.assertFalse(result)


class TestUpdatePlan(unittest.TestCase):
    @patch("db_utils.get_db_connection")
    def test_update_success(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        cur.rowcount = 1
        mock_gdc.return_value = ctx
        with (
            patch.object(db_utils, "_is_postgresql_connection", return_value=False),
            patch.object(db_utils, "adapt_sql", side_effect=lambda s: s),
            patch.object(db_utils, "get_placeholder", return_value="?"),
        ):
            result = db_utils.update_plan(1, plan_name="Updated Name")
        self.assertTrue(result)

    @patch("db_utils.get_db_connection")
    def test_no_valid_fields_returns_false(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        with (
            patch.object(db_utils, "_is_postgresql_connection", return_value=False),
            patch.object(db_utils, "adapt_sql", side_effect=lambda s: s),
            patch.object(db_utils, "get_placeholder", return_value="?"),
        ):
            result = db_utils.update_plan(1, invalid_field="x")
        self.assertFalse(result)

    @patch("db_utils.get_db_connection")
    def test_plan_not_found_returns_false(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        cur.rowcount = 0
        mock_gdc.return_value = ctx
        with (
            patch.object(db_utils, "_is_postgresql_connection", return_value=False),
            patch.object(db_utils, "adapt_sql", side_effect=lambda s: s),
            patch.object(db_utils, "get_placeholder", return_value="?"),
        ):
            result = db_utils.update_plan(999, plan_name="X")
        self.assertFalse(result)

    @patch("db_utils.get_db_connection")
    def test_exception_returns_false(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        cur.execute.side_effect = Exception("DB error")
        with (
            patch.object(db_utils, "_is_postgresql_connection", return_value=False),
            patch.object(db_utils, "adapt_sql", side_effect=lambda s: s),
            patch.object(db_utils, "get_placeholder", return_value="?"),
        ):
            result = db_utils.update_plan(1, plan_name="X")
        self.assertFalse(result)

    @patch("db_utils.get_db_connection")
    def test_update_postgresql_path(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        cur.rowcount = 1
        mock_gdc.return_value = ctx
        with (
            patch.object(db_utils, "_is_postgresql_connection", return_value=True),
            patch.object(db_utils, "adapt_sql", side_effect=lambda s: s),
            patch.object(db_utils, "get_placeholder", return_value="%s"),
        ):
            result = db_utils.update_plan(1, plan_name="PG Name")
        self.assertTrue(result)


class TestDeletePlan(unittest.TestCase):
    @patch("db_utils.get_db_connection")
    def test_delete_success(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        cur.rowcount = 1
        mock_gdc.return_value = ctx
        plan_mock = MagicMock()
        plan_mock.fetchone.return_value = (1, "monthly")
        cur.execute.return_value = plan_mock
        with patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s):
            result = db_utils.delete_plan(1)
        self.assertTrue(result)

    @patch("db_utils.get_db_connection")
    def test_free_plan_not_deleted(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        plan_mock = MagicMock()
        plan_mock.fetchone.return_value = ("free",)
        cur.execute.return_value = plan_mock
        with patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s):
            result = db_utils.delete_plan(1)
        self.assertFalse(result)

    @patch("db_utils.get_db_connection")
    def test_plan_not_found_returns_false(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        cur.rowcount = 0
        mock_gdc.return_value = ctx
        plan_mock = MagicMock()
        plan_mock.fetchone.return_value = None
        cur.execute.return_value = plan_mock
        with patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s):
            result = db_utils.delete_plan(999)
        self.assertFalse(result)

    @patch("db_utils.get_db_connection")
    def test_exception_returns_false(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        cur.execute.side_effect = Exception("DB error")
        with patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s):
            result = db_utils.delete_plan(1)
        self.assertFalse(result)


class TestTogglePlanActive(unittest.TestCase):
    @patch("db_utils.get_db_connection")
    def test_toggle_success(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        cur.rowcount = 1
        mock_gdc.return_value = ctx
        result = db_utils.toggle_plan_active(1)
        self.assertTrue(result)

    @patch("db_utils.get_db_connection")
    def test_toggle_not_found_returns_false(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        cur.rowcount = 0
        mock_gdc.return_value = ctx
        result = db_utils.toggle_plan_active(999)
        self.assertFalse(result)

    @patch("db_utils.get_db_connection")
    def test_toggle_exception_returns_false(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        cur.execute.side_effect = Exception("DB error")
        result = db_utils.toggle_plan_active(1)
        self.assertFalse(result)


class TestGetPlanPrice(unittest.TestCase):
    def test_plan_not_found_returns_zero(self):
        import db_utils

        with patch.object(db_utils, "get_plan_by_code", return_value=None):
            result = db_utils.get_plan_price("nonexistent", "month")
        self.assertEqual(result, 0)

    def test_test_price_year(self):
        import db_utils

        plan = {
            "test_price_year": 9.9,
            "test_price_month": 0.99,
            "actual_price_year": 99.0,
            "actual_price_month": 9.9,
        }
        with patch.object(db_utils, "get_plan_by_code", return_value=plan):
            result = db_utils.get_plan_price("monthly", "year", use_test_price=True)
        self.assertAlmostEqual(result, 9.9)

    def test_test_price_month(self):
        import db_utils

        plan = {
            "test_price_year": 9.9,
            "test_price_month": 0.99,
            "actual_price_year": 99.0,
            "actual_price_month": 9.9,
        }
        with patch.object(db_utils, "get_plan_by_code", return_value=plan):
            result = db_utils.get_plan_price("monthly", "month", use_test_price=True)
        self.assertAlmostEqual(result, 0.99)

    def test_actual_price_year(self):
        import db_utils

        plan = {
            "test_price_year": 9.9,
            "test_price_month": 0.99,
            "actual_price_year": 99.0,
            "actual_price_month": 9.9,
        }
        with patch.object(db_utils, "get_plan_by_code", return_value=plan):
            result = db_utils.get_plan_price("monthly", "year", use_test_price=False)
        self.assertAlmostEqual(result, 99.0)

    def test_actual_price_month(self):
        import db_utils

        plan = {
            "test_price_year": 9.9,
            "test_price_month": 0.99,
            "actual_price_year": 99.0,
            "actual_price_month": 9.9,
        }
        with patch.object(db_utils, "get_plan_by_code", return_value=plan):
            result = db_utils.get_plan_price("monthly", "month")
        self.assertAlmostEqual(result, 9.9)


class TestGetExchangeRateFallback(unittest.TestCase):
    @patch("db_utils.get_db_connection")
    def test_rate_found(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        cur.fetchone.return_value = (7.25,)
        with patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s):
            result = db_utils.get_exchange_rate_fallback("USD_CNY")
        self.assertAlmostEqual(result, 7.25)

    @patch("db_utils.get_db_connection")
    def test_rate_not_found_returns_none(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        cur.fetchone.return_value = None
        with patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s):
            result = db_utils.get_exchange_rate_fallback("XYZ_CNY")
        self.assertIsNone(result)

    @patch("db_utils.get_db_connection")
    def test_exception_returns_none(self, mock_gdc):
        import db_utils

        mock_gdc.side_effect = Exception("connection error")
        result = db_utils.get_exchange_rate_fallback("USD_CNY")
        self.assertIsNone(result)


class TestUpdateExchangeRateFallback(unittest.TestCase):
    @patch("db_utils.get_db_connection")
    def test_upsert_success(self, mock_gdc):
        import db_utils

        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx
        with patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s):
            db_utils.update_exchange_rate_fallback("USD_CNY", 7.25, "api")
        cur.execute.assert_called_once()
        conn.commit.assert_called_once()

    @patch("db_utils.get_db_connection")
    def test_exception_silently_ignored(self, mock_gdc):
        import db_utils

        mock_gdc.side_effect = Exception("connection error")
        db_utils.update_exchange_rate_fallback("USD_CNY", 7.25)


class TestGetDashboardStatsFull(unittest.TestCase):
    @patch("db_utils.set_statistics_cache")
    @patch("db_utils.get_statistics_cache")
    @patch("db_utils.get_db_connection")
    def test_all_fields_present_in_result(
        self, mock_gdc, mock_cache_get, mock_cache_set
    ):
        import db_utils

        mock_cache_get.return_value = None
        ctx, conn, cur = _make_ctx()
        mock_gdc.return_value = ctx

        fetch_returns = iter(
            [
                (10,),
                (5,),
                (200,),
                (1000.0,),
                (100.0,),
                (95.0,),
                (300.0,),
                (3,),
            ]
        )
        cur.fetchone.side_effect = lambda: next(fetch_returns)

        with (
            patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s),
            patch.object(db_utils, "_is_postgresql_connection", return_value=False),
        ):
            result = db_utils.get_dashboard_stats()

        expected_keys = [
            "active_users_today",
            "new_users_today",
            "total_users",
            "total_revenue",
            "revenue_today",
            "revenue_yesterday",
            "revenue_month",
            "online_users",
            "timestamp",
        ]
        for key in expected_keys:
            self.assertIn(key, result)


if __name__ == "__main__":
    unittest.main()
