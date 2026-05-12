# pyright: reportUnusedFunction=false

import sys
import os
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402
from api.main import app  # noqa: E402
from api import dependencies  # noqa: E402
from api.routes.payment import get_payment_service  # noqa: E402
from database import get_db  # noqa: E402
from models.order import PaymentOrder  # noqa: E402
from services.payment_service import SuspiciousWechatNotifyError  # noqa: E402
from wechat_pay_v3_api import WechatResponseSignatureError  # noqa: E402

MOCK_USER = {
    "id": 1,
    "username": "testuser",
    "role": "user",
    "user_type": "professional",
    "remaining_calculations": 100,
}

client = TestClient(app, raise_server_exceptions=False)
SIGNED_NOTIFY_HEADERS = {
    "Wechatpay-Timestamp": "1700000000",
    "Wechatpay-Nonce": "test-nonce",
    "Wechatpay-Signature": "test-signature",
    "Wechatpay-Serial": "test-serial",
}


def _mock_session():
    s = MagicMock()
    s.add = MagicMock()
    s.flush = AsyncMock()
    s.commit = AsyncMock()
    s.rollback = AsyncMock()
    return s


def _mock_svc():
    svc = AsyncMock()
    return svc


@pytest.fixture(autouse=True)
def _setup_overrides():
    app.dependency_overrides[dependencies.get_current_user_id] = lambda: 1
    app.dependency_overrides[dependencies.get_current_user] = lambda: MOCK_USER
    ms = _mock_session()
    mock_service = _mock_svc()
    app.dependency_overrides[get_db] = lambda: ms
    app.dependency_overrides[get_payment_service] = lambda: mock_service
    yield ms, mock_service
    app.dependency_overrides.pop(dependencies.get_current_user_id, None)
    app.dependency_overrides.pop(dependencies.get_current_user, None)
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_payment_service, None)


class TestCreatePayment:
    @patch("api.routes.payment.wechat_pay_v3")
    @patch("api.routes.payment._wechat_available", True)
    @patch(
        "api.routes.payment.get_plan_by_code",
        new_callable=AsyncMock,
    )
    @patch(
        "api.routes.payment.get_plan_price",
        new_callable=AsyncMock,
    )
    @patch(
        "api.routes.payment.is_registration_open",
        new_callable=AsyncMock,
    )
    def test_success(
        self,
        mock_is_open,
        mock_price,
        mock_plan,
        mock_wechat,
        _setup_overrides,
    ):
        _, mock_svc = _setup_overrides
        mock_is_open.return_value = True
        mock_price.return_value = 29.9
        mock_plan.return_value = {"plan_name": "Pro"}
        mock_wechat.create_native_order.return_value = {
            "success": True,
            "code_url": "weixin://test",
        }
        mock_order = MagicMock()
        mock_order.order_id = "test_ord_001"
        mock_order.description = "订阅Pro"
        mock_order.status = "PENDING"
        mock_svc.create_order.return_value = mock_order
        resp = client.post(
            "/api/payments/create",
            json={
                "plan_code": "pro",
                "billing_cycle": "month",
                "amount": 29.9,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "order_id" in data
        assert data["code_url"] == "weixin://test"

    @patch(
        "api.routes.payment.get_plan_price",
        new_callable=AsyncMock,
    )
    @patch(
        "api.routes.payment.is_registration_open",
        new_callable=AsyncMock,
    )
    def test_amount_mismatch(self, mock_is_open, mock_price):
        mock_is_open.return_value = True
        mock_price.return_value = 99.9
        resp = client.post(
            "/api/payments/create",
            json={
                "plan_code": "pro",
                "billing_cycle": "month",
                "amount": 29.9,
            },
        )
        assert resp.status_code == 400

    @patch("api.routes.payment._wechat_available", False)
    @patch(
        "api.routes.payment.get_plan_by_code",
        new_callable=AsyncMock,
    )
    @patch(
        "api.routes.payment.get_plan_price",
        new_callable=AsyncMock,
    )
    @patch(
        "api.routes.payment.is_registration_open",
        new_callable=AsyncMock,
    )
    def test_wechat_unavailable(
        self,
        mock_is_open,
        mock_price,
        mock_plan,
        _setup_overrides,
    ):
        _, mock_svc = _setup_overrides
        mock_is_open.return_value = True
        mock_price.return_value = 29.9
        mock_plan.return_value = {"plan_name": "Pro"}
        mock_order = MagicMock()
        mock_order.order_id = "test_ord_002"
        mock_order.description = "订阅Pro"
        mock_order.status = "PENDING"
        mock_svc.create_order.return_value = mock_order
        resp = client.post(
            "/api/payments/create",
            json={
                "plan_code": "pro",
                "billing_cycle": "month",
                "amount": 29.9,
            },
        )
        assert resp.status_code == 502

    @patch("api.routes.payment.wechat_pay_v3")
    @patch("api.routes.payment._wechat_available", True)
    @patch(
        "api.routes.payment.get_plan_by_code",
        new_callable=AsyncMock,
    )
    @patch(
        "api.routes.payment.get_plan_price",
        new_callable=AsyncMock,
    )
    @patch(
        "api.routes.payment.is_registration_open",
        new_callable=AsyncMock,
    )
    def test_signature_failure_returns_502_and_keeps_pending(
        self,
        mock_is_open,
        mock_price,
        mock_plan,
        mock_wechat,
        _setup_overrides,
    ):
        _, mock_svc = _setup_overrides
        mock_is_open.return_value = True
        mock_price.return_value = 29.9
        mock_plan.return_value = {"plan_name": "Pro"}
        mock_wechat.create_native_order.side_effect = WechatResponseSignatureError(
            "平台签名验证失败"
        )
        mock_wechat.query_order.return_value = {
            "success": False,
            "message": "订单状态未确认",
        }
        mock_order = MagicMock()
        mock_order.order_id = "test_ord_004"
        mock_order.description = "订阅Pro"
        mock_order.status = "PENDING"
        mock_svc.create_order.return_value = mock_order

        resp = client.post(
            "/api/payments/create",
            json={
                "plan_code": "pro",
                "billing_cycle": "month",
                "amount": 29.9,
            },
        )

        assert resp.status_code == 502
        assert resp.json()["detail"] == "微信支付订单创建状态未确认，请重试"
        assert mock_order.status == "PENDING"
        mock_wechat.query_order.assert_called_once_with("test_ord_004")

    @patch("api.routes.payment.wechat_pay_v3")
    @patch("api.routes.payment._wechat_available", True)
    @patch(
        "api.routes.payment.get_plan_by_code",
        new_callable=AsyncMock,
    )
    @patch(
        "api.routes.payment.get_plan_price",
        new_callable=AsyncMock,
    )
    @patch(
        "api.routes.payment.is_registration_open",
        new_callable=AsyncMock,
    )
    def test_signature_failure_query_success_reconciles_and_commits(
        self,
        mock_is_open,
        mock_price,
        mock_plan,
        mock_wechat,
        _setup_overrides,
    ):
        """W8 fix: signature failure → query SUCCESS → apply credit + commit + 502."""
        mock_session, mock_svc = _setup_overrides
        mock_is_open.return_value = True
        mock_price.return_value = 29.9
        mock_plan.return_value = {"plan_name": "Pro"}
        mock_wechat.create_native_order.side_effect = WechatResponseSignatureError(
            "平台签名验证失败"
        )
        mock_wechat.query_order.return_value = {
            "success": True,
            "trade_state": "SUCCESS",
            "data": {
                "out_trade_no": "test_ord_recon",
                "transaction_id": "wx_tx_recon",
                "amount": {"total": 2990, "currency": "CNY"},
                "appid": "wx_app",
                "mchid": "wx_mch",
            },
        }
        mock_svc.apply_wechat_payment_success = AsyncMock(return_value="processed")
        mock_order = MagicMock()
        mock_order.order_id = "test_ord_recon"
        mock_order.description = "订阅Pro"
        mock_order.status = "PENDING"
        mock_svc.create_order.return_value = mock_order

        resp = client.post(
            "/api/payments/create",
            json={
                "plan_code": "pro",
                "billing_cycle": "month",
                "amount": 29.9,
            },
        )

        assert resp.status_code == 502
        assert resp.json()["detail"] == "微信支付订单创建状态未确认，请重试"
        mock_wechat.query_order.assert_called_once_with("test_ord_recon")
        assert mock_svc.apply_wechat_payment_success.await_count == 1
        mock_svc.apply_wechat_payment_success.assert_awaited_once_with(
            out_trade_no="test_ord_recon",
            transaction_id="wx_tx_recon",
            amount_total=2990,
            currency="CNY",
            appid="wx_app",
            mchid="wx_mch",
            raw_notify=mock_wechat.query_order.return_value["data"],
        )
        mock_session.commit.assert_awaited()

    @patch("api.routes.payment.wechat_pay_v3")
    @patch("api.routes.payment._wechat_available", True)
    @patch(
        "api.routes.payment.get_plan_by_code",
        new_callable=AsyncMock,
    )
    @patch(
        "api.routes.payment.get_plan_price",
        new_callable=AsyncMock,
    )
    @patch(
        "api.routes.payment.is_registration_open",
        new_callable=AsyncMock,
    )
    def test_wechat_fails(
        self,
        mock_is_open,
        mock_price,
        mock_plan,
        mock_wechat,
        _setup_overrides,
    ):
        _, mock_svc = _setup_overrides
        mock_is_open.return_value = True
        mock_price.return_value = 29.9
        mock_plan.return_value = {"plan_name": "Pro"}
        mock_wechat.create_native_order.return_value = {
            "success": False,
            "message": "失败",
        }
        mock_order = MagicMock()
        mock_order.order_id = "test_ord_003"
        mock_order.description = "订阅Pro"
        mock_order.status = "PENDING"
        mock_svc.create_order.return_value = mock_order
        resp = client.post(
            "/api/payments/create",
            json={
                "plan_code": "pro",
                "billing_cycle": "month",
                "amount": 29.9,
            },
        )
        assert resp.status_code == 502


class TestPaymentNotify:
    @patch("api.routes.payment.wechat_pay_v3")
    @patch("api.routes.payment._wechat_available", True)
    def test_verified_transaction_success_credits_and_audits(
        self,
        mock_wechat,
        _setup_overrides,
    ):
        mock_session, mock_svc = _setup_overrides
        mock_svc.apply_wechat_payment_success.return_value = "processed"
        payload = {
            "out_trade_no": "test_notify_ord",
            "transaction_id": "wx_tx_001",
            "amount": {"total": 2990, "currency": "CNY"},
            "appid": "wx_app",
            "mchid": "wx_mch",
        }
        mock_wechat.process_notify.return_value = payload, True
        body = {
            "event_type": "TRANSACTION.SUCCESS",
            "resource": {"ciphertext": "encrypted"},
            "out_trade_no": "test_notify_ord",
            "transaction_id": "wx_tx_001",
        }

        resp = client.post(
            "/api/payments/notify",
            json=body,
            headers=SIGNED_NOTIFY_HEADERS,
        )

        assert resp.status_code == 200
        assert resp.json() == {"code": "SUCCESS", "message": "OK"}
        mock_svc.apply_wechat_payment_success.assert_awaited_once_with(
            out_trade_no="test_notify_ord",
            transaction_id="wx_tx_001",
            amount_total=2990,
            currency="CNY",
            appid="wx_app",
            mchid="wx_mch",
            raw_notify=payload,
        )
        audit = mock_session.add.call_args.args[0]
        assert audit.out_trade_no == "test_notify_ord"
        assert audit.transaction_id == "wx_tx_001"
        assert audit.signature_verified is True
        assert audit.response_code == "SUCCESS"
        assert audit.response_message == "OK"
        assert json.loads(audit.raw_body) == body
        mock_session.flush.assert_awaited()

    @patch("api.routes.payment.wechat_pay_v3")
    @patch("api.routes.payment._wechat_available", True)
    def test_signature_fail_audits_only_and_acks_200(
        self,
        mock_wechat,
        _setup_overrides,
    ):
        mock_session, mock_svc = _setup_overrides
        mock_wechat.process_notify.return_value = None, False
        body = {
            "event_type": "TRANSACTION.SUCCESS",
            "out_trade_no": "test_notify_bad_sig_ord",
            "transaction_id": "wx_tx_bad_sig",
        }

        resp = client.post(
            "/api/payments/notify",
            json=body,
            headers=SIGNED_NOTIFY_HEADERS,
        )

        assert resp.status_code == 200
        assert resp.json() == {"code": "SUCCESS", "message": "OK"}
        mock_svc.apply_wechat_payment_success.assert_not_awaited()
        audit = mock_session.add.call_args.args[0]
        assert audit.out_trade_no == "test_notify_bad_sig_ord"
        assert audit.transaction_id == "wx_tx_bad_sig"
        assert audit.signature_verified is False
        assert audit.response_code == "SUCCESS"
        assert audit.response_message == "OK"
        mock_session.flush.assert_awaited()

    @patch("api.routes.payment.wechat_pay_v3")
    @patch("api.routes.payment._wechat_available", True)
    def test_idempotent(self, mock_wechat, _setup_overrides):
        _, mock_svc = _setup_overrides
        mock_svc.apply_wechat_payment_success.return_value = "duplicate"
        mock_wechat.process_notify.return_value = {
            "out_trade_no": "test_idemp_ord",
            "transaction_id": "wx_tx_002",
            "amount": {"total": 2990, "currency": "CNY"},
        }, True
        body = {
            "event_type": "TRANSACTION.SUCCESS",
            "out_trade_no": "test_idemp_ord",
            "transaction_id": "wx_tx_002",
        }
        resp = client.post(
            "/api/payments/notify",
            json=body,
            headers=SIGNED_NOTIFY_HEADERS,
        )
        assert resp.status_code == 200
        assert resp.json()["code"] == "SUCCESS"

    @patch("api.routes.payment._wechat_available", False)
    def test_wechat_unavailable(self, _setup_overrides):
        resp = client.post(
            "/api/payments/notify",
            json={},
            headers=SIGNED_NOTIFY_HEADERS,
        )
        assert resp.status_code == 200
        assert resp.json() == {"code": "SUCCESS", "message": "OK"}

    @patch("api.routes.payment._wechat_available", False)
    def test_wechat_unavailable_in_production_returns_503(self, _setup_overrides):
        with patch("api.routes.payment._is_production", return_value=True):
            with patch.dict(os.environ, {"E2E_TEST": ""}, clear=False):
                os.environ.pop("E2E_TEST", None)
                resp = client.post(
                    "/api/payments/notify",
                    json={"out_trade_no": "prod_notify_ord"},
                    headers=SIGNED_NOTIFY_HEADERS,
                )

        assert resp.status_code == 503
        assert resp.json() == {"code": "FAIL", "message": "微信支付模块不可用"}

    @patch("api.routes.payment._wechat_available", False)
    def test_wechat_unavailable_in_production_allows_e2e_success(
        self,
        _setup_overrides,
    ):
        with patch("api.routes.payment._is_production", return_value=True):
            with patch.dict(os.environ, {"E2E_TEST": "1"}, clear=False):
                resp = client.post(
                    "/api/payments/notify",
                    json={"out_trade_no": "e2e_notify_ord"},
                    headers=SIGNED_NOTIFY_HEADERS,
                )

        assert resp.status_code == 200
        assert resp.json() == {"code": "SUCCESS", "message": "OK"}

    @patch("api.routes.payment.wechat_pay_v3")
    @patch("api.routes.payment._wechat_available", True)
    def test_suspicious_returns_success_to_stop_retries(
        self,
        mock_wechat,
        _setup_overrides,
    ):
        mock_session, mock_svc = _setup_overrides
        mock_svc.apply_wechat_payment_success.side_effect = (
            SuspiciousWechatNotifyError("test")
        )
        mock_wechat.process_notify.return_value = {
            "out_trade_no": "test_notify_exception_ord",
            "transaction_id": "wx_tx_003",
            "amount": {"total": 2990, "currency": "CNY"},
        }, True
        body = {
            "event_type": "TRANSACTION.SUCCESS",
            "out_trade_no": "test_notify_exception_ord",
            "transaction_id": "wx_tx_003",
        }

        resp = client.post(
            "/api/payments/notify",
            json=body,
            headers=SIGNED_NOTIFY_HEADERS,
        )

        assert resp.status_code == 200
        assert resp.json() == {"code": "SUCCESS", "message": "OK"}
        mock_session.rollback.assert_awaited_once()

    @patch("api.routes.payment.wechat_pay_v3")
    @patch("api.routes.payment._wechat_available", True)
    def test_missing_required_fields_returns_success_without_credit(
        self,
        mock_wechat,
        _setup_overrides,
    ):
        _, mock_svc = _setup_overrides
        mock_wechat.process_notify.return_value = {
            "out_trade_no": "test_notify_missing_ord",
        }, True

        resp = client.post(
            "/api/payments/notify",
            json={"out_trade_no": "test_notify_missing_ord"},
            headers=SIGNED_NOTIFY_HEADERS,
        )

        assert resp.status_code == 200
        assert resp.json() == {"code": "SUCCESS", "message": "OK"}
        mock_svc.apply_wechat_payment_success.assert_not_awaited()

    @patch("api.routes.payment.wechat_pay_v3")
    @patch("api.routes.payment._wechat_available", True)
    def test_unexpected_processing_error_returns_fail(
        self,
        mock_wechat,
        _setup_overrides,
    ):
        mock_session, mock_svc = _setup_overrides
        mock_svc.apply_wechat_payment_success.side_effect = RuntimeError("boom")
        mock_wechat.process_notify.return_value = {
            "out_trade_no": "test_notify_error_ord",
            "transaction_id": "wx_tx_004",
            "amount": {"total": 2990, "currency": "CNY"},
        }, True
        body = {
            "event_type": "TRANSACTION.SUCCESS",
            "out_trade_no": "test_notify_error_ord",
            "transaction_id": "wx_tx_004",
        }

        resp = client.post(
            "/api/payments/notify",
            json=body,
            headers=SIGNED_NOTIFY_HEADERS,
        )

        # W9 SEC#1: generic exceptions must FAIL the notify so WeChat retries
        assert resp.status_code == 503
        assert resp.json() == {"code": "FAIL", "message": "处理失败，请重试"}
        mock_session.rollback.assert_awaited_once()


class TestPaymentStatus:
    @patch("api.routes.payment.wechat_pay_v3")
    @patch("api.routes.payment._wechat_available", True)
    def test_pending_order(self, mock_wechat, _setup_overrides):
        _, mock_svc = _setup_overrides
        mock_order = MagicMock()
        mock_order.status = "PENDING"
        mock_order.user_id = 1
        mock_svc.get_user_order.return_value = mock_order
        mock_wechat.query_order.return_value = {
            "success": True,
            "trade_state": "NOTPAY",
        }
        resp = client.get("/api/payments/test_ord_123/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "PENDING"
        assert data["trade_state"] == "NOTPAY"

    def test_success_order(self, _setup_overrides):
        _, mock_svc = _setup_overrides
        mock_order = MagicMock()
        mock_order.status = "SUCCESS"
        mock_order.user_id = 1
        mock_svc.get_user_order.return_value = mock_order
        resp = client.get("/api/payments/test_ord_456/status")
        assert resp.status_code == 200
        assert resp.json()["status"] == "SUCCESS"

    def test_not_found(self, _setup_overrides):
        _, mock_svc = _setup_overrides
        mock_svc.get_user_order.return_value = None
        resp = client.get("/api/payments/nonexistent/status")
        assert resp.status_code == 404

    def test_wrong_user(self, _setup_overrides):
        _, mock_svc = _setup_overrides
        mock_svc.get_user_order.return_value = None
        resp = client.get("/api/payments/test_ord_789/status")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    @patch("api.routes.payment.wechat_pay_v3")
    @patch("api.routes.payment._wechat_available", True)
    async def test_query_success_applies_wechat_validation_and_persists_txid(
        self,
        mock_wechat,
        db_session,
        test_user,
        monkeypatch,
    ):
        from api.routes.payment import get_payment_status
        from services import overflow_service as _ovf
        from db import subscriptions as _subs
        import services.payment_service as payment_service

        monkeypatch.setattr(payment_service.time, "time", lambda: 1_700_000_000)
        monkeypatch.setattr(_subs, "get_plan_by_code", AsyncMock(return_value=None))
        monkeypatch.setattr(_subs, "_count_active_rules", AsyncMock(return_value=0))
        monkeypatch.setattr(_ovf, "restore_all_overflow", AsyncMock(return_value=0))

        order_id = "status_success_ord"
        order = PaymentOrder(
            order_id=order_id,
            user_id=test_user["id"],
            amount=2990,
            description="订阅专业版",
            duration="month",
            status="PENDING",
            created_at=int(time.time()),
        )
        db_session.add(order)
        await db_session.flush()
        order_pk = order.id
        await db_session.commit()
        order = await db_session.get(PaymentOrder, order_pk)
        mock_wechat.query_order.return_value = {
            "success": True,
            "trade_state": "SUCCESS",
            "data": {
                "out_trade_no": order_id,
                "transaction_id": "wx_tx_123",
                "amount": {"total": 2990, "currency": "CNY"},
                "appid": None,
                "mchid": None,
            },
        }
        real_svc = __import__(
            "services.payment_service", fromlist=["PaymentService"]
        ).PaymentService(db_session)
        real_svc.get_user_order = AsyncMock(return_value=order)
        real_apply = real_svc.apply_wechat_payment_success
        real_svc.apply_wechat_payment_success = AsyncMock(side_effect=real_apply)
        svc = real_svc

        resp = await get_payment_status(order_id, test_user["id"], svc)

        assert resp.status == "SUCCESS"
        svc.apply_wechat_payment_success.assert_awaited_once_with(
            out_trade_no=order_id,
            transaction_id="wx_tx_123",
            amount_total=2990,
            currency="CNY",
            appid=None,
            mchid=None,
            raw_notify=mock_wechat.query_order.return_value["data"],
        )
        await db_session.refresh(order)
        assert order.status == "SUCCESS"
        assert order.wechat_transaction_id == "wx_tx_123"
        svc.get_user_order.assert_awaited_once_with(order_id, test_user["id"])

    @pytest.mark.asyncio
    @patch("api.routes.payment.wechat_pay_v3")
    @patch("api.routes.payment._wechat_available", True)
    async def test_query_success_amount_mismatch_keeps_pending(
        self,
        mock_wechat,
        db_session,
        test_user,
        monkeypatch,
    ):
        from api.routes.payment import get_payment_status
        from services import overflow_service as _ovf
        from db import subscriptions as _subs
        import services.payment_service as payment_service

        monkeypatch.setattr(payment_service.time, "time", lambda: 1_700_000_000)
        monkeypatch.setattr(_subs, "get_plan_by_code", AsyncMock(return_value=None))
        monkeypatch.setattr(_subs, "_count_active_rules", AsyncMock(return_value=0))
        monkeypatch.setattr(_ovf, "restore_all_overflow", AsyncMock(return_value=0))

        order_id = "status_mismatch_ord"
        order = PaymentOrder(
            order_id=order_id,
            user_id=test_user["id"],
            amount=2990,
            description="订阅专业版",
            duration="month",
            status="PENDING",
            created_at=int(time.time()),
        )
        db_session.add(order)
        await db_session.flush()
        order_pk = order.id
        await db_session.commit()
        order = await db_session.get(PaymentOrder, order_pk)
        mock_wechat.query_order.return_value = {
            "success": True,
            "trade_state": "SUCCESS",
            "data": {
                "out_trade_no": order_id,
                "transaction_id": "wx_tx_bad_amount",
                "amount": {"total": 1990, "currency": "CNY"},
                "appid": None,
                "mchid": None,
            },
        }
        real_svc = __import__(
            "services.payment_service", fromlist=["PaymentService"]
        ).PaymentService(db_session)
        real_svc.get_user_order = AsyncMock(return_value=order)
        real_apply = real_svc.apply_wechat_payment_success
        real_svc.apply_wechat_payment_success = AsyncMock(side_effect=real_apply)
        svc = real_svc

        resp = await get_payment_status(order_id, test_user["id"], svc)

        assert resp.status == "PENDING"
        svc.apply_wechat_payment_success.assert_awaited_once()
        stored_order = await db_session.get(PaymentOrder, order_pk)
        assert stored_order.status == "PENDING"
        assert stored_order.wechat_transaction_id is None
