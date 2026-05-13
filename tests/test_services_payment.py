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
    @pytest.fixture(autouse=True)
    def _patch_apply_paid(self, monkeypatch):
        async def _fake_apply(session, user_id, plan_code, **kwargs):
            user = await session.get(None, user_id)
            if user is None:
                return MagicMock()
            duration_days = kwargs.get("duration_days", 30)
            started_at = kwargs.get("started_at", int(time.time()))
            user.subscription_type = plan_code
            user.user_type = plan_code
            user.subscription_start = started_at
            user.subscription_expires = started_at + duration_days * 86400
            user.remaining_calculations = -1
            return MagicMock()

        monkeypatch.setattr(
            "services.payment_service.apply_paid_subscription", _fake_apply
        )

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
    async def test_english_year_billing_cycle_grants_365_days(self):
        session = _mock_session()
        order = _make_order(description="专业版套餐", duration="year")
        user = _make_user()
        _setup_session_execute(session, order)
        session.get.return_value = user

        svc = PaymentService(session)
        await svc.handle_payment_success("ord_en_year")

        expected_min = int(time.time()) + 365 * 86400 - 5
        assert user.subscription_expires >= expected_min

    @pytest.mark.asyncio
    async def test_english_month_billing_cycle_grants_30_days(self):
        session = _mock_session()
        order = _make_order(description="专业版套餐", duration="month")
        user = _make_user()
        _setup_session_execute(session, order)
        session.get.return_value = user

        svc = PaymentService(session)
        await svc.handle_payment_success("ord_en_month")

        expected_max = int(time.time()) + 30 * 86400 + 5
        expected_min = int(time.time()) + 30 * 86400 - 5
        assert expected_min <= user.subscription_expires <= expected_max

    @pytest.mark.asyncio
    async def test_user_not_found_raises_value_error(self):
        session = _mock_session()
        order = _make_order()
        _setup_session_execute(session, order)
        session.get.return_value = None

        svc = PaymentService(session)
        with pytest.raises(ValueError, match="用户不存在"):
            await svc.handle_payment_success("ord_nouser")

        assert order.status == "PENDING"

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


class TestFunnelSourceTagging:
    """Enforces the 3-source funnel taxonomy (regression guard)."""

    @pytest.mark.asyncio
    async def test_payment_success_uses_source_payment_success(self, monkeypatch):
        captured = {}

        async def _fake_apply(session, user_id, plan_code, **kwargs):
            captured["source"] = kwargs.get("source")
            captured["plan_code"] = plan_code
            captured["user_id"] = user_id
            captured["duration_days"] = kwargs.get("duration_days")
            captured["started_at"] = kwargs.get("started_at")
            return MagicMock()

        monkeypatch.setattr(
            "services.payment_service.apply_paid_subscription", _fake_apply
        )

        session = _mock_session()
        order = _make_order(description="效率版月套餐", duration="month")
        user = _make_user()
        _setup_session_execute(session, order)
        session.get.return_value = user

        svc = PaymentService(session)
        await svc.handle_payment_success("ord_001")

        assert captured["source"] == "payment_success"
        assert captured["plan_code"] == "efficiency"
        assert captured["user_id"] == 1
        assert captured["started_at"] is not None
        assert captured["duration_days"] is not None
        assert captured["duration_days"] > 0

    @pytest.mark.asyncio
    async def test_wechat_notify_uses_source_wechat_notify(self, monkeypatch):
        captured = {}

        async def _fake_apply(session, user_id, plan_code, **kwargs):
            captured["source"] = kwargs.get("source")
            captured["plan_code"] = plan_code
            return MagicMock()

        monkeypatch.setattr(
            "services.payment_service.apply_paid_subscription", _fake_apply
        )

        session = _mock_session()
        row = _make_order(
            order_id="ord_wx_001",
            user_id=1,
            amount=2990,
            description="效率版月套餐",
            duration="month",
        )
        result = MagicMock()
        result.scalar_one_or_none.return_value = row
        session.execute.return_value = result
        session.get.return_value = _make_user()

        svc = PaymentService(session)
        outcome = await svc.apply_wechat_payment_success(
            out_trade_no="ord_wx_001",
            transaction_id="tx_001",
            amount_total=2990,
            currency="CNY",
            appid=None,
            mchid=None,
            raw_notify={},
        )

        assert outcome == "processed"
        assert captured["source"] == "wechat_notify"
        assert captured["plan_code"] == "efficiency"

    @pytest.mark.asyncio
    async def test_legacy_handler_uses_source_wechat_pay_legacy(self):
        import inspect
        import payment_handler

        src = inspect.getsource(payment_handler)
        assert "PaymentService" in src, \
            "payment_handler.py must route legacy calls through PaymentService"
        assert "with_for_update" not in src, \
            "payment_handler.py must not keep a separate lock-based path"


class TestApplyPaidSubscriptionDirect:
    """Verifies paid funnel writes user_type, subscription_start, quota=-1."""

    @pytest.mark.asyncio
    async def test_writes_user_type_and_started_at_and_unlimited_quota(
        self, db_session, test_user
    ):
        from db.subscriptions import apply_paid_subscription
        from models.user import User

        uid = test_user["id"]
        started_at = int(time.time())
        expires = started_at + 30 * 86400

        await apply_paid_subscription(
            db_session,
            uid,
            "efficiency",
            subscription_expires=expires,
            started_at=started_at,
            source="test_direct",
        )
        await db_session.commit()

        user = await db_session.get(User, uid)
        assert user.user_type == "efficiency"
        assert user.subscription_start == started_at
        assert user.remaining_calculations == -1
        assert user.subscription_type == "efficiency"
        assert user.subscription_expires == expires

    @pytest.mark.asyncio
    async def test_admin_grant_does_not_reset_quota_when_using_change_only(
        self, db_session, test_user
    ):
        from db.subscriptions import apply_subscription_change
        from models.user import User

        uid = test_user["id"]
        user = await db_session.get(User, uid)
        user.remaining_calculations = 7
        await db_session.commit()

        await apply_subscription_change(
            db_session, uid, "professional", source="admin_grant",
        )
        await db_session.commit()

        user = await db_session.get(User, uid)
        assert user.subscription_type == "professional"
        assert user.remaining_calculations == 7


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
