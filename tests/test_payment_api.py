import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402
from api.main import app  # noqa: E402
from api import dependencies  # noqa: E402
from database import get_db  # noqa: E402

MOCK_USER = {
    "id": 1,
    "username": "testuser",
    "role": "user",
    "user_type": "professional",
    "remaining_calculations": 100,
}

client = TestClient(app, raise_server_exceptions=False)


def _mock_session():
    s = MagicMock()
    s.flush = AsyncMock()
    s.commit = AsyncMock()
    return s


@pytest.fixture(autouse=True)
def _setup_overrides():
    app.dependency_overrides[dependencies.get_current_user_id] = lambda: 1
    app.dependency_overrides[dependencies.get_current_user] = lambda: MOCK_USER
    ms = _mock_session()
    app.dependency_overrides[get_db] = lambda: ms
    yield ms
    app.dependency_overrides.pop(dependencies.get_current_user_id, None)
    app.dependency_overrides.pop(dependencies.get_current_user, None)
    app.dependency_overrides.pop(get_db, None)


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
    def test_success(self, mock_price, mock_plan, mock_wechat):
        mock_price.return_value = 29.9
        mock_plan.return_value = {"plan_name": "Pro"}
        mock_wechat.create_native_order.return_value = {
            "success": True,
            "code_url": "weixin://test",
        }
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
    def test_amount_mismatch(self, mock_price):
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
    def test_wechat_unavailable(self, mock_price, mock_plan):
        mock_price.return_value = 29.9
        mock_plan.return_value = {"plan_name": "Pro"}
        resp = client.post(
            "/api/payments/create",
            json={
                "plan_code": "pro",
                "billing_cycle": "month",
                "amount": 29.9,
            },
        )
        assert resp.status_code == 502
        assert resp.json().get("error") == "wechat_error"

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
    def test_wechat_fails(self, mock_price, mock_plan, mock_wechat):
        mock_price.return_value = 29.9
        mock_plan.return_value = {"plan_name": "Pro"}
        mock_wechat.create_native_order.return_value = {
            "success": False,
            "message": "失败",
        }
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
    @patch(
        "api.routes.payment._handle_payment_success_task",
        new_callable=AsyncMock,
    )
    @patch("api.routes.payment.wechat_pay_v3")
    @patch("api.routes.payment._wechat_available", True)
    @patch(
        "api.routes.payment._get_order",
        new_callable=AsyncMock,
    )
    def test_success(self, mock_get_order, mock_wechat, mock_handle):
        mock_get_order.return_value = None
        mock_wechat.process_notify.return_value = {
            "success": True,
            "trade_state": "SUCCESS",
            "out_trade_no": "test_notify_ord",
        }
        resp = client.post(
            "/api/payments/notify",
            json={"out_trade_no": "test_notify_ord"},
        )
        assert resp.status_code == 200
        assert resp.json()["code"] == "SUCCESS"

    @patch("api.routes.payment.wechat_pay_v3")
    @patch(
        "api.routes.payment._get_order",
        new_callable=AsyncMock,
    )
    def test_idempotent(self, mock_get_order, mock_wechat):
        mock_order = MagicMock()
        mock_order.status = "SUCCESS"
        mock_get_order.return_value = mock_order
        resp = client.post(
            "/api/payments/notify",
            json={"out_trade_no": "test_idemp_ord"},
        )
        assert resp.status_code == 200
        assert resp.json()["code"] == "SUCCESS"
        mock_wechat.process_notify.assert_not_called()

    @patch("api.routes.payment._wechat_available", False)
    @patch(
        "api.routes.payment._get_order",
        new_callable=AsyncMock,
    )
    def test_wechat_unavailable(self, mock_get_order):
        mock_get_order.return_value = None
        resp = client.post(
            "/api/payments/notify",
            json={},
        )
        assert resp.status_code == 400


class TestPaymentStatus:
    @patch("api.routes.payment.wechat_pay_v3")
    @patch("api.routes.payment._wechat_available", True)
    @patch(
        "api.routes.payment._get_order",
        new_callable=AsyncMock,
    )
    def test_pending_order(self, mock_get_order, mock_wechat):
        mock_order = MagicMock()
        mock_order.status = "PENDING"
        mock_order.user_id = 1
        mock_get_order.return_value = mock_order
        mock_wechat.query_order.return_value = {
            "success": True,
            "trade_state": "NOTPAY",
        }
        resp = client.get("/api/payments/test_ord_123/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "PENDING"
        assert data["trade_state"] == "NOTPAY"

    @patch(
        "api.routes.payment._get_order",
        new_callable=AsyncMock,
    )
    def test_success_order(self, mock_get_order):
        mock_order = MagicMock()
        mock_order.status = "SUCCESS"
        mock_order.user_id = 1
        mock_get_order.return_value = mock_order
        resp = client.get("/api/payments/test_ord_456/status")
        assert resp.status_code == 200
        assert resp.json()["status"] == "SUCCESS"

    @patch(
        "api.routes.payment._get_order",
        new_callable=AsyncMock,
    )
    def test_not_found(self, mock_get_order):
        mock_get_order.return_value = None
        resp = client.get("/api/payments/nonexistent/status")
        assert resp.status_code == 404

    @patch(
        "api.routes.payment._get_order",
        new_callable=AsyncMock,
    )
    def test_wrong_user(self, mock_get_order):
        mock_order = MagicMock()
        mock_order.status = "PENDING"
        mock_order.user_id = 2
        mock_get_order.return_value = mock_order
        resp = client.get("/api/payments/test_ord_789/status")
        assert resp.status_code == 404
