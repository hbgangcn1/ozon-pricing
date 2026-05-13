import builtins
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import services.payment_service as payment_service
from services.payment_service import (
    PaymentService,
    SuspiciousWechatNotifyError,
)


def _session():
    session = AsyncMock()
    session.add = MagicMock()
    return session


def _execute_result(*, first=None, scalar=None):
    result = MagicMock()
    result.first.return_value = first
    result.scalar_one_or_none.return_value = scalar if scalar is not None else first
    return result


def _order(**overrides):
    data = {
        "order_id": "ord-1",
        "user_id": 7,
        "amount": 2990,
        "description": "默认套餐",
        "duration": "按月",
        "status": "PENDING",
        "wechat_transaction_id": None,
        "updated_at": None,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def _user(**overrides):
    data = {
        "id": 7,
        "subscription_type": "free",
        "user_type": "free",
        "subscription_expires": None,
        "subscription_start": None,
        "remaining_calculations": 0,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_plan_code_and_duration_helpers_cover_all_branches():
    extract_plan_code = getattr(payment_service, "_extract_plan_code")
    parse_duration = getattr(payment_service, "_parse_duration")

    assert extract_plan_code("普通描述") == "efficiency"
    assert extract_plan_code("效率版月套餐") == "efficiency"
    assert extract_plan_code("专业版月套餐") == "professional"
    assert extract_plan_code("企业版年套餐") == "enterprise"
    assert parse_duration("1年") == 365
    assert parse_duration("1月") == 30
    assert parse_duration("unknown") == 30


def test_redact_txid_handles_empty_and_value():
    redact_txid = getattr(payment_service, "_redact_txid")

    assert redact_txid(None) == "<empty>"
    assert redact_txid("") == "<empty>"
    assert redact_txid("4200001234567890") == "***567890"


@pytest.mark.asyncio
async def test_apply_wechat_payment_success_duplicate_cas(monkeypatch):
    session = _session()
    session.execute.return_value = _execute_result(first=None)
    existing = _order(status="SUCCESS", wechat_transaction_id="wx-tx-1")
    service = PaymentService(session)
    service.get_order = AsyncMock(return_value=existing)
    monkeypatch.setattr(payment_service.time, "time", lambda: 1_700_000_000)

    result = await service.apply_wechat_payment_success(
        out_trade_no="ord-1",
        transaction_id="wx-tx-1",
        amount_total=2990,
        currency="CNY",
        appid=None,
        mchid=None,
        raw_notify={},
    )

    assert result == "duplicate"


@pytest.mark.asyncio
async def test_apply_wechat_payment_success_amount_mismatch(monkeypatch):
    session = _session()
    session.execute.return_value = _execute_result(
        first=SimpleNamespace(
            id=1,
            user_id=7,
            amount=1990,
            description="效率版月套餐",
            duration="1月",
            status="PENDING",
        )
    )
    service = PaymentService(session)
    monkeypatch.setattr(payment_service.time, "time", lambda: 1_700_000_000)

    with pytest.raises(SuspiciousWechatNotifyError, match="amount mismatch"):
        await service.apply_wechat_payment_success(
            out_trade_no="ord-1",
            transaction_id="wx-tx-2",
            amount_total=2990,
            currency="CNY",
            appid=None,
            mchid=None,
            raw_notify={},
        )


@pytest.mark.asyncio
async def test_apply_wechat_payment_success_user_missing(monkeypatch):
    session = _session()
    session.execute.return_value = _execute_result(
        first=SimpleNamespace(
            id=1,
            user_id=7,
            amount=2990,
            description="效率版月套餐",
            duration="1月",
            status="PENDING",
        )
    )
    session.get.return_value = None
    service = PaymentService(session)
    monkeypatch.setattr(payment_service.time, "time", lambda: 1_700_000_000)

    with pytest.raises(SuspiciousWechatNotifyError, match="user not found"):
        await service.apply_wechat_payment_success(
            out_trade_no="ord-1",
            transaction_id="wx-tx-3",
            amount_total=2990,
            currency="CNY",
            appid=None,
            mchid=None,
            raw_notify={},
        )


@pytest.mark.asyncio
async def test_apply_wechat_payment_success_happy_path(monkeypatch):
    session = _session()
    session.execute.return_value = _execute_result(
        first=SimpleNamespace(
            id=1,
            user_id=7,
            amount=2990,
            description="企业版年套餐",
            duration="1年",
            status="PENDING",
            plan_code="enterprise",
        )
    )
    user = _user()
    session.get.return_value = user
    service = PaymentService(session)
    from datetime import datetime, timezone
    fixed_dt = datetime.fromtimestamp(1_700_000_000, timezone.utc)
    monkeypatch.setattr(payment_service, "_utc_now", lambda: fixed_dt)
    monkeypatch.setattr(payment_service.time, "time", lambda: 1_700_000_000)

    captured = {}

    async def _fake_apply(sess, user_id, plan_code, **kwargs):
        captured["plan_code"] = plan_code
        captured["kwargs"] = kwargs
        user.user_type = plan_code
        user.subscription_type = plan_code
        user.subscription_start = kwargs.get("started_at")
        user.remaining_calculations = -1
        return {"ok": True}

    monkeypatch.setattr(
        "services.payment_service.apply_paid_subscription", _fake_apply
    )

    result = await service.apply_wechat_payment_success(
        out_trade_no="ord-1",
        transaction_id="wx-tx-4",
        amount_total=2990,
        currency="CNY",
        appid=None,
        mchid=None,
        raw_notify={"id": "notify-1"},
    )

    assert result == "processed"
    assert user.user_type == "enterprise"
    assert user.subscription_start == 1_700_000_000
    assert user.remaining_calculations == -1


@pytest.mark.asyncio
async def test_handle_payment_success_happy_path(monkeypatch):
    session = _session()
    order = _order(description="专业版月套餐", duration="1月")
    user = _user()
    session.execute.return_value = _execute_result(scalar=order)
    session.get.return_value = user
    service = PaymentService(session)
    monkeypatch.setattr(payment_service.time, "time", lambda: 1_700_001_000)
    from datetime import datetime, timezone
    fixed_dt = datetime.fromtimestamp(1_700_001_000, timezone.utc)
    monkeypatch.setattr(payment_service, "_utc_now", lambda: fixed_dt)

    captured = {}

    async def _fake_apply(sess, user_id, plan_code, **kwargs):
        captured["user_id"] = user_id
        captured["plan_code"] = plan_code
        captured["kwargs"] = kwargs
        user.subscription_type = plan_code
        user.user_type = plan_code
        user.subscription_start = kwargs.get("started_at")
        user.subscription_expires = (
            kwargs.get("started_at") + kwargs.get("duration_days") * 86400
        )
        user.remaining_calculations = -1
        return MagicMock()

    monkeypatch.setattr(
        "services.payment_service.apply_paid_subscription", _fake_apply
    )

    await service.handle_payment_success("ord-1")

    assert order.status == "SUCCESS"
    assert order.updated_at == 1_700_001_000
    assert captured["plan_code"] == "professional"
    assert captured["user_id"] == order.user_id
    assert captured["kwargs"]["source"] == "payment_success"
    assert captured["kwargs"]["duration_days"] == 30
    assert captured["kwargs"]["started_at"] == 1_700_001_000
    assert user.subscription_type == "professional"
    assert user.user_type == "professional"
    assert user.subscription_start == 1_700_001_000
    assert user.subscription_expires == 1_700_001_000 + 30 * 86400
    assert user.remaining_calculations == -1
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_payment_success_order_not_found():
    session = _session()
    session.execute.return_value = _execute_result(scalar=None)
    service = PaymentService(session)

    with pytest.raises(ValueError, match="订单不存在"):
        await service.handle_payment_success("missing-order")


@pytest.mark.asyncio
async def test_handle_payment_success_already_success_returns_early():
    session = _session()
    order = _order(status="SUCCESS")
    session.execute.return_value = _execute_result(scalar=order)
    service = PaymentService(session)

    await service.handle_payment_success("ord-1")

    session.get.assert_not_awaited()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_payment_success_user_not_found(monkeypatch):
    session = _session()
    order = _order()
    session.execute.return_value = _execute_result(scalar=order)
    session.get.return_value = None
    service = PaymentService(session)
    monkeypatch.setattr(payment_service.time, "time", lambda: 1_700_001_111)

    with pytest.raises(ValueError, match="用户不存在"):
        await service.handle_payment_success("ord-1")


@pytest.mark.asyncio
async def test_update_order_status_updates_existing_order(monkeypatch):
    session = _session()
    order = _order(status="PENDING")
    session.execute.return_value = _execute_result(scalar=order)
    service = PaymentService(session)
    monkeypatch.setattr(payment_service.time, "time", lambda: 1_700_002_000)

    await service.update_order_status("ord-1", "FAILED")

    assert order.status == "FAILED"
    assert order.updated_at == 1_700_002_000


@pytest.mark.asyncio
async def test_update_order_status_ignores_missing_order():
    session = _session()
    session.execute.return_value = _execute_result(scalar=None)
    service = PaymentService(session)

    await service.update_order_status("ord-1", "FAILED")


@pytest.mark.asyncio
async def test_create_get_and_get_user_order(monkeypatch):
    session = _session()
    created_service = PaymentService(session)
    monkeypatch.setattr(payment_service.uuid, "uuid4", lambda: SimpleNamespace(hex="fixed-order-id"))
    monkeypatch.setattr(payment_service.time, "time", lambda: 1_700_003_000)

    created = await created_service.create_order(
        user_id=9,
        amount_cents=5990,
        description="效率版月套餐",
        billing_cycle="1月",
        order_type="efficiency",
    )

    assert created.order_id == "fixed-order-id"
    assert created.user_id == 9
    assert created.amount == 5990
    assert created.status == "PENDING"
    assert created.created_at == 1_700_003_000
    session.add.assert_called_once_with(created)
    session.flush.assert_awaited_once()

    found = _order(order_id="fixed-order-id", user_id=9)
    session.execute.return_value = _execute_result(scalar=found)
    assert await created_service.get_order("fixed-order-id") is found
    assert await created_service.get_user_order("fixed-order-id", 9) is found
    assert await created_service.get_user_order("fixed-order-id", 10) is None

    session.execute.return_value = _execute_result(scalar=None)
    assert await created_service.get_order("missing") is None
    assert await created_service.get_user_order("missing", 9) is None


@pytest.mark.asyncio
async def test_classify_wechat_cas_miss_order_missing():
    service = PaymentService(_session())
    service.get_order = AsyncMock(return_value=None)
    classify = getattr(service, "_classify_wechat_cas_miss")

    with pytest.raises(SuspiciousWechatNotifyError, match="order not found"):
        await classify(
            out_trade_no="missing-order",
            transaction_id="wx-tx-missing",
        )


@pytest.mark.asyncio
async def test_classify_wechat_cas_miss_duplicate_txid():
    service = PaymentService(_session())
    service.get_order = AsyncMock(
        return_value=_order(status="SUCCESS", wechat_transaction_id="wx-tx-dup")
    )
    classify = getattr(service, "_classify_wechat_cas_miss")

    result = await classify(
        out_trade_no="ord-1",
        transaction_id="wx-tx-dup",
    )

    assert result == "duplicate"


@pytest.mark.asyncio
async def test_classify_wechat_cas_miss_txid_conflict():
    service = PaymentService(_session())
    service.get_order = AsyncMock(
        return_value=_order(status="SUCCESS", wechat_transaction_id="wx-old")
    )
    classify = getattr(service, "_classify_wechat_cas_miss")

    with pytest.raises(SuspiciousWechatNotifyError, match="txid conflict"):
        await classify(
            out_trade_no="ord-1",
            transaction_id="wx-new",
        )


@pytest.mark.asyncio
async def test_classify_wechat_cas_miss_non_pending():
    service = PaymentService(_session())
    service.get_order = AsyncMock(return_value=_order(status="FAILED"))
    classify = getattr(service, "_classify_wechat_cas_miss")

    with pytest.raises(SuspiciousWechatNotifyError, match="non-pending state"):
        await classify(
            out_trade_no="ord-1",
            transaction_id="wx-tx-5",
        )


def test_validate_wechat_notify_identity_rejects_currency():
    validate_identity = getattr(PaymentService, "_validate_wechat_notify_identity")

    with pytest.raises(SuspiciousWechatNotifyError, match="currency mismatch"):
        validate_identity("USD", None, None)


def test_validate_wechat_notify_identity_rejects_appid(monkeypatch):
    validate_identity = getattr(PaymentService, "_validate_wechat_notify_identity")
    monkeypatch.setitem(
        sys.modules,
        "wechat_pay_config",
        SimpleNamespace(wechat_config=SimpleNamespace(app_id="wx-app", mch_id="mch-id")),
    )

    with pytest.raises(SuspiciousWechatNotifyError, match="appid mismatch"):
        validate_identity("CNY", "wrong-app", "mch-id")


def test_validate_wechat_notify_identity_rejects_mchid(monkeypatch):
    validate_identity = getattr(PaymentService, "_validate_wechat_notify_identity")
    monkeypatch.setitem(
        sys.modules,
        "wechat_pay_config",
        SimpleNamespace(wechat_config=SimpleNamespace(app_id="wx-app", mch_id="mch-id")),
    )

    with pytest.raises(SuspiciousWechatNotifyError, match="mchid mismatch"):
        validate_identity("CNY", "wx-app", "wrong-mch")


def test_validate_wechat_notify_identity_accepts_matching_config(monkeypatch):
    validate_identity = getattr(PaymentService, "_validate_wechat_notify_identity")
    monkeypatch.setitem(
        sys.modules,
        "wechat_pay_config",
        SimpleNamespace(wechat_config=SimpleNamespace(app_id="wx-app", mch_id="mch-id")),
    )

    validate_identity("CNY", "wx-app", "mch-id")


def test_validate_wechat_notify_identity_skips_when_config_import_fails(monkeypatch):
    validate_identity = getattr(PaymentService, "_validate_wechat_notify_identity")
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "wechat_pay_config":
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    monkeypatch.delitem(sys.modules, "wechat_pay_config", raising=False)

    validate_identity("CNY", "wx-app", "mch-id")
