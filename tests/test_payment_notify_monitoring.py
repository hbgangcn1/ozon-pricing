# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

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
    mock_svc = _make_payment_service_mock()

    async def _override_db():
        yield db_session

    async def _override_svc():
        return mock_svc

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_payment_service] = _override_svc

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, mock_svc

    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_payment_service, None)


async def _audit_rows(db_session):
    result = await db_session.execute(select(WechatNotifyAuditLog))
    return result.scalars().all()


async def _single_audit_row(db_session):
    rows = await _audit_rows(db_session)
    assert len(rows) == 1
    return rows[0]


def _assert_protocol_success_ack(resp):
    # [SEC-W12R2-02] Signature/parse failures must FAIL so WeChat retries.
    assert resp.status_code in (401, 500)
    assert resp.json()["code"] == "FAIL"


def _assert_signature_failure_log(caplog, out_trade_no, transaction_id):
    records = [
        rec for rec in caplog.records
        if getattr(rec, "event", None) == "payment_signature_failure"
    ]
    assert records
    record = records[-1]
    assert record.ip == "203.0.113.9"
    assert record.out_trade_no == out_trade_no
    assert record.transaction_id == transaction_id


@pytest.mark.asyncio
@patch("api.routes.payment._wechat_available", True)
@patch("api.routes.payment.wechat_pay_v3")
async def test_bad_signature_returns_fail_and_audits_unverified(
    mock_wechat: MagicMock,
    db_session,
    audit_client,
    caplog,
):
    import wechat_pay_v3_api

    client, mock_svc = audit_client
    mock_wechat.process_notify.side_effect = wechat_pay_v3_api.WeChatPayError(
        "signature verification failed"
    )
    body = {
        "event_type": "TRANSACTION.SUCCESS",
        "out_trade_no": "monitor_bad_sig_ord",
        "transaction_id": "wx_monitor_bad_sig",
    }

    resp = await client.post(
        "/api/payments/notify",
        json=body,
        headers={**SIGNED_NOTIFY_HEADERS, "X-Forwarded-For": "203.0.113.9"},
    )

    _assert_protocol_success_ack(resp)
    mock_svc.apply_wechat_payment_success.assert_not_awaited()
    audit = await _single_audit_row(db_session)
    assert audit.signature_verified is False
    assert audit.out_trade_no == "monitor_bad_sig_ord"
    assert audit.transaction_id == "wx_monitor_bad_sig"
    assert audit.response_code == "FAIL"
    assert "signature" in audit.response_message
    assert json.loads(audit.raw_body) == body
    _assert_signature_failure_log(
        caplog,
        "monitor_bad_sig_ord",
        "wx_monitor_bad_sig",
    )


@pytest.mark.asyncio
@patch("api.routes.payment._wechat_available", True)
@patch("api.routes.payment.wechat_pay_v3")
async def test_malformed_body_returns_fail_and_audits_unverified(
    mock_wechat: MagicMock,
    db_session,
    audit_client,
    caplog,
):
    client, mock_svc = audit_client
    mock_wechat.process_notify.side_effect = ValueError("malformed notify body")

    resp = await client.post(
        "/api/payments/notify",
        content=b"{not-json",
        headers={**SIGNED_NOTIFY_HEADERS, "X-Forwarded-For": "203.0.113.9"},
    )

    _assert_protocol_success_ack(resp)
    mock_svc.apply_wechat_payment_success.assert_not_awaited()
    audit = await _single_audit_row(db_session)
    assert audit.signature_verified is False
    assert audit.out_trade_no is None
    assert audit.transaction_id is None
    assert audit.raw_body == "{not-json"
    assert audit.response_code == "FAIL"
    assert audit.response_message == "malformed notify body"
    _assert_signature_failure_log(caplog, None, None)


@pytest.mark.asyncio
@patch("api.routes.payment._wechat_available", True)
@patch("api.routes.payment.wechat_pay_v3")
async def test_generic_parse_exception_returns_fail_and_audits_unverified(
    mock_wechat: MagicMock,
    db_session,
    audit_client,
    caplog,
):
    client, mock_svc = audit_client
    mock_wechat.process_notify.side_effect = RuntimeError("signature lib crashed")
    body = {
        "out_trade_no": "monitor_generic_exc_ord",
        "transaction_id": "wx_monitor_generic_exc",
    }

    resp = await client.post(
        "/api/payments/notify",
        json=body,
        headers={**SIGNED_NOTIFY_HEADERS, "X-Forwarded-For": "203.0.113.9"},
    )

    _assert_protocol_success_ack(resp)
    mock_svc.apply_wechat_payment_success.assert_not_awaited()
    audit = await _single_audit_row(db_session)
    assert audit.signature_verified is False
    assert audit.out_trade_no == "monitor_generic_exc_ord"
    assert audit.transaction_id == "wx_monitor_generic_exc"
    assert audit.response_code == "FAIL"
    assert audit.response_message == "signature lib crashed"
    _assert_signature_failure_log(
        caplog,
        "monitor_generic_exc_ord",
        "wx_monitor_generic_exc",
    )


@pytest.mark.asyncio
@patch("api.routes.payment._wechat_available", True)
@patch("api.routes.payment.wechat_pay_v3")
async def test_good_signature_returns_success_and_audits_verified(
    mock_wechat: MagicMock,
    db_session,
    audit_client,
):
    client, mock_svc = audit_client
    payload = {
        "out_trade_no": "monitor_good_sig_ord",
        "transaction_id": "wx_monitor_good_sig",
        "amount": {"total": 2990, "currency": "CNY"},
        "appid": "wx_app",
        "mchid": "wx_mch",
    }
    body = {
        "event_type": "TRANSACTION.SUCCESS",
        "out_trade_no": "monitor_good_sig_ord",
        "transaction_id": "wx_monitor_good_sig",
    }
    mock_wechat.process_notify.return_value = payload

    resp = await client.post(
        "/api/payments/notify",
        json=body,
        headers=SIGNED_NOTIFY_HEADERS,
    )

    assert resp.status_code == 200
    assert resp.json() == {"code": "SUCCESS", "message": "OK"}
    mock_svc.apply_wechat_payment_success.assert_awaited_once()
    audit = await _single_audit_row(db_session)
    assert audit.signature_verified is True
    assert audit.out_trade_no == "monitor_good_sig_ord"
    assert audit.transaction_id == "wx_monitor_good_sig"
    assert audit.response_code == "SUCCESS"
    assert audit.response_message == "OK"
    assert json.loads(audit.raw_body) == body
