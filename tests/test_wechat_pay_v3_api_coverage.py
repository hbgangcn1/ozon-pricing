import base64
import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

import wechat_pay_v3_api as wechat_pay_v3_api_module
from wechat_pay_v3_api import (
    SignatureVerificationError,
    WeChatPayError,
    WeChatPayV3API,
    WechatResponseSignatureError,
)


API_V3_KEY = "0123456789abcdef0123456789abcdef"


@pytest.fixture
def rsa_material(tmp_path):
    merchant_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    platform_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    merchant_private_pem = merchant_private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    merchant_private_key_path = tmp_path / "merchant_private.pem"
    merchant_private_key_path.write_bytes(merchant_private_pem)
    return {
        "merchant_private_key": merchant_private_key,
        "merchant_private_key_path": str(merchant_private_key_path),
        "platform_private_key": platform_private_key,
        "platform_public_key": platform_private_key.public_key(),
    }


@pytest.fixture
def api(rsa_material):
    config = SimpleNamespace(
        app_id="wx-app",
        mch_id="mch-id",
        cert_serial_no="merchant-serial",
        private_key_path=rsa_material["merchant_private_key_path"],
        api_v3_key=API_V3_KEY,
        notify_url="https://notify.example/pay",
        jsapi_pay_url="https://api.example/jsapi",
        native_pay_url="https://api.example/native",
        order_query_url="https://api.example/query",
        platform_public_key_id="platform-serial",
        platform_public_key=rsa_material["platform_public_key"],
    )
    return WeChatPayV3API(config=config)


def _signed_headers(api, platform_private_key, body_bytes, **overrides):
    timestamp = overrides.pop("Wechatpay-Timestamp", "1700000000")
    nonce = overrides.pop("Wechatpay-Nonce", "notify-nonce")
    serial = overrides.pop("Wechatpay-Serial", api.config.platform_public_key_id)
    message = getattr(api, "_build_platform_sign_message")(timestamp, nonce, body_bytes)
    signature = platform_private_key.sign(
        message,
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    headers = {
        "Wechatpay-Timestamp": timestamp,
        "Wechatpay-Nonce": nonce,
        "Wechatpay-Signature": base64.b64encode(signature).decode("utf-8"),
        "Wechatpay-Serial": serial,
    }
    headers.update(overrides)
    return headers


def _response(api, platform_private_key, body, status_code=200, **header_overrides):
    body_bytes = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
    response = Mock()
    response.status_code = status_code
    response.text = body_bytes.decode("utf-8", errors="ignore")
    response.content = body_bytes
    response.headers = _signed_headers(
        api,
        platform_private_key,
        body_bytes,
        **header_overrides,
    )
    try:
        response.json.return_value = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
    except json.JSONDecodeError:
        response.json.return_value = {}
    return response


def _encrypt_resource(data, api_key=API_V3_KEY, nonce="nonce-123456", associated_data="aad"):
    plaintext = json.dumps(data, separators=(",", ":")).encode("utf-8")
    ciphertext = AESGCM(api_key.encode("utf-8")).encrypt(
        nonce.encode("utf-8"),
        plaintext,
        associated_data.encode("utf-8"),
    )
    return {
        "ciphertext": base64.b64encode(ciphertext).decode("utf-8"),
        "nonce": nonce,
        "associated_data": associated_data,
    }


def test_load_private_key_no_path(api):
    api.config.private_key_path = None

    assert api._load_private_key() is None


def test_load_private_key_missing_file_returns_none(api):
    api.config.private_key_path = "missing.pem"

    with patch("wechat_pay_v3_api.os.path.exists", return_value=False):
        assert api._load_private_key() is None


def test_load_private_key_success_and_cache(api):
    first = api._load_private_key()
    second = api._load_private_key()

    assert isinstance(first, rsa.RSAPrivateKey)
    assert second is first


def test_load_private_key_load_failure(api, tmp_path):
    bad_file = tmp_path / "bad.pem"
    bad_file.write_text("not a key", encoding="utf-8")
    api.config.private_key_path = str(bad_file)

    assert api._load_private_key() is None


def test_load_private_key_non_rsa_returns_none(api):
    with patch("wechat_pay_v3_api.os.path.exists", return_value=True):
        with patch("builtins.open", create=True):
            with patch(
                "wechat_pay_v3_api.serialization.load_pem_private_key",
                return_value=object(),
            ):
                assert api._load_private_key() is None


def test_get_timestamp_and_nonce(api, monkeypatch):
    monkeypatch.setattr(wechat_pay_v3_api_module.time, "time", lambda: 1_700_000_123)
    with patch("wechat_pay_v3_api.secrets.token_urlsafe", return_value="nonce-token"):
        assert api._get_timestamp() == "1700000123"
        assert api._get_nonce_str() == "nonce-token"


def test_build_signature_and_auth_header(api, rsa_material, monkeypatch):
    monkeypatch.setattr(wechat_pay_v3_api_module.time, "time", lambda: 1_700_000_123)
    with patch("wechat_pay_v3_api.secrets.token_urlsafe", return_value="nonce-token"):
        signature = api._build_signature("POST", "/v3/pay/test", "1700000123", "nonce-token", '{"a":1}')
        assert isinstance(signature, str)
        header = api._build_auth_header("POST", "/v3/pay/test", '{"a":1}')

    assert header["Content-Type"] == "application/json"
    assert header["Accept"] == "application/json"
    assert 'mchid="mch-id"' in header["Authorization"]
    assert 'nonce_str="nonce-token"' in header["Authorization"]
    assert 'timestamp="1700000123"' in header["Authorization"]
    assert 'serial_no="merchant-serial"' in header["Authorization"]


def test_build_signature_requires_private_key(api):
    with patch.object(api, "_load_private_key", return_value=None):
        with pytest.raises(Exception, match="商户私钥未配置或加载失败"):
            api._build_signature("POST", "/v3/pay/test", "1700000123", "nonce-token", "")


def test_extract_header_handles_non_string_and_rejects_bad_values(api):
    extract_header = getattr(api, "_extract_header")

    assert extract_header({"X-Test": 123}, "X-Test") == "123"

    with pytest.raises(SignatureVerificationError, match="X-Missing"):
        extract_header({}, "X-Missing")
    with pytest.raises(SignatureVerificationError, match="X-Empty"):
        extract_header({"X-Empty": ""}, "X-Empty")
    with pytest.raises(SignatureVerificationError, match="格式非法"):
        extract_header({"X-Comma": "a,b"}, "X-Comma")


def test_decode_platform_signature_invalid_base64(api):
    decode_signature = getattr(api, "_decode_platform_signature")

    with pytest.raises(SignatureVerificationError, match="格式非法"):
        decode_signature("%%%not-base64%%%")


def test_verify_platform_signature_invalid_timestamp(api):
    with pytest.raises(SignatureVerificationError, match="时间戳格式非法"):
        api.verify_platform_signature(
            {
                "Wechatpay-Timestamp": "not-a-number",
                "Wechatpay-Nonce": "nonce",
                "Wechatpay-Signature": "sig",
                "Wechatpay-Serial": api.config.platform_public_key_id,
            },
            b"{}",
        )


def test_verify_platform_signature_expired_timestamp(api, rsa_material, monkeypatch):
    monkeypatch.setattr(wechat_pay_v3_api_module.time, "time", lambda: 1_700_000_000)
    headers = _signed_headers(
        api,
        rsa_material["platform_private_key"],
        b"{}",
        **{"Wechatpay-Timestamp": "1699999699"},
    )

    with pytest.raises(SignatureVerificationError, match="已过期"):
        api.verify_platform_signature(headers, b"{}")


def test_verify_platform_signature_requires_public_key_id(api, rsa_material, monkeypatch):
    monkeypatch.setattr(wechat_pay_v3_api_module.time, "time", lambda: 1_700_000_000)
    api.config.platform_public_key_id = ""
    headers = _signed_headers(
        api,
        rsa_material["platform_private_key"],
        b"{}",
        **{"Wechatpay-Serial": "serial-present"},
    )

    with pytest.raises(SignatureVerificationError, match="公钥ID未配置"):
        api.verify_platform_signature(headers, b"{}")


def test_verify_platform_signature_serial_mismatch(api, rsa_material, monkeypatch):
    monkeypatch.setattr(wechat_pay_v3_api_module.time, "time", lambda: 1_700_000_000)
    headers = _signed_headers(
        api,
        rsa_material["platform_private_key"],
        b"{}",
        **{"Wechatpay-Serial": "wrong-serial"},
    )

    with pytest.raises(SignatureVerificationError, match="序列号不匹配"):
        api.verify_platform_signature(headers, b"{}")


def test_verify_platform_signature_requires_loaded_public_key(api, rsa_material, monkeypatch):
    monkeypatch.setattr(wechat_pay_v3_api_module.time, "time", lambda: 1_700_000_000)
    api.config.platform_public_key = None
    headers = _signed_headers(api, rsa_material["platform_private_key"], b"{}")

    with pytest.raises(SignatureVerificationError, match="公钥未加载"):
        api.verify_platform_signature(headers, b"{}")


def test_verify_platform_signature_success(api, rsa_material, monkeypatch):
    monkeypatch.setattr(wechat_pay_v3_api_module.time, "time", lambda: 1_700_000_000)
    body = b'{"ok":true}'
    headers = _signed_headers(api, rsa_material["platform_private_key"], body)

    api.verify_platform_signature(headers, body)


def test_verify_platform_signature_verify_failure(api, rsa_material, monkeypatch):
    monkeypatch.setattr(wechat_pay_v3_api_module.time, "time", lambda: 1_700_000_000)
    body = b'{"ok":true}'
    other_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    headers = _signed_headers(api, other_private_key, body)

    with pytest.raises(SignatureVerificationError, match="平台签名验证失败"):
        api.verify_platform_signature(headers, body)


def test_parse_verified_response_empty_body(api, rsa_material, monkeypatch):
    monkeypatch.setattr(wechat_pay_v3_api_module.time, "time", lambda: 1_700_000_000)
    response = _response(api, rsa_material["platform_private_key"], b"")

    assert api._parse_verified_response(response, WechatResponseSignatureError) == {}


def test_parse_verified_response_invalid_json(api, rsa_material, monkeypatch):
    monkeypatch.setattr(wechat_pay_v3_api_module.time, "time", lambda: 1_700_000_000)
    response = _response(api, rsa_material["platform_private_key"], b"{bad-json")

    with pytest.raises(WechatResponseSignatureError, match="JSON解析失败"):
        api._parse_verified_response(response, WechatResponseSignatureError)


def test_parse_verified_response_signature_failure_maps_error(api):
    response = Mock(headers={}, content=b"{}")

    with patch.object(
        api,
        "verify_platform_signature",
        side_effect=SignatureVerificationError("sign bad"),
    ):
        with pytest.raises(WechatResponseSignatureError, match="sign bad"):
            api._parse_verified_response(response, WechatResponseSignatureError)


def test_handle_api_error_signature_failure(api):
    response = Mock(status_code=400)

    with patch.object(
        api,
        "_parse_verified_response",
        side_effect=WechatResponseSignatureError("sig fail"),
    ):
        with pytest.raises(WechatResponseSignatureError, match="sig fail"):
            api._handle_api_error(response)


def test_handle_api_error_http_fallback(api):
    response = Mock(status_code=500)

    with patch.object(api, "_parse_verified_response", return_value={}):
        result = api._handle_api_error(response)

    assert result == {"success": False, "message": "HTTP 500"}


def test_create_jsapi_order_kwargs_handling(api, rsa_material, monkeypatch):
    monkeypatch.setattr(wechat_pay_v3_api_module.time, "time", lambda: 1_700_000_000)
    response = _response(api, rsa_material["platform_private_key"], {"prepay_id": "prepay-1"})

    with patch.object(api, "_build_auth_header", return_value={"Authorization": "test-auth"}):
        with patch("wechat_pay_v3_api.requests.post", return_value=response) as post_mock:
            result = api.create_jsapi_order(
                "order-1",
                1234,
                "套餐",
                "openid-1",
                time_expire="2026-12-31T00:00:00+08:00",
                attach="attach-1",
                goods_tag="tag-1",
                ignored="value",
            )

    sent_body = json.loads(post_mock.call_args.kwargs["data"])
    assert sent_body["time_expire"] == "2026-12-31T00:00:00+08:00"
    assert sent_body["attach"] == "attach-1"
    assert sent_body["goods_tag"] == "tag-1"
    assert "ignored" not in sent_body
    assert result["success"] is True
    assert result["prepay_id"] == "prepay-1"


def test_create_jsapi_order_http_error(api, rsa_material, monkeypatch):
    monkeypatch.setattr(wechat_pay_v3_api_module.time, "time", lambda: 1_700_000_000)
    response = _response(
        api,
        rsa_material["platform_private_key"],
        {"message": "invalid request"},
        status_code=400,
    )

    with patch.object(api, "_build_auth_header", return_value={"Authorization": "test-auth"}):
        with patch("wechat_pay_v3_api.requests.post", return_value=response):
            result = api.create_jsapi_order("order-1", 1234, "套餐", "openid-1")

    assert result == {"success": False, "message": "invalid request"}


def test_create_jsapi_order_signature_error_reraise(api):
    with patch.object(api, "_build_auth_header", return_value={"Authorization": "test-auth"}):
        with patch("wechat_pay_v3_api.requests.post", return_value=Mock(status_code=200)):
            with patch.object(
                api,
                "_parse_verified_response",
                side_effect=WechatResponseSignatureError("bad sign"),
            ):
                with pytest.raises(WechatResponseSignatureError, match="bad sign"):
                    api.create_jsapi_order("order-1", 1234, "套餐", "openid-1")


def test_create_jsapi_order_network_failure(api):
    with patch.object(api, "_build_auth_header", return_value={"Authorization": "test-auth"}):
        with patch("wechat_pay_v3_api.requests.post", side_effect=RuntimeError("network down")):
            result = api.create_jsapi_order("order-1", 1234, "套餐", "openid-1")

    assert result["success"] is False
    assert "网络请求失败" in result["message"]


def test_create_native_order_kwargs_handling(api, rsa_material, monkeypatch):
    monkeypatch.setattr(wechat_pay_v3_api_module.time, "time", lambda: 1_700_000_000)
    response = _response(api, rsa_material["platform_private_key"], {"code_url": "weixin://code"})

    with patch.object(api, "_build_auth_header", return_value={"Authorization": "test-auth"}):
        with patch("wechat_pay_v3_api.requests.post", return_value=response) as post_mock:
            result = api.create_native_order(
                "order-2",
                2234,
                "套餐",
                time_expire="2026-12-31T00:00:00+08:00",
                attach="attach-2",
                goods_tag="tag-2",
                ignored="value",
            )

    sent_body = json.loads(post_mock.call_args.kwargs["data"])
    assert sent_body["time_expire"] == "2026-12-31T00:00:00+08:00"
    assert sent_body["attach"] == "attach-2"
    assert sent_body["goods_tag"] == "tag-2"
    assert "ignored" not in sent_body
    assert result["success"] is True
    assert result["code_url"] == "weixin://code"


def test_create_native_order_http_error(api, rsa_material, monkeypatch):
    monkeypatch.setattr(wechat_pay_v3_api_module.time, "time", lambda: 1_700_000_000)
    response = _response(
        api,
        rsa_material["platform_private_key"],
        {"message": "native bad"},
        status_code=400,
    )

    with patch.object(api, "_build_auth_header", return_value={"Authorization": "test-auth"}):
        with patch("wechat_pay_v3_api.requests.post", return_value=response):
            result = api.create_native_order("order-2", 2234, "套餐")

    assert result == {"success": False, "message": "native bad"}


def test_create_native_order_signature_error_reraise(api):
    with patch.object(api, "_build_auth_header", return_value={"Authorization": "test-auth"}):
        with patch("wechat_pay_v3_api.requests.post", return_value=Mock(status_code=200)):
            with patch.object(
                api,
                "_parse_verified_response",
                side_effect=WechatResponseSignatureError("native sign fail"),
            ):
                with pytest.raises(WechatResponseSignatureError, match="native sign fail"):
                    api.create_native_order("order-2", 2234, "套餐")


def test_create_native_order_network_failure(api):
    with patch.object(api, "_build_auth_header", return_value={"Authorization": "test-auth"}):
        with patch("wechat_pay_v3_api.requests.post", side_effect=RuntimeError("network down")):
            result = api.create_native_order("order-2", 2234, "套餐")

    assert result["success"] is False
    assert "网络请求失败" in result["message"]


def test_query_order_success(api, rsa_material, monkeypatch):
    monkeypatch.setattr(wechat_pay_v3_api_module.time, "time", lambda: 1_700_000_000)
    response = _response(
        api,
        rsa_material["platform_private_key"],
        {"trade_state": "SUCCESS", "trade_state_desc": "支付成功"},
    )

    with patch.object(api, "_build_auth_header", return_value={"Authorization": "test-auth"}):
        with patch("wechat_pay_v3_api.requests.get", return_value=response):
            result = api.query_order("order-3")

    assert result["success"] is True
    assert result["trade_state"] == "SUCCESS"
    assert result["trade_state_desc"] == "支付成功"


def test_query_order_http_error(api, rsa_material, monkeypatch):
    monkeypatch.setattr(wechat_pay_v3_api_module.time, "time", lambda: 1_700_000_000)
    response = _response(
        api,
        rsa_material["platform_private_key"],
        {"message": "not found"},
        status_code=404,
    )

    with patch.object(api, "_build_auth_header", return_value={"Authorization": "test-auth"}):
        with patch("wechat_pay_v3_api.requests.get", return_value=response):
            result = api.query_order("order-3")

    assert result == {"success": False, "message": "not found"}


def test_query_order_signature_error_reraise(api):
    with patch.object(api, "_build_auth_header", return_value={"Authorization": "test-auth"}):
        with patch("wechat_pay_v3_api.requests.get", return_value=Mock(status_code=200)):
            with patch.object(
                api,
                "_parse_verified_response",
                side_effect=WechatResponseSignatureError("query sign fail"),
            ):
                with pytest.raises(WechatResponseSignatureError, match="query sign fail"):
                    api.query_order("order-3")


def test_query_order_network_failure(api):
    with patch.object(api, "_build_auth_header", return_value={"Authorization": "test-auth"}):
        with patch("wechat_pay_v3_api.requests.get", side_effect=RuntimeError("network down")):
            result = api.query_order("order-3")

    assert result["success"] is False
    assert "网络请求失败" in result["message"]


def test_verify_notify_signature_not_implemented(api):
    with pytest.raises(NotImplementedError, match="请改用平台公钥签名验证"):
        api.verify_notify_signature("ts", "nonce", "body", "sig")


def test_decrypt_resource_invalid_api_key_length(api):
    api.config.api_v3_key = "short"

    assert api._decrypt_resource({"ciphertext": "x", "nonce": "n", "associated_data": "a"}) == {}


def test_decrypt_resource_missing_fields(api):
    assert api._decrypt_resource({}) == {}


def test_decrypt_resource_success(api):
    resource = _encrypt_resource(
        {
            "out_trade_no": "order-5",
            "transaction_id": "tx-5",
            "trade_state": "SUCCESS",
        }
    )

    result = api._decrypt_resource(resource)

    assert result["out_trade_no"] == "order-5"
    assert result["transaction_id"] == "tx-5"
    assert result["trade_state"] == "SUCCESS"


def test_decrypt_resource_failure_returns_empty(api):
    assert api._decrypt_resource(
        {
            "ciphertext": "%%%bad%%%",
            "nonce": "nonce-123456",
            "associated_data": "aad",
        }
    ) == {}


def test_process_notify_signature_failure(api):
    with patch.object(
        api,
        "verify_platform_signature",
        side_effect=SignatureVerificationError("bad signature"),
    ):
        with pytest.raises(WeChatPayError, match="signature verification failed"):
            api.process_notify({}, b"{}")


def test_process_notify_non_transaction_success(api):
    body = json.dumps({"event_type": "REFUND.SUCCESS"}).encode("utf-8")

    with patch.object(api, "verify_platform_signature", return_value=None):
        with patch.object(api, "_extract_header", return_value="nonce-ok"):
            payload = api.process_notify({}, body)

    assert payload is None


def test_process_notify_decrypt_failure(api):
    body = json.dumps(
        {"event_type": "TRANSACTION.SUCCESS", "resource": {"ciphertext": "bad"}}
    ).encode("utf-8")

    with patch.object(api, "verify_platform_signature", return_value=None):
        with patch.object(api, "_extract_header", return_value="nonce-ok"):
            with patch.object(api, "_decrypt_resource", return_value={}):
                with pytest.raises(WeChatPayError):
                    api.process_notify({}, body)


def test_process_notify_success(api, rsa_material, monkeypatch):
    monkeypatch.setattr(wechat_pay_v3_api_module.time, "time", lambda: 1_700_000_000)
    payload_dict = {
        "event_type": "TRANSACTION.SUCCESS",
        "resource": _encrypt_resource(
            {
                "out_trade_no": "order-6",
                "transaction_id": "tx-6",
                "trade_state": "SUCCESS",
            }
        ),
    }
    body = json.dumps(payload_dict).encode("utf-8")
    headers = _signed_headers(api, rsa_material["platform_private_key"], body)

    payload = api.process_notify(headers, body)
    assert payload is not None
    assert payload["out_trade_no"] == "order-6"
    assert payload["transaction_id"] == "tx-6"
    assert payload["trade_state"] == "SUCCESS"


def test_process_notify_general_exception(api):
    with patch.object(api, "verify_platform_signature", return_value=None):
        with patch.object(api, "_extract_header", return_value="nonce-ok"):
            with pytest.raises(WeChatPayError):
                api.process_notify({}, b"not-json")


def test_verify_notify_signature_with_public_key_success(api, monkeypatch):
    captured = {}

    def fake_verify(headers, raw_body):
        captured["headers"] = headers
        captured["raw_body"] = raw_body

    monkeypatch.setattr(api, "verify_platform_signature", fake_verify)

    result = api.verify_notify_signature_with_public_key(
        "1700000000",
        "nonce-1",
        '{"k":1}',
        "signature-1",
        serial="serial-1",
    )

    assert result is True
    assert captured["headers"]["Wechatpay-Serial"] == "serial-1"
    assert captured["raw_body"] == b'{"k":1}'


def test_verify_notify_signature_with_public_key_failure(api):
    with patch.object(
        api,
        "verify_platform_signature",
        side_effect=SignatureVerificationError("bad sign"),
    ):
        result = api.verify_notify_signature_with_public_key(
            "1700000000",
            "nonce-1",
            '{"k":1}',
            "signature-1",
        )

    assert result is False
