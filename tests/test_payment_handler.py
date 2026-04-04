# -*- coding: utf-8 -*-
import time
import unittest
from unittest.mock import MagicMock, patch

from payment_handler import (
    PaymentHandler,
    _extract_plan_code,
    _parse_duration,
    payment_handler,
)


def _make_db_mock(mock_db, fetchone_return=None, fetchall_return=None):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = fetchone_return
    if fetchall_return is not None:
        mock_cursor.fetchall.return_value = fetchall_return
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=(mock_conn, mock_cursor))
    ctx.__exit__ = MagicMock(return_value=False)
    mock_db.return_value = ctx
    return mock_conn, mock_cursor


class TestPaymentHandlerQueryStatus(unittest.TestCase):
    @patch("payment_handler._wechat_available", True)
    @patch("payment_handler.wechat_pay_v3")
    def test_successful_query_returns_mapped_status(self, mock_wechat):
        mock_wechat.query_order.return_value = {
            "success": True,
            "trade_state": "SUCCESS",
            "trade_state_desc": "支付成功",
        }
        result = PaymentHandler.query_payment_status("order_001")
        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(result["message"], "支付成功")
        mock_wechat.query_order.assert_called_once_with("order_001")

    @patch("payment_handler._wechat_available", True)
    @patch("payment_handler.wechat_pay_v3")
    def test_successful_query_uses_trade_state_when_no_desc(self, mock_wechat):
        mock_wechat.query_order.return_value = {
            "success": True,
            "trade_state": "NOTPAY",
            "trade_state_desc": "",
        }
        result = PaymentHandler.query_payment_status("order_002")
        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "NOTPAY")
        self.assertEqual(result["message"], "NOTPAY")

    @patch("payment_handler._wechat_available", True)
    @patch("payment_handler.wechat_pay_v3")
    def test_failed_query_returns_error(self, mock_wechat):
        mock_wechat.query_order.return_value = {
            "success": False,
            "message": "订单不存在",
        }
        result = PaymentHandler.query_payment_status("order_bad")
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertEqual(result["message"], "订单不存在")

    @patch("payment_handler._wechat_available", False)
    @patch("payment_handler.wechat_pay_v3", None)
    def test_wechat_unavailable_returns_graceful_error(self):
        result = PaymentHandler.query_payment_status("order_any")
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertEqual(result["message"], "微信支付模块不可用")

    @patch("payment_handler._wechat_available", True)
    @patch("payment_handler.wechat_pay_v3")
    def test_exception_returns_error(self, mock_wechat):
        mock_wechat.query_order.side_effect = RuntimeError("network error")
        result = PaymentHandler.query_payment_status("order_err")
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertIn("network error", result["message"])


class TestPaymentHandlerHandleSuccess(unittest.TestCase):
    @patch("payment_handler._db_available", True)
    @patch("payment_handler.get_db_connection")
    def test_successful_flow(self, mock_db):
        mock_conn, mock_cursor = _make_db_mock(
            mock_db,
            fetchone_return=("user_99", "效率版月套餐", "1月", "PENDING"),
        )
        PaymentHandler.handle_payment_success("order_ok")
        mock_conn.commit.assert_called_once()
        calls = mock_cursor.execute.call_args_list
        sqls = [str(c[0][0]) for c in calls]
        self.assertTrue(any("payment_orders" in s for s in sqls))
        self.assertTrue(any("users" in s for s in sqls))

    @patch("payment_handler._db_available", True)
    @patch("payment_handler.get_db_connection")
    def test_order_not_found_raises_value_error(self, mock_db):
        _make_db_mock(mock_db, fetchone_return=None)
        with self.assertRaises(ValueError) as ctx:
            PaymentHandler.handle_payment_success("no_order")
        self.assertIn("no_order", str(ctx.exception))

    @patch("payment_handler._db_available", True)
    @patch("payment_handler.get_db_connection")
    def test_idempotent_already_success(self, mock_db):
        mock_conn, mock_cursor = _make_db_mock(
            mock_db,
            fetchone_return=("user_1", "效率版月套餐", "1月", "SUCCESS"),
        )
        PaymentHandler.handle_payment_success("order_dup")
        mock_conn.commit.assert_not_called()
        mock_cursor.execute.assert_called_once()

    @patch("payment_handler._db_available", True)
    @patch("payment_handler.get_db_connection")
    def test_db_error_propagated(self, mock_db):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ("user_x", "效率版", "月", "PENDING")
        mock_cursor.execute.side_effect = [
            None,
            Exception("db write error"),
        ]
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=(mock_conn, mock_cursor))
        ctx.__exit__ = MagicMock(return_value=False)
        mock_db.return_value = ctx
        with self.assertRaises(Exception) as c:
            PaymentHandler.handle_payment_success("order_dberr")
        self.assertIn("db write error", str(c.exception))

    @patch("payment_handler._db_available", True)
    @patch("payment_handler.get_db_connection")
    def test_plan_code_efficiency(self, mock_db):
        mock_conn, mock_cursor = _make_db_mock(
            mock_db,
            fetchone_return=("u1", "效率版年套餐", "1年", "PENDING"),
        )
        PaymentHandler.handle_payment_success("ord_eff")
        args_list = mock_cursor.execute.call_args_list
        user_update_args = None
        for call in args_list:
            sql_arg = str(call[0][0])
            if "users" in sql_arg and "subscription_type" in sql_arg:
                user_update_args = call[0][1]
        self.assertIsNotNone(user_update_args)
        self.assertEqual(user_update_args[0], "efficiency")

    @patch("payment_handler._db_available", True)
    @patch("payment_handler.get_db_connection")
    def test_plan_code_professional(self, mock_db):
        mock_conn, mock_cursor = _make_db_mock(
            mock_db,
            fetchone_return=("u2", "专业版月套餐", "1月", "PENDING"),
        )
        PaymentHandler.handle_payment_success("ord_pro")
        args_list = mock_cursor.execute.call_args_list
        user_update_args = None
        for call in args_list:
            sql_arg = str(call[0][0])
            if "users" in sql_arg and "subscription_type" in sql_arg:
                user_update_args = call[0][1]
        self.assertIsNotNone(user_update_args)
        self.assertEqual(user_update_args[0], "professional")

    @patch("payment_handler._db_available", True)
    @patch("payment_handler.get_db_connection")
    def test_plan_code_enterprise(self, mock_db):
        mock_conn, mock_cursor = _make_db_mock(
            mock_db,
            fetchone_return=("u3", "企业版年套餐", "1年", "PENDING"),
        )
        PaymentHandler.handle_payment_success("ord_ent")
        args_list = mock_cursor.execute.call_args_list
        user_update_args = None
        for call in args_list:
            sql_arg = str(call[0][0])
            if "users" in sql_arg and "subscription_type" in sql_arg:
                user_update_args = call[0][1]
        self.assertIsNotNone(user_update_args)
        self.assertEqual(user_update_args[0], "enterprise")

    @patch("payment_handler._db_available", True)
    @patch("payment_handler.get_db_connection")
    def test_duration_yearly_365_days(self, mock_db):
        now = int(time.time())
        mock_conn, mock_cursor = _make_db_mock(
            mock_db,
            fetchone_return=("u4", "效率版年套餐", "1年", "PENDING"),
        )
        PaymentHandler.handle_payment_success("ord_yr")
        args_list = mock_cursor.execute.call_args_list
        user_update_args = None
        for call in args_list:
            sql_arg = str(call[0][0])
            if "users" in sql_arg and "subscription_type" in sql_arg:
                user_update_args = call[0][1]
        self.assertIsNotNone(user_update_args)
        expiry = user_update_args[1]
        self.assertAlmostEqual(expiry, now + 365 * 86400, delta=5)

    @patch("payment_handler._db_available", True)
    @patch("payment_handler.get_db_connection")
    def test_duration_monthly_30_days(self, mock_db):
        now = int(time.time())
        mock_conn, mock_cursor = _make_db_mock(
            mock_db,
            fetchone_return=("u5", "专业版月套餐", "1月", "PENDING"),
        )
        PaymentHandler.handle_payment_success("ord_mo")
        args_list = mock_cursor.execute.call_args_list
        user_update_args = None
        for call in args_list:
            sql_arg = str(call[0][0])
            if "users" in sql_arg and "subscription_type" in sql_arg:
                user_update_args = call[0][1]
        self.assertIsNotNone(user_update_args)
        expiry = user_update_args[1]
        self.assertAlmostEqual(expiry, now + 30 * 86400, delta=5)


class TestPaymentHandlerUpdateOrderStatus(unittest.TestCase):
    @patch("payment_handler._db_available", True)
    @patch("payment_handler.get_db_connection")
    def test_successful_update(self, mock_db):
        mock_conn, mock_cursor = _make_db_mock(mock_db)
        PaymentHandler.update_order_status("ord_upd", "PAID")
        mock_conn.commit.assert_called_once()
        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args[0]
        self.assertIn("PAID", call_args[1])
        self.assertIn("ord_upd", call_args[1])

    @patch("payment_handler._db_available", True)
    @patch("payment_handler.get_db_connection")
    def test_db_error_propagated(self, mock_db):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("update failed")
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=(mock_conn, mock_cursor))
        ctx.__exit__ = MagicMock(return_value=False)
        mock_db.return_value = ctx
        with self.assertRaises(Exception) as c:
            PaymentHandler.update_order_status("ord_fail", "PAID")
        self.assertIn("update failed", str(c.exception))


class TestPaymentHandlerProcessNotify(unittest.TestCase):
    @patch("payment_handler._wechat_available", True)
    @patch("payment_handler.wechat_pay_v3")
    @patch("payment_handler._db_available", True)
    @patch("payment_handler.get_db_connection")
    def test_successful_notify_calls_update_order_status(self, mock_db, mock_wechat):
        mock_conn, mock_cursor = _make_db_mock(mock_db)
        mock_wechat.process_notify.return_value = {
            "success": True,
            "out_trade_no": "trade_123",
            "transaction_id": "tx_abc",
            "trade_state": "SUCCESS",
        }
        result = payment_handler.process_wechat_notify({"key": "val"})
        self.assertTrue(result["success"])
        self.assertEqual(result["out_trade_no"], "trade_123")
        mock_conn.commit.assert_called_once()

    @patch("payment_handler._wechat_available", False)
    @patch("payment_handler.wechat_pay_v3", None)
    def test_wechat_unavailable_returns_error(self):
        result = payment_handler.process_wechat_notify({})
        self.assertFalse(result["success"])
        self.assertEqual(result["message"], "微信支付模块不可用")
        self.assertIn("out_trade_no", result)

    @patch("payment_handler._wechat_available", True)
    @patch("payment_handler.wechat_pay_v3")
    def test_wechat_returns_failure(self, mock_wechat):
        mock_wechat.process_notify.return_value = {
            "success": False,
            "message": "签名验证失败",
            "out_trade_no": "",
        }
        result = payment_handler.process_wechat_notify({"data": "x"})
        self.assertFalse(result["success"])
        self.assertEqual(result["message"], "签名验证失败")
        self.assertIn("out_trade_no", result)

    @patch("payment_handler._wechat_available", True)
    @patch("payment_handler.wechat_pay_v3")
    def test_out_trade_no_always_present(self, mock_wechat):
        mock_wechat.process_notify.return_value = {
            "success": True,
            "transaction_id": "tx_999",
        }
        result = payment_handler.process_wechat_notify({})
        self.assertIn("out_trade_no", result)

    @patch("payment_handler._wechat_available", True)
    @patch("payment_handler.wechat_pay_v3")
    @patch("payment_handler._db_available", True)
    @patch("payment_handler.get_db_connection")
    def test_no_update_when_empty_out_trade_no(self, mock_db, mock_wechat):
        mock_conn, mock_cursor = _make_db_mock(mock_db)
        mock_wechat.process_notify.return_value = {
            "success": True,
            "out_trade_no": "",
        }
        payment_handler.process_wechat_notify({})
        mock_conn.commit.assert_not_called()


class TestHelpers(unittest.TestCase):
    def test_extract_efficiency(self):
        self.assertEqual(_extract_plan_code("效率版月套餐"), "efficiency")

    def test_extract_professional(self):
        self.assertEqual(_extract_plan_code("专业版年套餐"), "professional")

    def test_extract_enterprise(self):
        self.assertEqual(_extract_plan_code("企业版月套餐"), "enterprise")

    def test_extract_default(self):
        self.assertEqual(_extract_plan_code("未知套餐"), "efficiency")

    def test_extract_empty_string(self):
        self.assertEqual(_extract_plan_code(""), "efficiency")

    def test_parse_monthly(self):
        self.assertEqual(_parse_duration("1月"), 30)

    def test_parse_yearly(self):
        self.assertEqual(_parse_duration("1年"), 365)

    def test_parse_default(self):
        self.assertEqual(_parse_duration("unknown"), 30)

    def test_parse_empty(self):
        self.assertEqual(_parse_duration(""), 30)

    def test_parse_year_takes_priority(self):
        self.assertEqual(_parse_duration("1年12月"), 365)


class TestDbUnavailablePaths(unittest.TestCase):
    """覆盖 _db_available=False 时的 RuntimeError 路径"""

    @patch("payment_handler._db_available", False)
    @patch("payment_handler.get_db_connection", None)
    def test_handle_payment_success_db_unavailable(self):
        """line 111: handle_payment_success raises RuntimeError"""
        with self.assertRaises(RuntimeError) as ctx:
            PaymentHandler.handle_payment_success("order_any")
        self.assertIn("数据库不可用", str(ctx.exception))

    @patch("payment_handler._db_available", False)
    @patch("payment_handler.get_db_connection", None)
    def test_update_order_status_db_unavailable(self):
        """line 167: update_order_status raises RuntimeError"""
        with self.assertRaises(RuntimeError) as ctx:
            PaymentHandler.update_order_status("order_any", "PAID")
        self.assertIn("数据库不可用", str(ctx.exception))


class TestProcessWechatNotifyException(unittest.TestCase):
    """覆盖 process_wechat_notify 的 Exception 路径 lines 215-217"""

    @patch("payment_handler._wechat_available", True)
    @patch("payment_handler.wechat_pay_v3")
    def test_exception_in_process_notify(self, mock_wechat):
        mock_wechat.process_notify.side_effect = RuntimeError("notify boom")
        result = payment_handler.process_wechat_notify({"data": "x"})
        self.assertFalse(result["success"])
        self.assertIn("notify boom", result["message"])
        self.assertEqual(result["out_trade_no"], "")


class TestImportFallbacks(unittest.TestCase):
    """覆盖模块级 import fallback 路径 lines 17-22, 29-31"""

    def test_db_adapter_import_fallback(self):
        """强制重导入 payment_handler，使 db_adapter 导入失败"""
        import builtins
        import importlib
        import sys

        saved_modules = {}
        for key in list(sys.modules.keys()):
            if key == "payment_handler" or key == "db_adapter":
                saved_modules[key] = sys.modules.pop(key)

        orig_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "db_adapter":
                raise ImportError("mocked db_adapter missing")
            return orig_import(name, *args, **kwargs)

        try:
            builtins.__import__ = mock_import
            mod = importlib.import_module("payment_handler")
            self.assertFalse(mod._db_available)
            self.assertIsNone(mod.get_db_connection)
            self.assertEqual(mod.adapt_sql("SELECT 1"), "SELECT 1")
        finally:
            builtins.__import__ = orig_import
            for key, val in saved_modules.items():
                sys.modules[key] = val

    def test_wechat_import_fallback(self):
        """强制重导入 payment_handler，使 wechat_pay_v3 导入失败"""
        import builtins
        import importlib
        import sys

        saved_modules = {}
        for key in list(sys.modules.keys()):
            if key == "payment_handler" or key == "wechat_pay_v3_api":
                saved_modules[key] = sys.modules.pop(key)

        orig_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "wechat_pay_v3_api":
                raise ImportError("mocked wechat missing")
            return orig_import(name, *args, **kwargs)

        try:
            builtins.__import__ = mock_import
            mod = importlib.import_module("payment_handler")
            self.assertFalse(mod._wechat_available)
            self.assertIsNone(mod.wechat_pay_v3)
        finally:
            builtins.__import__ = orig_import
            for key, val in saved_modules.items():
                sys.modules[key] = val


if __name__ == "__main__":
    unittest.main()
