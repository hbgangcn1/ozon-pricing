# -*- coding: utf-8 -*-

import base64
import json
import time
from unittest.mock import MagicMock

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from wechat_pay_v3_api import (
    SignatureVerificationError,
    WeChatPayV3API,
    WechatResponseSignatureError,
)


class _TestAPI(WeChatPayV3API):
    def parse_verified_response(self, response):
        return self._parse_verified_response(response, WechatResponseSignatureError)

    def set_auth_header_builder(self):
        self._build_auth_header = MagicMock(return_value={"Authorization": "test"})


def _make_api():
    config = MagicMock()
    config.app_id = "wx-app"
    config.mch_id = "mch-id"
    config.cert_serial_no = "merchant-serial"
    config.private_key_path = None
    config.public_key_path = None
    config.api_v3_key = "a" * 32
    config.notify_url = "https://test.example/notify"
    config.jsapi_pay_url = "https://api.test.com/jsapi"
    config.native_pay_url = "https://api.test.com/native"
    config.order_query_url = "https://api.test.com/query"
    config.platform_public_key_id = "PUB_KEY_ID_001"
    public_key = MagicMock(spec=rsa.RSAPublicKey)
    config.platform_public_key = public_key
    return _TestAPI(config=config), public_key


def _signed_headers(**overrides):
    headers = {
        "Wechatpay-Timestamp": str(int(time.time())),
        "Wechatpay-Nonce": "nonce-123",
        "Wechatpay-Signature": base64.b64encode(b"sig").decode("utf-8"),
        "Wechatpay-Serial": "PUB_KEY_ID_001",
    }
    headers.update(overrides)
    return headers


def _response(status_code=200, body=None, headers=None):
    payload = body if body is not None else {}
    raw_body = json.dumps(payload).encode("utf-8")
    response = MagicMock()
    response.status_code = status_code
    response.content = raw_body
    response.headers = headers or _signed_headers()
    return response


class TestPlatformSignatureVerification:
    def test_missing_wechatpay_serial(self):
        api, _ = _make_api()
        headers = _signed_headers()
        headers.pop("Wechatpay-Serial")

        with pytest.raises(SignatureVerificationError, match="Wechatpay-Serial"):
            api.verify_platform_signature(headers, b"{}")

    def test_serial_mismatch(self):
        api, _ = _make_api()

        with pytest.raises(SignatureVerificationError, match="序列号不匹配"):
            api.verify_platform_signature(
                _signed_headers(**{"Wechatpay-Serial": "WRONG_SERIAL"}),
                b"{}",
            )

    def test_rejects_duplicated_header_value(self):
        api, _ = _make_api()

        with pytest.raises(SignatureVerificationError, match="格式非法"):
            api.verify_platform_signature(
                _signed_headers(**{"Wechatpay-Serial": "PUB_KEY_ID_001,PUB_KEY_ID_002"}),
                b"{}",
            )

    def test_rejects_expired_timestamp(self):
        api, _ = _make_api()

        with pytest.raises(SignatureVerificationError, match="已过期"):
            api.verify_platform_signature(
                _signed_headers(
                    **{"Wechatpay-Timestamp": str(int(time.time()) - 301)}
                ),
                b"{}",
            )


class TestWechatResponseVerification:
    def test_outbound_response_missing_header(self):
        api, _ = _make_api()
        response = _response(headers={"Wechatpay-Timestamp": str(int(time.time()))})

        with pytest.raises(WechatResponseSignatureError, match="缺少签名头"):
            api.parse_verified_response(response)

    def test_outbound_response_signature_failure(self):
        api, public_key = _make_api()
        public_key.verify.side_effect = ValueError("bad sig")
        response = _response(body={"code_url": "weixin://unsafe"})

        with pytest.raises(WechatResponseSignatureError, match="平台签名验证失败"):
            api.parse_verified_response(response)

    def test_outbound_response_signature_success_and_parse(self):
        api, public_key = _make_api()
        response = _response(body={"code_url": "weixin://ok", "trade_state": "SUCCESS"})

        result = api.parse_verified_response(response)

        assert result["code_url"] == "weixin://ok"
        public_key.verify.assert_called_once()

    def test_create_native_order_raises_on_signature_failure(self):
        api, public_key = _make_api()
        api.set_auth_header_builder()
        public_key.verify.side_effect = ValueError("bad sig")

        with pytest.raises(WechatResponseSignatureError):
            with pytest.MonkeyPatch.context() as mp:
                mp.setattr(
                    "wechat_pay_v3_api.requests.post",
                    MagicMock(return_value=_response(body={"code_url": "weixin://unsafe"})),
                )
                api.create_native_order("order-1", 100, "desc")

    def test_query_order_raises_on_signature_failure(self):
        api, public_key = _make_api()
        api.set_auth_header_builder()
        public_key.verify.side_effect = ValueError("bad sig")

        with pytest.raises(WechatResponseSignatureError):
            with pytest.MonkeyPatch.context() as mp:
                mp.setattr(
                    "wechat_pay_v3_api.requests.get",
                    MagicMock(return_value=_response(body={"trade_state": "SUCCESS"})),
                )
                api.query_order("order-1")
