# -*- coding: utf-8 -*-
import time
import pytest
from unittest.mock import AsyncMock, MagicMock

from services.payment_service import PaymentService


def _mock_session():
    s = AsyncMock()
    s.add = MagicMock()
    return s


def _make_order(
    order_id="ord_001",
    user_id=1,
    amount=2990,
    description="订阅效率版",
    duration="month",
    status="PENDING",
):
    o = MagicMock()
    o.order_id = order_id
    o.user_id = user_id
    o.amount = amount
    o.description = description
    o.duration = duration
    o.status = status
    o.updated_at = None
    return o


def _make_user(uid=1):
    u = MagicMock()
    u.id = uid
    u.subscription_type = "free"
    u.subscription_expires = None
    u.remaining_calculations = 0
    return u


def _setup_session_execute(session, order=None):
    result = MagicMock()
    result.scalar_one_or_none.return_value = order
    session.execute.return_value = result


class TestPaymentServiceInit:
    def test_accepts_async_session(self):
        session = _mock_session()
        svc = PaymentService(session)
        assert svc is not None


class TestHandlePaymentSuccess:
    @pytest.mark.asyncio
    async def test_updates_order_and_user_subscription(self):
        session = _mock_session()
        order = _make_order(
            description="效率版月套餐",
            duration="1月",
        )
        user = _make_user()
        _setup_session_execute(session, order)
        session.get.return_value = user

        svc = PaymentService(session)
        await svc.handle_payment_success("ord_001")

        assert order.status == "SUCCESS"
        assert order.updated_at is not None
        assert user.subscription_type == "efficiency"
        assert user.remaining_calculations == -1
        expected_min = int(time.time()) + 30 * 86400 - 5
        expected_max = int(time.time()) + 30 * 86400 + 5
        assert expected_min <= user.subscription_expires <= expected_max

    @pytest.mark.asyncio
    async def test_order_not_found_raises_value_error(self):
        session = _mock_session()
        _setup_session_execute(session, None)

        svc = PaymentService(session)
        with pytest.raises(ValueError, match="ord_missing"):
            await svc.handle_payment_success("ord_missing")

    @pytest.mark.asyncio
    async def test_idempotent_when_already_success(self):
        session = _mock_session()
        order = _make_order(status="SUCCESS")
        _setup_session_execute(session, order)

        svc = PaymentService(session)
        await svc.handle_payment_success("ord_dup")

        # Unit of Work: no commit assertions — get_db handles transactions
        # Verify idempotency: order status unchanged, user lookup skipped
        assert order.status == "SUCCESS"
        session.get.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_plan_code_professional(self):
        session = _mock_session()
        order = _make_order(description="专业版年套餐", duration="1年")
        user = _make_user()
        _setup_session_execute(session, order)
        session.get.return_value = user

        svc = PaymentService(session)
        await svc.handle_payment_success("ord_pro")

        assert user.subscription_type == "professional"
        expected_min = int(time.time()) + 365 * 86400 - 5
        assert user.subscription_expires >= expected_min

    @pytest.mark.asyncio
    async def test_plan_code_enterprise(self):
        session = _mock_session()
        order = _make_order(description="企业版月套餐", duration="1月")
        user = _make_user()
        _setup_session_execute(session, order)
        session.get.return_value = user

        svc = PaymentService(session)
        await svc.handle_payment_success("ord_ent")

        assert user.subscription_type == "enterprise"

    @pytest.mark.asyncio
    async def test_user_not_found_still_updates_order(self):
        session = _mock_session()
        order = _make_order()
        _setup_session_execute(session, order)
        session.get.return_value = None

        svc = PaymentService(session)
        await svc.handle_payment_success("ord_nouser")

        assert order.status == "SUCCESS"

    @pytest.mark.asyncio
    async def test_db_error_propagated(self):
        session = _mock_session()
        session.execute.side_effect = Exception("db boom")

        svc = PaymentService(session)
        with pytest.raises(Exception, match="db boom"):
            await svc.handle_payment_success("ord_err")


class TestUpdateOrderStatus:
    @pytest.mark.asyncio
    async def test_updates_status_and_timestamp(self):
        session = _mock_session()
        order = _make_order(status="PENDING")
        _setup_session_execute(session, order)

        svc = PaymentService(session)
        await svc.update_order_status("ord_upd", "PAID")

        assert order.status == "PAID"
        assert order.updated_at is not None

    @pytest.mark.asyncio
    async def test_order_not_found_silent(self):
        session = _mock_session()
        _setup_session_execute(session, None)

        svc = PaymentService(session)
        await svc.update_order_status("ord_gone", "PAID")

    @pytest.mark.asyncio
    async def test_db_error_propagated(self):
        session = _mock_session()
        session.execute.side_effect = Exception("update fail")

        svc = PaymentService(session)
        with pytest.raises(Exception, match="update fail"):
            await svc.update_order_status("ord_fail", "PAID")


class TestCreateOrder:
    @pytest.mark.asyncio
    async def test_creates_payment_order(self):
        session = _mock_session()

        svc = PaymentService(session)
        order = await svc.create_order(
            user_id=1,
            amount_cents=2990,
            description="订阅效率版",
            billing_cycle="month",
            order_type="efficiency",
        )

        assert order.user_id == 1
        assert order.amount == 2990
        assert order.description == "订阅效率版"
        assert order.duration == "month"
        assert order.order_type == "efficiency"
        assert order.status == "PENDING"
        assert order.created_at is not None
        assert order.order_id is not None and len(order.order_id) > 0
        session.add.assert_called_once()
        session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_order_id_is_unique(self):
        session = _mock_session()
        svc = PaymentService(session)

        o1 = await svc.create_order(
            user_id=1,
            amount_cents=100,
            description="a",
            billing_cycle="month",
            order_type="free",
        )
        o2 = await svc.create_order(
            user_id=1,
            amount_cents=100,
            description="b",
            billing_cycle="month",
            order_type="free",
        )
        assert o1.order_id != o2.order_id


class TestGetOrder:
    @pytest.mark.asyncio
    async def test_found(self):
        session = _mock_session()
        order = _make_order()
        _setup_session_execute(session, order)

        svc = PaymentService(session)
        result = await svc.get_order("ord_001")

        assert result is order

    @pytest.mark.asyncio
    async def test_not_found(self):
        session = _mock_session()
        _setup_session_execute(session, None)

        svc = PaymentService(session)
        result = await svc.get_order("ord_nope")

        assert result is None


class TestGetUserOrder:
    @pytest.mark.asyncio
    async def test_found_correct_user(self):
        session = _mock_session()
        order = _make_order(user_id=1)
        _setup_session_execute(session, order)

        svc = PaymentService(session)
        result = await svc.get_user_order("ord_001", user_id=1)

        assert result is order

    @pytest.mark.asyncio
    async def test_found_wrong_user(self):
        session = _mock_session()
        order = _make_order(user_id=2)
        _setup_session_execute(session, order)

        svc = PaymentService(session)
        result = await svc.get_user_order("ord_001", user_id=1)

        assert result is None

    @pytest.mark.asyncio
    async def test_not_found(self):
        session = _mock_session()
        _setup_session_execute(session, None)

        svc = PaymentService(session)
        result = await svc.get_user_order("ord_nope", user_id=1)

        assert result is None
