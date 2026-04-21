# -*- coding: utf-8 -*-
"""wechat_pay_v3_api.py 单元测试。"""

import base64
import json
import time
from unittest.mock import MagicMock, mock_open, patch

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from wechat_pay_v3_api import WeChatPayV3API


def _make_config():
    config = MagicMock()
    config.app_id = "test_app_id"
    config.mch_id = "test_mch_id"
    config.cert_serial_no = "test_serial"
    config.private_key_path = "test_key.pem"
    config.public_key_path = "test_pub.pem"
    config.api_v3_key = "a" * 32
    config.notify_url = "https://test.com/notify"
    config.jsapi_pay_url = "https://api.test.com/jsapi"
    config.native_pay_url = "https://api.test.com/native"
    config.order_query_url = "https://api.test.com/query"
    config.platform_public_key_id = "platform_serial"
    config.platform_public_key = MagicMock(spec=rsa.RSAPublicKey)
    return config


def _wechatpay_headers(config, **overrides):
    headers = {
        "Wechatpay-Timestamp": str(int(time.time())),
        "Wechatpay-Nonce": "test_nonce",
        "Wechatpay-Signature": base64.b64encode(b"signature").decode("utf-8"),
        "Wechatpay-Serial": config.platform_public_key_id,
    }
    headers.update(overrides)
    return headers


def _response(payload=None, status_code=200, headers=None):
    body = json.dumps(payload or {}).encode("utf-8")
    response = MagicMock()
    response.status_code = status_code
    response.content = body
    response.headers = headers or {}
    return response


class TestWeChatPayV3API:
    """测试微信支付 v3 API 基础能力。"""

    @pytest.fixture
    def mock_config(self):
        return _make_config()

    @pytest.fixture
    def api(self, mock_config):
        return WeChatPayV3API(config=mock_config)

    def test_init_with_config(self, mock_config):
        api = WeChatPayV3API(config=mock_config)

        assert api.config == mock_config
        assert api.config.cert_serial_no == "test_serial"

    def test_init_without_config(self):
        mock_config = MagicMock()
        mock_config.app_id = "default"

        with patch("wechat_pay_v3_api.wechat_config", mock_config):
            api = WeChatPayV3API()

        assert api.config == mock_config

    def test_get_timestamp(self, api):
        ts = api._get_timestamp()

        assert ts.isdigit()
        assert abs(int(ts) - time.time()) < 2

    def test_get_nonce_str(self, api):
        nonce = api._get_nonce_str()

        assert len(nonce) > 20

    def test_load_private_key_not_loaded(self, api, mock_config):
        mock_config.private_key_path = None

        assert api._load_private_key() is None

    def test_load_private_key_file_not_exists(self, api, mock_config):
        mock_config.private_key_path = "nonexistent.pem"

        with patch("os.path.exists", return_value=False):
            assert api._load_private_key() is None

    def test_load_private_key_invalid_format(self, api, mock_config):
        mock_config.private_key_path = "test.pem"

        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=b"invalid key data")):
                with patch(
                    "wechat_pay_v3_api.serialization.load_pem_private_key",
                    side_effect=ValueError("Invalid key"),
                ):
                    assert api._load_private_key() is None

    def test_build_signature_no_private_key(self, api, mock_config):
        mock_config.private_key_path = None

        with pytest.raises(Exception, match="商户私钥未配置"):
            api._build_signature("POST", "/test", "123", "nonce", "{}")

    def test_build_auth_header(self, api):
        mock_private_key = MagicMock()
        mock_private_key.sign.return_value = b"signature_bytes"

        with patch.object(api, "_load_private_key", return_value=mock_private_key):
            with patch("wechat_pay_v3_api.base64.b64encode", return_value=b"b64_sig"):
                header = api._build_auth_header("POST", "/test", "{}")

        assert "Authorization" in header
        assert header["Content-Type"] == "application/json"
        assert "WECHATPAY2-SHA256-RSA2048" in header["Authorization"]

    def test_verify_notify_signature(self, api, mock_config):
        result = api.verify_notify_signature_with_public_key(
            str(int(time.time())),
            "test_nonce",
            '{"test": "data"}',
            base64.b64encode(b"valid_signature").decode("utf-8"),
            serial=mock_config.platform_public_key_id,
        )

        assert result is True
        mock_config.platform_public_key.verify.assert_called_once()

    def test_verify_notify_signature_invalid(self, api, mock_config):
        mock_config.platform_public_key.verify.side_effect = ValueError("bad sig")

        result = api.verify_notify_signature_with_public_key(
            str(int(time.time())),
            "test_nonce",
            "body",
            base64.b64encode(b"invalid_signature").decode("utf-8"),
            serial=mock_config.platform_public_key_id,
        )

        assert result is False

    def test_decrypt_resource_missing_fields(self, api):
        assert api._decrypt_resource({}) == {}
        assert (
            api._decrypt_resource(
                {"ciphertext": "", "nonce": "n", "associated_data": "a"}
            )
            == {}
        )

    def test_decrypt_resource_invalid_key_length(self, api, mock_config):
        mock_config.api_v3_key = "short"

        result = api._decrypt_resource(
            {
                "ciphertext": "abc",
                "nonce": "nonce",
                "associated_data": "aad",
            }
        )

        assert result == {}

    def test_decrypt_resource_invalid_base64(self, api, mock_config):
        mock_config.api_v3_key = "a" * 32

        result = api._decrypt_resource(
            {
                "ciphertext": "not_valid_base64!!!",
                "nonce": "nonce",
                "associated_data": "aad",
            }
        )

        assert result == {}

    def test_process_notify_missing_timestamp(self, api, mock_config):
        result = api.process_notify(
            {
                "Wechatpay-Nonce": "n",
                "Wechatpay-Signature": "s",
                "Wechatpay-Serial": mock_config.platform_public_key_id,
            },
            b"{}",
        )

        assert result["success"] is False
        assert "Wechatpay-Timestamp" in result["message"]

    def test_process_notify_expired_timestamp(self, api, mock_config):
        result = api.process_notify(
            _wechatpay_headers(
                mock_config,
                **{"Wechatpay-Timestamp": str(int(time.time()) - 400)}
            ),
            b"{}",
        )

        assert result["success"] is False
        assert "过期" in result["message"]

    def test_process_notify_invalid_timestamp_format(self, api, mock_config):
        result = api.process_notify(
            _wechatpay_headers(mock_config, **{"Wechatpay-Timestamp": "not_a_number"}),
            b"{}",
        )

        assert result["success"] is False
        assert "格式非法" in result["message"]

    def test_process_notify_signature_verification_fails(self, api, mock_config):
        mock_config.platform_public_key.verify.side_effect = ValueError("bad sig")

        result = api.process_notify(_wechatpay_headers(mock_config), b"{}")

        assert result["success"] is False
        assert "平台签名验证失败" in result["message"]

    def test_process_notify_non_transaction_success(self, api, mock_config):
        body = json.dumps({"event_type": "OTHER_EVENT"}).encode("utf-8")

        result = api.process_notify(_wechatpay_headers(mock_config), body)

        assert result["success"] is False
        assert "非支付成功通知" in result["message"]

    def test_process_notify_success(self, api, mock_config):
        body = json.dumps(
            {"event_type": "TRANSACTION.SUCCESS", "resource": {}}
        ).encode("utf-8")

        with patch.object(
            api,
            "_decrypt_resource",
            return_value={
                "out_trade_no": "order123",
                "transaction_id": "tx123",
                "trade_state": "SUCCESS",
            },
        ):
            result = api.process_notify(_wechatpay_headers(mock_config), body)

        assert result["success"] is True
        assert result["out_trade_no"] == "order123"

    def test_verify_notify_signature_with_public_key_no_config(
        self, api, mock_config
    ):
        mock_config.platform_public_key_id = ""

        result = api.verify_notify_signature_with_public_key(
            str(int(time.time())),
            "n",
            "b",
            base64.b64encode(b"sig").decode("utf-8"),
        )

        assert result is False

    def test_verify_notify_signature_with_public_key_file_not_exists(
        self, api, mock_config
    ):
        mock_config.platform_public_key = None

        result = api.verify_notify_signature_with_public_key(
            str(int(time.time())),
            "n",
            "b",
            base64.b64encode(b"sig").decode("utf-8"),
            serial=mock_config.platform_public_key_id,
        )

        assert result is False

    def test_verify_notify_signature_with_public_key_invalid_key(
        self, api, mock_config
    ):
        mock_config.platform_public_key.verify.side_effect = ValueError("invalid key")

        result = api.verify_notify_signature_with_public_key(
            str(int(time.time())),
            "n",
            "b",
            base64.b64encode(b"sig").decode("utf-8"),
            serial=mock_config.platform_public_key_id,
        )

        assert result is False


class TestCreateJsapiOrder:
    @pytest.fixture
    def mock_config(self):
        return _make_config()

    def test_create_jsapi_order_success(self, mock_config):
        api = WeChatPayV3API(config=mock_config)
        response = _response(
            {"prepay_id": "prepay123"},
            headers=_wechatpay_headers(mock_config),
        )

        with patch.object(api, "_build_auth_header", return_value={"Authorization": "test"}):
            with patch("wechat_pay_v3_api.requests.post", return_value=response):
                result = api.create_jsapi_order(
                    "order123",
                    100,
                    "test",
                    "openid123",
                )

        assert result["success"] is True
        assert result["prepay_id"] == "prepay123"

    def test_create_jsapi_order_http_error(self, mock_config):
        api = WeChatPayV3API(config=mock_config)
        response = _response(
            {"message": "error"},
            status_code=400,
            headers=_wechatpay_headers(mock_config),
        )

        with patch.object(api, "_build_auth_header", return_value={"Authorization": "test"}):
            with patch("wechat_pay_v3_api.requests.post", return_value=response):
                result = api.create_jsapi_order(
                    "order123",
                    100,
                    "test",
                    "openid123",
                )

        assert result["success"] is False
        assert result["message"] == "error"

    def test_create_jsapi_order_network_error(self, mock_config):
        api = WeChatPayV3API(config=mock_config)

        with patch.object(api, "_build_auth_header", return_value={"Authorization": "test"}):
            with patch(
                "wechat_pay_v3_api.requests.post",
                side_effect=Exception("Network error"),
            ):
                result = api.create_jsapi_order(
                    "order123",
                    100,
                    "test",
                    "openid123",
                )

        assert result["success"] is False
        assert "网络请求失败" in result["message"]


class TestCreateNativeOrder:
    @pytest.fixture
    def mock_config(self):
        return _make_config()

    def test_create_native_order_success(self, mock_config):
        api = WeChatPayV3API(config=mock_config)
        response = _response(
            {"code_url": "weixin://pay"},
            headers=_wechatpay_headers(mock_config),
        )

        with patch.object(api, "_build_auth_header", return_value={"Authorization": "test"}):
            with patch("wechat_pay_v3_api.requests.post", return_value=response):
                result = api.create_native_order("order123", 100, "test")

        assert result["success"] is True
        assert result["code_url"] == "weixin://pay"


class TestQueryOrder:
    @pytest.fixture
    def mock_config(self):
        return _make_config()

    def test_query_order_success(self, mock_config):
        api = WeChatPayV3API(config=mock_config)
        response = _response(
            {"trade_state": "SUCCESS", "trade_state_desc": "支付成功"},
            headers=_wechatpay_headers(mock_config),
        )

        with patch.object(api, "_build_auth_header", return_value={"Authorization": "test"}):
            with patch("wechat_pay_v3_api.requests.get", return_value=response):
                result = api.query_order("order123")

        assert result["success"] is True
        assert result["trade_state"] == "SUCCESS"

    def test_query_order_not_found(self, mock_config):
        api = WeChatPayV3API(config=mock_config)
        response = _response(
            {"message": "not found"},
            status_code=404,
            headers=_wechatpay_headers(mock_config),
        )

        with patch.object(api, "_build_auth_header", return_value={"Authorization": "test"}):
            with patch("wechat_pay_v3_api.requests.get", return_value=response):
                result = api.query_order("order123")

        assert result["success"] is False
        assert result["message"] == "not found"
