# -*- coding: utf-8 -*-
"""W10 TEST#1: 微信支付回调签名失败必须写入 wechat_notify_audit_logs 表。

资金链路审计回归测试：使用真实 PostgreSQL（worker schema 隔离），覆盖
- 签名失败路径 (`signature_verified=False`) 必须落库
- 签名成功路径 (`signature_verified=True`) 也必须落库
- raw_body 持久化 + out_trade_no 提取
"""
from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from api import dependencies
from api.main import app
from api.routes.payment import get_payment_service
from database import get_db
from models.log import WechatNotifyAuditLog


SIGNED_NOTIFY_HEADERS = {
    "Wechatpay-Timestamp": "1700000000",
    "Wechatpay-Nonce": "test-nonce",
    "Wechatpay-Signature": "test-signature",
    "Wechatpay-Serial": "test-serial",
}


def _make_payment_service_mock() -> Any:
    svc = AsyncMock()
    svc.apply_wechat_payment_success = AsyncMock(return_value="processed")
    return svc


@pytest.fixture
async def audit_client(db_session):
    """HTTP client whose `get_db` dependency returns the SAME db_session
    used to inspect the audit table after the request — guarantees
    the test sees the row even before/without commit (read in same session).
    """
    mock_svc = _make_payment_service_mock()

    async def _override_db():
        yield db_session

    async def _override_svc():
        return mock_svc

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_payment_service] = _override_svc
    app.dependency_overrides[dependencies.get_current_user_id] = lambda: 1

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, mock_svc

    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_payment_service, None)
    app.dependency_overrides.pop(dependencies.get_current_user_id, None)


async def _fetch_audit_rows(db_session, out_trade_no: str):
    stmt = select(WechatNotifyAuditLog).where(
        WechatNotifyAuditLog.out_trade_no == out_trade_no
    )
    result = await db_session.execute(stmt)
    return result.scalars().all()


@pytest.mark.asyncio
@patch("api.routes.payment._wechat_available", True)
@patch("api.routes.payment.wechat_pay_v3")
async def test_invalid_signature_writes_audit_log_with_verified_false(
    mock_wechat: MagicMock,
    db_session,
    audit_client,
):
    """签名失败：process_notify 返回 (None, False)，必须写一行 verified=False
    审计日志，response_code=SUCCESS（阻止微信重试风暴），raw_body 持久化，
    out_trade_no/transaction_id 从 raw body 解析提取。
    """
    client, mock_svc = audit_client
    mock_wechat.process_notify.return_value = (None, False)
    body = {
        "event_type": "TRANSACTION.SUCCESS",
        "out_trade_no": "audit_bad_sig_ord_001",
        "transaction_id": "wx_tx_bad_sig_001",
        "resource": {"ciphertext": "tampered"},
    }

    resp = await client.post(
        "/api/payments/notify",
        json=body,
        headers=SIGNED_NOTIFY_HEADERS,
    )

    # ACK SUCCESS 阻止微信重试
    assert resp.status_code == 200
    assert resp.json() == {"code": "SUCCESS", "message": "OK"}

    # 业务侧不能扣款
    mock_svc.apply_wechat_payment_success.assert_not_awaited()

    # 审计行必须存在
    rows = await _fetch_audit_rows(db_session, "audit_bad_sig_ord_001")
    assert len(rows) == 1, "签名失败必须写入恰好一行审计日志"
    audit = rows[0]

    assert audit.signature_verified is False, "签名失败时 verified 必须为 False"
    assert audit.out_trade_no == "audit_bad_sig_ord_001"
    assert audit.transaction_id == "wx_tx_bad_sig_001"
    assert audit.response_code == "SUCCESS"
    assert audit.response_message == "OK"

    # raw_body 必须完整持久化（验签失败也保留原始报文供取证）
    assert audit.raw_body, "raw_body 不能为空"
    persisted = json.loads(audit.raw_body)
    assert persisted == body, "raw_body 必须 1:1 持久化原始 JSON"

    assert audit.created_at is not None
    assert audit.id is not None


@pytest.mark.asyncio
@patch("api.routes.payment._wechat_available", True)
@patch("api.routes.payment.wechat_pay_v3")
async def test_valid_signature_writes_audit_log_with_verified_true(
    mock_wechat: MagicMock,
    db_session,
    audit_client,
):
    """签名成功：process_notify 返回 (payload, True)，必须写一行 verified=True
    审计日志，response_code=SUCCESS，raw_body 持久化，标识符提取正确。
    """
    client, mock_svc = audit_client
    payload = {
        "out_trade_no": "audit_good_sig_ord_001",
        "transaction_id": "wx_tx_good_sig_001",
        "amount": {"total": 2990, "currency": "CNY"},
        "appid": "wx_app",
        "mchid": "wx_mch",
    }
    mock_wechat.process_notify.return_value = (payload, True)
    body = {
        "event_type": "TRANSACTION.SUCCESS",
        "resource": {"ciphertext": "encrypted_payload"},
        "out_trade_no": "audit_good_sig_ord_001",
        "transaction_id": "wx_tx_good_sig_001",
    }

    resp = await client.post(
        "/api/payments/notify",
        json=body,
        headers=SIGNED_NOTIFY_HEADERS,
    )

    assert resp.status_code == 200
    assert resp.json() == {"code": "SUCCESS", "message": "OK"}

    # 验签成功：业务入账被调用
    mock_svc.apply_wechat_payment_success.assert_awaited_once()

    # 审计行必须存在
    rows = await _fetch_audit_rows(db_session, "audit_good_sig_ord_001")
    assert len(rows) == 1, "签名成功必须写入恰好一行审计日志"
    audit = rows[0]

    assert audit.signature_verified is True, "签名成功时 verified 必须为 True"
    assert audit.out_trade_no == "audit_good_sig_ord_001"
    assert audit.transaction_id == "wx_tx_good_sig_001"
    assert audit.response_code == "SUCCESS"
    assert audit.response_message == "OK"

    # raw_body 1:1 持久化
    assert audit.raw_body
    persisted = json.loads(audit.raw_body)
    assert persisted == body

    assert audit.created_at is not None
    assert audit.id is not None


@pytest.mark.asyncio
@patch("api.routes.payment._wechat_available", True)
@patch("api.routes.payment.wechat_pay_v3")
async def test_signature_verification_exception_audits_as_unverified(
    mock_wechat: MagicMock,
    db_session,
    audit_client,
):
    """process_notify 抛异常（解析失败/签名 lib 内部错）也要写审计日志，
    且 verified=False（防止异常路径绕过审计）。
    """
    client, mock_svc = audit_client
    mock_wechat.process_notify.side_effect = RuntimeError("signature lib crashed")
    body = {
        "event_type": "TRANSACTION.SUCCESS",
        "out_trade_no": "audit_exc_ord_001",
        "transaction_id": "wx_tx_exc_001",
    }

    resp = await client.post(
        "/api/payments/notify",
        json=body,
        headers=SIGNED_NOTIFY_HEADERS,
    )

    # 异常被吞，仍 ACK SUCCESS 防止微信重试风暴
    assert resp.status_code == 200
    mock_svc.apply_wechat_payment_success.assert_not_awaited()

    rows = await _fetch_audit_rows(db_session, "audit_exc_ord_001")
    assert len(rows) == 1, "解析异常路径也必须写入审计日志"
    audit = rows[0]
    assert audit.signature_verified is False
    assert audit.out_trade_no == "audit_exc_ord_001"
    assert audit.transaction_id == "wx_tx_exc_001"
    assert json.loads(audit.raw_body) == body
