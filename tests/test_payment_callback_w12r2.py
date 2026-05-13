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


def _headers(style: str) -> dict[str, str]:
    if style == "lower":
        return {k.lower(): v for k, v in SIGNED_NOTIFY_HEADERS.items()}
    if style == "upper":
        return {k.upper(): v for k, v in SIGNED_NOTIFY_HEADERS.items()}
    return dict(SIGNED_NOTIFY_HEADERS)


def _payment_service_mock() -> Any:
    svc = AsyncMock()
    svc.apply_wechat_payment_success = AsyncMock(return_value="processed")
    return svc


@pytest.fixture
async def audit_client(db_session):
    mock_svc = _payment_service_mock()

    async def _override_db():
        yield db_session

    async def _override_svc():
        return mock_svc

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_payment_service] = _override_svc
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, mock_svc
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_payment_service, None)


async def _audit_rows(db_session):
    result = await db_session.execute(select(WechatNotifyAuditLog))
    return result.scalars().all()


async def _single_audit(db_session):
    rows = await _audit_rows(db_session)
    assert len(rows) == 1
    return rows[0]


def _valid_payload(order_id: str) -> dict[str, Any]:
    return {
        "out_trade_no": order_id,
        "transaction_id": f"wx_{order_id}",
        "amount": {"total": 2990, "currency": "CNY"},
        "appid": "wx_app",
        "mchid": "wx_mch",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("style", ["mixed", "lower", "upper"])
@patch("api.routes.payment._wechat_available", True)
@patch("api.routes.payment.wechat_pay_v3")
async def test_header_case_insensitivity_returns_success_for_valid_signature(
    mock_wechat: MagicMock,
    db_session,
    audit_client,
    style: str,
):
    client, mock_svc = audit_client
    order_id = f"w12r2_header_{style}"
    body = {"out_trade_no": order_id, "transaction_id": f"wx_{order_id}"}
    mock_wechat.process_notify.return_value = _valid_payload(order_id)

    resp = await client.post(
        "/api/payments/notify",
        json=body,
        headers=_headers(style),
    )

    assert resp.status_code == 200
    assert resp.json() == {"code": "SUCCESS", "message": "OK"}
    passed_headers = mock_wechat.process_notify.call_args.args[0]
    assert passed_headers["Wechatpay-Signature"] == "test-signature"
    mock_svc.apply_wechat_payment_success.assert_awaited_once()
    audit = await _single_audit(db_session)
    assert audit.signature_verified is True
    assert audit.response_code == "SUCCESS"
    assert json.loads(audit.raw_body) == body


@pytest.mark.asyncio
@patch("api.routes.payment._wechat_available", True)
@patch("api.routes.payment.wechat_pay_v3")
async def test_bad_signature_returns_fail_and_audits_failure(
    mock_wechat: MagicMock,
    db_session,
    audit_client,
):
    import wechat_pay_v3_api

    client, mock_svc = audit_client
    mock_wechat.process_notify.side_effect = wechat_pay_v3_api.WeChatPayError(
        "signature verification failed"
    )
    body = {"out_trade_no": "w12r2_bad_sig", "transaction_id": "wx_bad"}

    resp = await client.post(
        "/api/payments/notify",
        json=body,
        headers=SIGNED_NOTIFY_HEADERS,
    )

    assert resp.status_code == 401
    assert resp.json()["code"] == "FAIL"
    mock_svc.apply_wechat_payment_success.assert_not_awaited()
    audit = await _single_audit(db_session)
    assert audit.signature_verified is False
    assert audit.response_code == "FAIL"
    assert "signature" in audit.response_message


@pytest.mark.asyncio
@patch("api.routes.payment._wechat_available", False)
async def test_missing_wechat_config_returns_fail_and_audits_failure(
    db_session,
    audit_client,
):
    client, mock_svc = audit_client
    body = {"out_trade_no": "w12r2_no_config", "transaction_id": "wx_no_config"}

    resp = await client.post(
        "/api/payments/notify",
        json=body,
        headers=SIGNED_NOTIFY_HEADERS,
    )

    assert resp.status_code == 500
    assert resp.json()["code"] == "FAIL"
    mock_svc.apply_wechat_payment_success.assert_not_awaited()
    audit = await _single_audit(db_session)
    assert audit.signature_verified is False
    assert audit.response_code == "FAIL"
    assert "不可用" in audit.response_message


@pytest.mark.asyncio
@patch("api.routes.payment._wechat_available", True)
@patch("api.routes.payment.wechat_pay_v3")
async def test_decryption_failure_returns_fail_and_audits_failure(
    mock_wechat: MagicMock,
    db_session,
    audit_client,
):
    import wechat_pay_v3_api

    client, mock_svc = audit_client
    mock_wechat.process_notify.side_effect = wechat_pay_v3_api.WeChatPayError(
        "notify resource decryption failed"
    )
    body = {"out_trade_no": "w12r2_decrypt", "transaction_id": "wx_decrypt"}

    resp = await client.post(
        "/api/payments/notify",
        json=body,
        headers=SIGNED_NOTIFY_HEADERS,
    )

    assert resp.status_code == 500
    assert resp.json()["code"] == "FAIL"
    mock_svc.apply_wechat_payment_success.assert_not_awaited()
    audit = await _single_audit(db_session)
    assert audit.signature_verified is False
    assert audit.response_code == "FAIL"
    assert "decryption" in audit.response_message
