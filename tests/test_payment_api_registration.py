# -*- coding: utf-8 -*-
"""
api/routes/payment.py 单元测试
测试 create_payment 端点根据开放注册设置使用不同价格
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestCreatePaymentWithRegistrationStatus:
    """测试 create_payment 根据注册开放状态选择价格"""

    @pytest.fixture
    def mock_session(self):
        session = AsyncMock()
        return session

    @pytest.fixture
    def mock_get_plan_price(self):
        with patch("api.routes.payment.get_plan_price") as mock:
            yield mock

    @pytest.fixture
    def mock_is_registration_open(self):
        with patch("api.routes.payment.is_registration_open") as mock:
            yield mock

    @pytest.fixture
    def mock_get_plan_by_code(self):
        with patch("api.routes.payment.get_plan_by_code") as mock:
            yield mock

    @pytest.mark.asyncio
    async def test_registration_open_uses_actual_price(
        self, mock_session, mock_get_plan_price, mock_is_registration_open, mock_get_plan_by_code
    ):
        """当注册开放时，应使用 actual_price"""
        from api.routes.payment import create_payment, CreatePaymentRequest

        mock_is_registration_open.return_value = True
        mock_get_plan_price.return_value = 79.0
        mock_get_plan_by_code.return_value = {"plan_name": "效率版"}

        with patch("api.routes.payment.PaymentService") as MockService:
            mock_svc = AsyncMock()
            mock_order = MagicMock()
            mock_order.order_id = "test_order_123"
            mock_order.description = "订阅效率版"
            mock_svc.create_order = AsyncMock(return_value=mock_order)
            MockService.return_value = mock_svc

            with patch("api.routes.payment.wechat_pay_v3") as mock_wechat:
                mock_wechat.create_native_order.return_value = {
                    "success": True,
                    "code_url": "weixin://pay/test"
                }

                req = CreatePaymentRequest(
                    plan_code="efficiency",
                    billing_cycle="month",
                    amount=79.0
                )

                response = await create_payment(
                    req=req,
                    user_id=1,
                    session=mock_session,
                    svc=mock_svc
                )

                mock_is_registration_open.assert_called_once_with(mock_session)
                mock_get_plan_price.assert_called_once_with(
                    mock_session, "efficiency", "month", use_test_price=False
                )
                assert response.code_url == "weixin://pay/test"

    @pytest.mark.asyncio
    async def test_registration_closed_uses_test_price(
        self, mock_session, mock_get_plan_price, mock_is_registration_open, mock_get_plan_by_code
    ):
        """当注册关闭时，应使用 test_price"""
        from api.routes.payment import create_payment, CreatePaymentRequest

        mock_is_registration_open.return_value = False
        mock_get_plan_price.return_value = 0.01
        mock_get_plan_by_code.return_value = {"plan_name": "效率版"}

        with patch("api.routes.payment.PaymentService") as MockService:
            mock_svc = AsyncMock()
            mock_order = MagicMock()
            mock_order.order_id = "test_order_456"
            mock_order.description = "订阅效率版"
            mock_svc.create_order = AsyncMock(return_value=mock_order)
            MockService.return_value = mock_svc

            with patch("api.routes.payment.wechat_pay_v3") as mock_wechat:
                mock_wechat.create_native_order.return_value = {
                    "success": True,
                    "code_url": "weixin://pay/test"
                }

                req = CreatePaymentRequest(
                    plan_code="efficiency",
                    billing_cycle="month",
                    amount=0.01
                )

                response = await create_payment(
                    req=req,
                    user_id=1,
                    session=mock_session,
                    svc=mock_svc
                )

                mock_is_registration_open.assert_called_once_with(mock_session)
                mock_get_plan_price.assert_called_once_with(
                    mock_session, "efficiency", "month", use_test_price=True
                )
                assert response.code_url == "weixin://pay/test"

    @pytest.mark.asyncio
    async def test_registration_open_yearly_uses_actual_price(
        self, mock_session, mock_get_plan_price, mock_is_registration_open, mock_get_plan_by_code
    ):
        """当注册开放时，年付应使用 actual_price_year"""
        from api.routes.payment import create_payment, CreatePaymentRequest

        mock_is_registration_open.return_value = True
        mock_get_plan_price.return_value = 790.0
        mock_get_plan_by_code.return_value = {"plan_name": "效率版"}

        with patch("api.routes.payment.PaymentService") as MockService:
            mock_svc = AsyncMock()
            mock_order = MagicMock()
            mock_order.order_id = "test_order_789"
            mock_order.description = "订阅效率版"
            mock_svc.create_order = AsyncMock(return_value=mock_order)
            MockService.return_value = mock_svc

            with patch("api.routes.payment.wechat_pay_v3") as mock_wechat:
                mock_wechat.create_native_order.return_value = {
                    "success": True,
                    "code_url": "weixin://pay/test"
                }

                req = CreatePaymentRequest(
                    plan_code="efficiency",
                    billing_cycle="year",
                    amount=790.0
                )

                response = await create_payment(
                    req=req,
                    user_id=1,
                    session=mock_session,
                    svc=mock_svc
                )

                mock_get_plan_price.assert_called_once_with(
                    mock_session, "efficiency", "year", use_test_price=False
                )

    @pytest.mark.asyncio
    async def test_registration_closed_yearly_uses_test_price(
        self, mock_session, mock_get_plan_price, mock_is_registration_open, mock_get_plan_by_code
    ):
        """当注册关闭时，年付应使用 test_price_year"""
        from api.routes.payment import create_payment, CreatePaymentRequest

        mock_is_registration_open.return_value = False
        mock_get_plan_price.return_value = 79.0
        mock_get_plan_by_code.return_value = {"plan_name": "效率版"}

        with patch("api.routes.payment.PaymentService") as MockService:
            mock_svc = AsyncMock()
            mock_order = MagicMock()
            mock_order.order_id = "test_order_101"
            mock_order.description = "订阅效率版"
            mock_svc.create_order = AsyncMock(return_value=mock_order)
            MockService.return_value = mock_svc

            with patch("api.routes.payment.wechat_pay_v3") as mock_wechat:
                mock_wechat.create_native_order.return_value = {
                    "success": True,
                    "code_url": "weixin://pay/test"
                }

                req = CreatePaymentRequest(
                    plan_code="efficiency",
                    billing_cycle="year",
                    amount=79.0
                )

                response = await create_payment(
                    req=req,
                    user_id=1,
                    session=mock_session,
                    svc=mock_svc
                )

                mock_get_plan_price.assert_called_once_with(
                    mock_session, "efficiency", "year", use_test_price=True
                )

    @pytest.mark.asyncio
    async def test_amount_mismatch_when_registration_open(
        self, mock_session, mock_get_plan_price, mock_is_registration_open, mock_get_plan_by_code
    ):
        """当注册开放时，金额不匹配应返回错误"""
        from api.routes.payment import create_payment, CreatePaymentRequest

        mock_is_registration_open.return_value = True
        mock_get_plan_price.return_value = 79.0
        mock_get_plan_by_code.return_value = {"plan_name": "效率版"}

        with patch("api.routes.payment.PaymentService") as MockService:
            mock_svc = AsyncMock()
            MockService.return_value = mock_svc

            req = CreatePaymentRequest(
                plan_code="efficiency",
                billing_cycle="month",
                amount=99.0
            )

            response = await create_payment(
                req=req,
                user_id=1,
                session=mock_session,
                svc=mock_svc
            )

            assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_amount_mismatch_when_registration_closed(
        self, mock_session, mock_get_plan_price, mock_is_registration_open, mock_get_plan_by_code
    ):
        """当注册关闭时，金额不匹配（与测试价不匹配）应返回错误"""
        from api.routes.payment import create_payment, CreatePaymentRequest

        mock_is_registration_open.return_value = False
        mock_get_plan_price.return_value = 0.01
        mock_get_plan_by_code.return_value = {"plan_name": "效率版"}

        with patch("api.routes.payment.PaymentService") as MockService:
            mock_svc = AsyncMock()
            MockService.return_value = mock_svc

            req = CreatePaymentRequest(
                plan_code="efficiency",
                billing_cycle="month",
                amount=0.02
            )

            response = await create_payment(
                req=req,
                user_id=1,
                session=mock_session,
                svc=mock_svc
            )

            assert response.status_code == 400


class TestIsRegistrationOpenImport:
    """测试 is_registration_open 正确导入"""

    def test_import_success(self):
        from api.routes.payment import is_registration_open
        assert callable(is_registration_open)

    def test_get_plan_price_accepts_use_test_price(self):
        from db.plans import get_plan_price
        import inspect
        sig = inspect.signature(get_plan_price)
        params = list(sig.parameters.keys())
        assert "use_test_price" in params
