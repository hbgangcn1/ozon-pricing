# -*- coding: utf-8 -*-
import asyncio
import time
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from payment_handler import (
    PaymentHandler,
    _extract_plan_code,
    _parse_duration,
    payment_handler,
)


def _make_session_mock(order=None, user=None):
    mock_session = AsyncMock()

    async def _execute_side_effect(stmt):
        result = MagicMock()
        result.scalar_one_or_none.return_value = order
        return result

    mock_session.execute.side_effect = _execute_side_effect
    mock_session.get.return_value = user

    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = mock_session
    mock_cm.__aexit__.return_value = None
    return mock_cm, mock_session


def _make_order(
    order_id="ord",
    user_id=1,
    description="效率版月套餐",
    duration="1月",
    status="PENDING",
):
    order = MagicMock()
    order.order_id = order_id
    order.user_id = user_id
    order.description = description
    order.duration = duration
    order.status = status
    return order


def _make_user(uid=1):
    user = MagicMock()
    user.id = uid
    return user


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
    @patch("payment_handler.AsyncSessionLocal")
    def test_successful_flow(self, mock_sl):
        order = _make_order()
        user = _make_user()
        mock_cm, mock_session = _make_session_mock(order=order, user=user)
        mock_sl.return_value = mock_cm
        asyncio.run(PaymentHandler.handle_payment_success("order_ok"))
        mock_session.commit.assert_called_once()

    @patch("payment_handler.AsyncSessionLocal")
    def test_order_not_found_raises_value_error(self, mock_sl):
        mock_cm, _ = _make_session_mock(order=None)
        mock_sl.return_value = mock_cm
        with self.assertRaises(ValueError) as ctx:
            asyncio.run(PaymentHandler.handle_payment_success("no_order"))
        self.assertIn("no_order", str(ctx.exception))

    @patch("payment_handler.AsyncSessionLocal")
    def test_idempotent_already_success(self, mock_sl):
        order = _make_order(status="SUCCESS")
        mock_cm, mock_session = _make_session_mock(order=order)
        mock_sl.return_value = mock_cm
        asyncio.run(PaymentHandler.handle_payment_success("order_dup"))
        mock_session.commit.assert_not_called()

    @patch("payment_handler.AsyncSessionLocal")
    def test_db_error_propagated(self, mock_sl):
        mock_session = AsyncMock()
        mock_session.execute.side_effect = Exception("db write error")
        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = mock_session
        mock_cm.__aexit__.return_value = None
        mock_sl.return_value = mock_cm
        with self.assertRaises(Exception) as c:
            asyncio.run(PaymentHandler.handle_payment_success("order_dberr"))
        self.assertIn("db write error", str(c.exception))

    @patch("payment_handler.AsyncSessionLocal")
    def test_plan_code_efficiency(self, mock_sl):
        order = _make_order(description="效率版年套餐", duration="1年")
        user = _make_user()
        mock_cm, mock_session = _make_session_mock(order=order, user=user)
        mock_sl.return_value = mock_cm
        asyncio.run(PaymentHandler.handle_payment_success("ord_eff"))
        self.assertEqual(user.subscription_type, "efficiency")

    @patch("payment_handler.AsyncSessionLocal")
    def test_plan_code_professional(self, mock_sl):
        order = _make_order(description="专业版月套餐", duration="1月")
        user = _make_user()
        mock_cm, mock_session = _make_session_mock(order=order, user=user)
        mock_sl.return_value = mock_cm
        asyncio.run(PaymentHandler.handle_payment_success("ord_pro"))
        self.assertEqual(user.subscription_type, "professional")

    @patch("payment_handler.AsyncSessionLocal")
    def test_plan_code_enterprise(self, mock_sl):
        order = _make_order(description="企业版年套餐", duration="1年")
        user = _make_user()
        mock_cm, mock_session = _make_session_mock(order=order, user=user)
        mock_sl.return_value = mock_cm
        asyncio.run(PaymentHandler.handle_payment_success("ord_ent"))
        self.assertEqual(user.subscription_type, "enterprise")

    @patch("payment_handler.AsyncSessionLocal")
    def test_duration_yearly_365_days(self, mock_sl):
        now = int(time.time())
        order = _make_order(description="效率版年套餐", duration="1年")
        user = _make_user()
        mock_cm, mock_session = _make_session_mock(order=order, user=user)
        mock_sl.return_value = mock_cm
        asyncio.run(PaymentHandler.handle_payment_success("ord_yr"))
        expiry = user.subscription_expires
        self.assertAlmostEqual(expiry, now + 365 * 86400, delta=5)

    @patch("payment_handler.AsyncSessionLocal")
    def test_duration_monthly_30_days(self, mock_sl):
        now = int(time.time())
        order = _make_order(description="专业版月套餐", duration="1月")
        user = _make_user()
        mock_cm, mock_session = _make_session_mock(order=order, user=user)
        mock_sl.return_value = mock_cm
        asyncio.run(PaymentHandler.handle_payment_success("ord_mo"))
        expiry = user.subscription_expires
        self.assertAlmostEqual(expiry, now + 30 * 86400, delta=5)


class TestPaymentHandlerUpdateOrderStatus(unittest.TestCase):
    @patch("payment_handler.AsyncSessionLocal")
    def test_successful_update(self, mock_sl):
        order = _make_order(status="PENDING")
        mock_cm, mock_session = _make_session_mock(order=order)
        mock_sl.return_value = mock_cm
        asyncio.run(PaymentHandler.update_order_status("ord_upd", "PAID"))
        mock_session.commit.assert_called_once()
        self.assertEqual(order.status, "PAID")

    @patch("payment_handler.AsyncSessionLocal")
    def test_db_error_propagated(self, mock_sl):
        mock_session = AsyncMock()
        mock_session.execute.side_effect = Exception("update failed")
        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = mock_session
        mock_cm.__aexit__.return_value = None
        mock_sl.return_value = mock_cm
        with self.assertRaises(Exception) as c:
            asyncio.run(PaymentHandler.update_order_status("ord_fail", "PAID"))
        self.assertIn("update failed", str(c.exception))


class TestPaymentHandlerProcessNotify(unittest.TestCase):
    @patch("payment_handler._wechat_available", True)
    @patch("payment_handler.wechat_pay_v3")
    @patch("payment_handler.AsyncSessionLocal")
    def test_successful_notify_calls_update_order_status(self, mock_sl, mock_wechat):
        order = _make_order(status="PENDING")
        mock_cm, mock_session = _make_session_mock(order=order)
        mock_sl.return_value = mock_cm
        mock_wechat.process_notify.return_value = {
            "success": True,
            "out_trade_no": "trade_123",
            "transaction_id": "tx_abc",
            "trade_state": "SUCCESS",
        }
        result = asyncio.run(payment_handler.process_wechat_notify({"key": "val"}))
        self.assertTrue(result["success"])
        self.assertEqual(result["out_trade_no"], "trade_123")
        mock_session.commit.assert_called_once()

    @patch("payment_handler._wechat_available", False)
    @patch("payment_handler.wechat_pay_v3", None)
    def test_wechat_unavailable_returns_error(self):
        result = asyncio.run(payment_handler.process_wechat_notify({}))
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
        result = asyncio.run(payment_handler.process_wechat_notify({"data": "x"}))
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
        result = asyncio.run(payment_handler.process_wechat_notify({}))
        self.assertIn("out_trade_no", result)

    @patch("payment_handler._wechat_available", True)
    @patch("payment_handler.wechat_pay_v3")
    @patch("payment_handler.AsyncSessionLocal")
    def test_no_update_when_empty_out_trade_no(self, mock_sl, mock_wechat):
        mock_cm, mock_session = _make_session_mock()
        mock_sl.return_value = mock_cm
        mock_wechat.process_notify.return_value = {
            "success": True,
            "out_trade_no": "",
        }
        asyncio.run(payment_handler.process_wechat_notify({}))
        mock_session.commit.assert_not_called()


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
    @patch("payment_handler.AsyncSessionLocal")
    def test_handle_payment_success_db_unavailable(self, mock_sl):
        mock_cm = AsyncMock()
        mock_cm.__aenter__.side_effect = Exception("数据库不可用")
        mock_sl.return_value = mock_cm
        with self.assertRaises(Exception) as ctx:
            asyncio.run(PaymentHandler.handle_payment_success("order_any"))
        self.assertIsNotNone(ctx.exception)

    @patch("payment_handler.AsyncSessionLocal")
    def test_update_order_status_db_unavailable(self, mock_sl):
        mock_cm = AsyncMock()
        mock_cm.__aenter__.side_effect = Exception("数据库不可用")
        mock_sl.return_value = mock_cm
        with self.assertRaises(Exception) as ctx:
            asyncio.run(PaymentHandler.update_order_status("order_any", "PAID"))
        self.assertIsNotNone(ctx.exception)


class TestProcessWechatNotifyException(unittest.TestCase):
    @patch("payment_handler._wechat_available", True)
    @patch("payment_handler.wechat_pay_v3")
    def test_exception_in_process_notify(self, mock_wechat):
        mock_wechat.process_notify.side_effect = RuntimeError("notify boom")
        result = asyncio.run(payment_handler.process_wechat_notify({"data": "x"}))
        self.assertFalse(result["success"])
        self.assertIn("notify boom", result["message"])
        self.assertEqual(result["out_trade_no"], "")


class TestImportFallbacks(unittest.TestCase):
    def test_wechat_import_fallback(self):
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
