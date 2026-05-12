# -*- coding: utf-8 -*-
"""W10 TEST#2 — WeChat 回调并发幂等性验证。

验证 services/payment_service.py 的 CAS UPDATE 防御能保证
同一 transaction_id 的 N 个并发回调只入账 1 次（exactly-once 权益发放）。

CAS 机制（payment_service.apply_wechat_payment_success）：
  UPDATE payment_orders
     SET status='SUCCESS', wechat_transaction_id=:txid
   WHERE order_id=:out_trade_no
     AND status IN ('PENDING','PAID')
     AND wechat_transaction_id IS NULL
  RETURNING ...

PostgreSQL 行级锁保证 N 个并发 UPDATE 串行化，只有第一个 RETURNING 行
（"processed"），其余 RETURNING 空（CAS miss → "duplicate"）。

每个并发 task 必须使用独立 AsyncSession（asyncpg / SQLAlchemy session 非并发安全）。
"""
from __future__ import annotations

import asyncio
import time
import uuid

import pytest
from sqlalchemy import select, update

from database import AsyncSessionLocal
from models.order import PaymentOrder
from models.user import User
import services.payment_service as payment_service
from services.payment_service import (
    DuplicateWechatNotifyError,
    PaymentService,
    SuspiciousWechatNotifyError,
)


CONCURRENT_CALLBACKS = 10
PLAN_DESCRIPTION = "效率版月套餐"
PLAN_DURATION = "1月"
ORDER_AMOUNT_FEN = 9900  # 99.00 CNY
WECHAT_APPID = None  # tests skip identity validation when config has no app_id
WECHAT_MCHID = None
NOTIFY_CURRENCY = "CNY"


async def _seed_pending_order(user_id: int) -> str:
    """Create a fresh PENDING PaymentOrder and return its order_id."""
    out_trade_no = uuid.uuid4().hex
    async with AsyncSessionLocal() as session:
        order = PaymentOrder(
            order_id=out_trade_no,
            user_id=user_id,
            amount=ORDER_AMOUNT_FEN,
            description=PLAN_DESCRIPTION,
            duration=PLAN_DURATION,
            status="PENDING",
            created_at=int(time.time()),
        )
        session.add(order)
        await session.commit()
    return out_trade_no


async def _invoke_wechat_notify(out_trade_no: str, transaction_id: str) -> str:
    """Run one apply_wechat_payment_success call in its own session.

    Returns the literal outcome ("processed" / "duplicate") or the exception
    class name on failure. Each task gets its own session so the CAS race
    is faithfully reproduced (sessions are not concurrency-safe).
    """
    async with AsyncSessionLocal() as session:
        service = PaymentService(session)
        try:
            outcome = await service.apply_wechat_payment_success(
                out_trade_no=out_trade_no,
                transaction_id=transaction_id,
                amount_total=ORDER_AMOUNT_FEN,
                currency=NOTIFY_CURRENCY,
                appid=WECHAT_APPID,
                mchid=WECHAT_MCHID,
                raw_notify={"resource": {"out_trade_no": out_trade_no}},
            )
            await session.commit()
            return outcome
        except DuplicateWechatNotifyError:
            await session.rollback()
            return "duplicate_exc"
        except SuspiciousWechatNotifyError as exc:
            await session.rollback()
            return f"suspicious:{exc}"
        except Exception as exc:  # pragma: no cover - debug aid
            await session.rollback()
            return f"error:{type(exc).__name__}:{exc}"


@pytest.mark.asyncio
async def test_concurrent_callbacks_idempotent_credit(test_user):
    """N 个并发回调只入账 1 次，订阅状态正确，无重复权益。"""
    user_id = test_user["id"]
    out_trade_no = await _seed_pending_order(user_id)
    transaction_id = f"wx_txid_{uuid.uuid4().hex[:16]}"

    # Fire CONCURRENT_CALLBACKS callbacks concurrently with the SAME txid.
    outcomes = await asyncio.gather(
        *(
            _invoke_wechat_notify(out_trade_no, transaction_id)
            for _ in range(CONCURRENT_CALLBACKS)
        )
    )

    processed = [o for o in outcomes if o == "processed"]
    duplicate = [o for o in outcomes if o == "duplicate"]
    other = [o for o in outcomes if o not in ("processed", "duplicate")]

    assert other == [], (
        f"unexpected outcomes leaked through CAS: {other}; full={outcomes}"
    )
    assert len(processed) == 1, (
        f"exactly one callback should win the CAS; got {len(processed)}: "
        f"{outcomes}"
    )
    assert len(duplicate) == CONCURRENT_CALLBACKS - 1, (
        f"the other {CONCURRENT_CALLBACKS - 1} should be classified as "
        f"duplicate; got {len(duplicate)}: {outcomes}"
    )

    # Verify DB end-state: order is SUCCESS with the right txid, exactly once.
    async with AsyncSessionLocal() as session:
        order = (
            await session.execute(
                select(PaymentOrder).where(
                    PaymentOrder.order_id == out_trade_no,
                )
            )
        ).scalar_one()
        assert order.status == "SUCCESS"
        assert order.wechat_transaction_id == transaction_id
        assert order.amount == ORDER_AMOUNT_FEN

        # Verify entitlement granted exactly once: subscription upgraded to
        # the paid plan, remaining_calculations set to unlimited (-1).
        user = await session.get(User, user_id)
        assert user is not None
        assert user.subscription_type == "efficiency", (
            f"expected efficiency plan after credit, got "
            f"{user.subscription_type}"
        )
        assert user.user_type == "efficiency"
        assert user.remaining_calculations == -1, (
            "paid users get unlimited calculations"
        )
        assert user.subscription_start is not None

        # Sanity: only one PaymentOrder row for this txid (uq constraint
        # also enforces this, but we double-check explicitly).
        count_stmt = select(PaymentOrder).where(
            PaymentOrder.wechat_transaction_id == transaction_id,
        )
        rows = (await session.execute(count_stmt)).scalars().all()
        assert len(rows) == 1, (
            f"exactly one order should be linked to this txid; "
            f"got {len(rows)}"
        )


@pytest.mark.asyncio
async def test_sequential_duplicate_after_success_returns_duplicate(test_user):
    """Replay 场景：第一次 processed 后再次回调应返回 duplicate (not processed)."""
    user_id = test_user["id"]
    out_trade_no = await _seed_pending_order(user_id)
    transaction_id = f"wx_txid_{uuid.uuid4().hex[:16]}"

    first = await _invoke_wechat_notify(out_trade_no, transaction_id)
    second = await _invoke_wechat_notify(out_trade_no, transaction_id)
    third = await _invoke_wechat_notify(out_trade_no, transaction_id)

    assert first == "processed", f"first call should win, got {first}"
    assert second == "duplicate", f"second call should be dedup, got {second}"
    assert third == "duplicate", f"third call should be dedup, got {third}"


@pytest.mark.asyncio
async def test_two_simultaneous_callbacks_only_one_grants_subscription(
    test_user,
    monkeypatch,
):
    """Regression guard for SELECT→UPDATE race: two workers, one grant."""
    user_id = test_user["id"]
    out_trade_no = await _seed_pending_order(user_id)
    transaction_id = f"wx_txid_{uuid.uuid4().hex[:16]}"
    grant_calls = 0

    async def _counting_grant(session, *args, **kwargs):
        nonlocal grant_calls
        grant_calls += 1
        user = await session.get(User, user_id)
        assert user is not None
        user.subscription_type = "efficiency"
        user.user_type = "efficiency"
        user.remaining_calculations = -1
        user.subscription_start = int(time.time())
        return None

    monkeypatch.setattr(
        payment_service,
        "apply_paid_subscription",
        _counting_grant,
    )

    outcomes = await asyncio.gather(
        _invoke_wechat_notify(out_trade_no, transaction_id),
        _invoke_wechat_notify(out_trade_no, transaction_id),
    )

    assert sorted(outcomes) == ["duplicate", "processed"]
    assert grant_calls == 1


@pytest.mark.asyncio
async def test_already_paid_order_short_circuits_without_grant(
    test_user,
    monkeypatch,
):
    """WeChat retry after commit must ACK duplicate without re-granting."""
    user_id = test_user["id"]
    out_trade_no = await _seed_pending_order(user_id)
    transaction_id = f"wx_txid_{uuid.uuid4().hex[:16]}"

    async with AsyncSessionLocal() as session:
        await session.execute(
            update(PaymentOrder)
            .where(PaymentOrder.order_id == out_trade_no)
            .values(
                status="SUCCESS",
                wechat_transaction_id=transaction_id,
                updated_at=int(time.time()),
            )
        )
        await session.commit()

    async def _fail_if_called(*args, **kwargs):
        raise AssertionError("duplicate callback must not grant subscription")

    monkeypatch.setattr(
        payment_service,
        "apply_paid_subscription",
        _fail_if_called,
    )

    outcome = await _invoke_wechat_notify(out_trade_no, transaction_id)

    assert outcome == "duplicate"
