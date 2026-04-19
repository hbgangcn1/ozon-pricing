# -*- coding: utf-8 -*-
"""
wechat_pay_v3_api.py 单元测试
"""
import pytest
import json
import time
from unittest.mock import MagicMock, patch, mock_open


class TestWeChatPayV3API:
    """测试微信支付v3 API类"""

    @pytest.fixture
    def mock_config(self):
        config = MagicMock()
        config.app_id = "test_app_id"
        config.mch_id = "test_mch_id"
        config.cert_serial_no = "test_serial"
        config.private_key_path = "test_key.pem"
        config.public_key_path = "test_pub.pem"
        config.api_v3_key = "a" * 32
        config.notify_url = "https://test.com/notify"
        config.jsapi_pay_url = "https://api.test.com"
        config.native_pay_url = "https://api.test.com"
        config.order_query_url = "https://api.test.com"
        return config

    @pytest.fixture
    def api(self, mock_config):
        with patch("wechat_pay_v3_api.wechat_config", mock_config):
            from wechat_pay_v3_api import WeChatPayV3API
            return WeChatPayV3API(config=mock_config)

    def test_init_with_config(self, mock_config):
        with patch("wechat_pay_v3_api.wechat_config", mock_config):
            from wechat_pay_v3_api import WeChatPayV3API
            api = WeChatPayV3API(config=mock_config)
            assert api.config == mock_config
            assert api._cert_serial_no == "test_serial"

    def test_init_without_config(self):
        mock_config = MagicMock()
        mock_config.app_id = "default"
        with patch("wechat_pay_v3_api.wechat_config", mock_config):
            from wechat_pay_v3_api import WeChatPayV3API
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
        result = api._load_private_key()
        assert result is None

    def test_load_private_key_file_not_exists(self, api, mock_config):
        mock_config.private_key_path = "nonexistent.pem"
        with patch("os.path.exists", return_value=False):
            result = api._load_private_key()
            assert result is None

    def test_load_private_key_invalid_format(self, api, mock_config):
        mock_config.private_key_path = "test.pem"
        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=b"invalid key data")):
                with patch("wechat_pay_v3_api.serialization.load_pem_private_key", side_effect=ValueError("Invalid key")):
                    result = api._load_private_key()
                    assert result is None

    def test_build_signature_no_private_key(self, api, mock_config):
        mock_config.private_key_path = None
        with pytest.raises(Exception, match="商户私钥未配置"):
            api._build_signature("POST", "/test", "123", "nonce", "{}")

    def test_build_auth_header(self, api):
        with patch.object(api, "_load_private_key") as mock_load:
            mock_key = MagicMock()
            mock_key.sign.return_value = b"signature_bytes"
            mock_load.return_value = mock_key

            with patch("wechat_pay_v3_api.base64.b64encode", return_value=b"b64_sig"):
                header = api._build_auth_header("POST", "/test", "{}")
                assert "Authorization" in header
                assert header["Content-Type"] == "application/json"
                assert "WECHATPAY2-SHA256-RSA2048" in header["Authorization"]

    def test_verify_notify_signature(self, api, mock_config):
        mock_config.api_v3_key = "a" * 32
        timestamp = str(int(time.time()))
        nonce = "test_nonce"
        body = '{"test": "data"}'

        sign_str = f"{timestamp}\n{nonce}\n{body}\n"
        import hashlib
        import hmac
        import base64
        expected = base64.b64encode(
            hmac.new(
                mock_config.api_v3_key.encode("utf-8"),
                sign_str.encode("utf-8"),
                hashlib.sha256,
            ).digest()
        ).decode("utf-8")

        result = api.verify_notify_signature(timestamp, nonce, body, expected)
        assert result is True

    def test_verify_notify_signature_invalid(self, api, mock_config):
        mock_config.api_v3_key = "a" * 32
        result = api.verify_notify_signature("123", "nonce", "body", "invalid_sig")
        assert result is False

    def test_decrypt_resource_missing_fields(self, api):
        result = api._decrypt_resource({})
        assert result == {}

        result = api._decrypt_resource({"ciphertext": "", "nonce": "n", "associated_data": "a"})
        assert result == {}

    def test_decrypt_resource_invalid_key_length(self, api, mock_config):
        mock_config.api_v3_key = "short"
        result = api._decrypt_resource({
            "ciphertext": "abc",
            "nonce": "nonce",
            "associated_data": "aad"
        })
        assert result == {}

    def test_decrypt_resource_invalid_base64(self, api, mock_config):
        mock_config.api_v3_key = "a" * 32
        result = api._decrypt_resource({
            "ciphertext": "not_valid_base64!!!",
            "nonce": "nonce",
            "associated_data": "aad"
        })
        assert result == {}

    def test_process_notify_missing_timestamp(self, api):
        result = api.process_notify({
            "headers": {"Wechatpay-Nonce": "n", "Wechatpay-Signature": "s"},
            "body": "{}"
        })
        assert result["success"] is False
        assert "时间戳" in result["message"]

    def test_process_notify_expired_timestamp(self, api):
        old_timestamp = str(int(time.time()) - 400)
        result = api.process_notify({
            "headers": {
                "Wechatpay-Timestamp": old_timestamp,
                "Wechatpay-Nonce": "n",
                "Wechatpay-Signature": "s"
            },
            "body": "{}"
        })
        assert result["success"] is False
        assert "过期" in result["message"]

    def test_process_notify_invalid_timestamp_format(self, api):
        result = api.process_notify({
            "headers": {
                "Wechatpay-Timestamp": "not_a_number",
                "Wechatpay-Nonce": "n",
                "Wechatpay-Signature": "s"
            },
            "body": "{}"
        })
        assert result["success"] is False
        assert "格式错误" in result["message"]

    def test_process_notify_signature_verification_fails(self, api, mock_config):
        mock_config.public_key_path = "nonexistent.pem"
        with patch.object(api, "verify_notify_signature_with_public_key", return_value=False):
            result = api.process_notify({
                "headers": {
                    "Wechatpay-Timestamp": str(int(time.time())),
                    "Wechatpay-Nonce": "n",
                    "Wechatpay-Signature": "s"
                },
                "body": "{}"
            })
            assert result["success"] is False
            assert "签名验证失败" in result["message"]

    def test_process_notify_non_transaction_success(self, api):
        with patch.object(api, "verify_notify_signature_with_public_key", return_value=True):
            result = api.process_notify({
                "headers": {
                    "Wechatpay-Timestamp": str(int(time.time())),
                    "Wechatpay-Nonce": "n",
                    "Wechatpay-Signature": "s"
                },
                "body": json.dumps({"event_type": "OTHER_EVENT"})
            })
            assert result["success"] is False
            assert "非支付成功通知" in result["message"]

    def test_process_notify_success(self, api, mock_config):
        mock_config.public_key_path = None
        with patch.object(api, "verify_notify_signature_with_public_key", return_value=True):
            with patch.object(api, "_decrypt_resource", return_value={
                "out_trade_no": "order123",
                "transaction_id": "tx123",
                "trade_state": "SUCCESS"
            }):
                result = api.process_notify({
                    "headers": {
                        "Wechatpay-Timestamp": str(int(time.time())),
                        "Wechatpay-Nonce": "n",
                        "Wechatpay-Signature": "s"
                    },
                    "body": json.dumps({
                        "event_type": "TRANSACTION.SUCCESS",
                        "resource": {}
                    })
                })
                assert result["success"] is True
                assert result["out_trade_no"] == "order123"

    def test_verify_notify_signature_with_public_key_no_config(self, api, mock_config):
        mock_config.public_key_path = None
        result = api.verify_notify_signature_with_public_key("t", "n", "b", "s")
        assert result is False

    def test_verify_notify_signature_with_public_key_file_not_exists(self, api, mock_config):
        mock_config.public_key_path = "nonexistent.pem"
        with patch("os.path.exists", return_value=False):
            result = api.verify_notify_signature_with_public_key("t", "n", "b", "s")
            assert result is False

    def test_verify_notify_signature_with_public_key_invalid_key(self, api, mock_config):
        mock_config.public_key_path = "test.pem"
        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=b"invalid")):
                with patch("wechat_pay_v3_api.serialization.load_pem_public_key", side_effect=ValueError("Invalid key")):
                    result = api.verify_notify_signature_with_public_key("t", "n", "b", "s")
                    assert result is False


class TestCreateJsapiOrder:
    @pytest.fixture
    def mock_config(self):
        config = MagicMock()
        config.app_id = "test_app_id"
        config.mch_id = "test_mch_id"
        config.cert_serial_no = "test_serial"
        config.private_key_path = None
        config.public_key_path = None
        config.api_v3_key = "a" * 32
        config.notify_url = "https://test.com/notify"
        config.jsapi_pay_url = "https://api.test.com"
        return config

    def test_create_jsapi_order_success(self, mock_config):
        with patch("wechat_pay_v3_api.wechat_config", mock_config):
            from wechat_pay_v3_api import WeChatPayV3API
            api = WeChatPayV3API(config=mock_config)

            with patch.object(api, "_build_auth_header", return_value={"Authorization": "test"}):
                with patch("wechat_pay_v3_api.requests.post") as mock_post:
                    mock_response = MagicMock()
                    mock_response.status_code = 200
                    mock_response.json.return_value = {"prepay_id": "prepay123"}
                    mock_post.return_value = mock_response

                    result = api.create_jsapi_order("order123", 100, "test", "openid123")
                    assert result["success"] is True
                    assert result["prepay_id"] == "prepay123"

    def test_create_jsapi_order_http_error(self, mock_config):
        with patch("wechat_pay_v3_api.wechat_config", mock_config):
            from wechat_pay_v3_api import WeChatPayV3API
            api = WeChatPayV3API(config=mock_config)

            with patch.object(api, "_build_auth_header", return_value={"Authorization": "test"}):
                with patch("wechat_pay_v3_api.requests.post") as mock_post:
                    mock_response = MagicMock()
                    mock_response.status_code = 400
                    mock_response.content = b'{"message": "error"}'
                    mock_response.json.return_value = {"message": "error"}
                    mock_post.return_value = mock_response

                    result = api.create_jsapi_order("order123", 100, "test", "openid123")
                    assert result["success"] is False

    def test_create_jsapi_order_network_error(self, mock_config):
        with patch("wechat_pay_v3_api.wechat_config", mock_config):
            from wechat_pay_v3_api import WeChatPayV3API
            api = WeChatPayV3API(config=mock_config)

            with patch.object(api, "_build_auth_header", return_value={"Authorization": "test"}):
                with patch("wechat_pay_v3_api.requests.post", side_effect=Exception("Network error")):
                    result = api.create_jsapi_order("order123", 100, "test", "openid123")
                    assert result["success"] is False
                    assert "网络请求失败" in result["message"]


class TestCreateNativeOrder:
    @pytest.fixture
    def mock_config(self):
        config = MagicMock()
        config.app_id = "test_app_id"
        config.mch_id = "test_mch_id"
        config.cert_serial_no = "test_serial"
        config.private_key_path = None
        config.public_key_path = None
        config.api_v3_key = "a" * 32
        config.notify_url = "https://test.com/notify"
        config.native_pay_url = "https://api.test.com"
        return config

    def test_create_native_order_success(self, mock_config):
        with patch("wechat_pay_v3_api.wechat_config", mock_config):
            from wechat_pay_v3_api import WeChatPayV3API
            api = WeChatPayV3API(config=mock_config)

            with patch.object(api, "_build_auth_header", return_value={"Authorization": "test"}):
                with patch("wechat_pay_v3_api.requests.post") as mock_post:
                    mock_response = MagicMock()
                    mock_response.status_code = 200
                    mock_response.json.return_value = {"code_url": "weixin://pay"}
                    mock_post.return_value = mock_response

                    result = api.create_native_order("order123", 100, "test")
                    assert result["success"] is True
                    assert result["code_url"] == "weixin://pay"


class TestQueryOrder:
    @pytest.fixture
    def mock_config(self):
        config = MagicMock()
        config.app_id = "test_app_id"
        config.mch_id = "test_mch_id"
        config.cert_serial_no = "test_serial"
        config.private_key_path = None
        config.public_key_path = None
        config.api_v3_key = "a" * 32
        config.notify_url = "https://test.com/notify"
        config.order_query_url = "https://api.test.com"
        return config

    def test_query_order_success(self, mock_config):
        with patch("wechat_pay_v3_api.wechat_config", mock_config):
            from wechat_pay_v3_api import WeChatPayV3API
            api = WeChatPayV3API(config=mock_config)

            with patch.object(api, "_build_auth_header", return_value={"Authorization": "test"}):
                with patch("wechat_pay_v3_api.requests.get") as mock_get:
                    mock_response = MagicMock()
                    mock_response.status_code = 200
                    mock_response.json.return_value = {
                        "trade_state": "SUCCESS",
                        "trade_state_desc": "支付成功"
                    }
                    mock_get.return_value = mock_response

                    result = api.query_order("order123")
                    assert result["success"] is True
                    assert result["trade_state"] == "SUCCESS"

    def test_query_order_not_found(self, mock_config):
        with patch("wechat_pay_v3_api.wechat_config", mock_config):
            from wechat_pay_v3_api import WeChatPayV3API
            api = WeChatPayV3API(config=mock_config)

            with patch.object(api, "_build_auth_header", return_value={"Authorization": "test"}):
                with patch("wechat_pay_v3_api.requests.get") as mock_get:
                    mock_response = MagicMock()
                    mock_response.status_code = 404
                    mock_response.content = b'{"message": "not found"}'
                    mock_response.json.return_value = {"message": "not found"}
                    mock_get.return_value = mock_response

                    result = api.query_order("order123")
                    assert result["success"] is False
