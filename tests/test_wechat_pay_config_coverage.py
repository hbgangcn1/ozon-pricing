import importlib
import builtins
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

import wechat_pay_config as wechat_pay_config_module


ENV_KEYS = [
    "WECHAT_APP_ID",
    "WECHAT_MCH_ID",
    "WECHAT_PRIVATE_KEY_PATH",
    "WECHAT_API_V3_KEY",
    "WECHAT_CERT_SERIAL_NO",
    "WECHAT_PUBLIC_KEY_PATH",
    "WECHAT_PUBLIC_KEY_ID",
    "WECHAT_NOTIFY_URL",
    "WECHAT_RETURN_URL",
    "WECHAT_SANDBOX",
    "WECHAT_CERT_DIR",
    "PRODUCTION_MODE",
    "LOCAL_TEST_MODE",
]


@pytest.fixture(autouse=True)
def clear_wechat_env(monkeypatch):
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


@pytest.fixture
def public_key_file(tmp_path):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    path = tmp_path / "wechat_public.pem"
    path.write_bytes(pem)
    return path


def _config(**overrides):
    values = {
        "app_id": "wx-app",
        "mch_id": "mch-id",
        "api_v3_key": "a" * 32,
        "private_key_path": "merchant.pem",
        "cert_serial_no": "ABCDEF",
        "public_key_path": None,
        "platform_public_key_id": None,
        "platform_public_key": None,
        "notify_url": "https://notify.example",
        "return_url": "https://return.example",
        "sandbox": False,
    }
    values.update(overrides)
    return wechat_pay_config_module.WeChatPayConfig(**values)


def test_config_url_properties():
    config = _config()

    assert config.api_base_url == "https://api.mch.weixin.qq.com"
    assert config.unified_order_url == "https://api.mch.weixin.qq.com/v3/pay/transactions"
    assert config.jsapi_pay_url == "https://api.mch.weixin.qq.com/v3/pay/transactions/jsapi"
    assert config.native_pay_url == "https://api.mch.weixin.qq.com/v3/pay/transactions/native"
    assert config.h5_pay_url == "https://api.mch.weixin.qq.com/v3/pay/transactions/h5"
    assert config.order_query_url == "https://api.mch.weixin.qq.com/v3/pay/transactions/out-trade-no"
    assert config.refund_url == "https://api.mch.weixin.qq.com/v3/refund/domestic/refunds"


def test_clean_cert_serial_variants():
    clean_cert_serial = getattr(wechat_pay_config_module, "_clean_cert_serial")

    assert clean_cert_serial("") is None
    assert clean_cert_serial(None) is None
    assert clean_cert_serial("aa:bb cc-dd") == "AABBCCDD"


def test_is_wechat_pay_enabled_missing_vars(monkeypatch):
    is_enabled = getattr(wechat_pay_config_module, "_is_wechat_pay_enabled")
    monkeypatch.setenv("WECHAT_APP_ID", "wx-app")
    monkeypatch.setenv("WECHAT_MCH_ID", "mch-id")

    assert is_enabled() is False


def test_is_wechat_pay_enabled_all_required_present(monkeypatch, tmp_path):
    is_enabled = getattr(wechat_pay_config_module, "_is_wechat_pay_enabled")
    key_path = tmp_path / "merchant.pem"
    key_path.write_text("placeholder", encoding="utf-8")
    monkeypatch.setenv("WECHAT_APP_ID", "wx-app")
    monkeypatch.setenv("WECHAT_MCH_ID", "mch-id")
    monkeypatch.setenv("WECHAT_PRIVATE_KEY_PATH", str(key_path))

    assert is_enabled() is True


def test_load_platform_public_key_success(public_key_file):
    load_public_key = getattr(wechat_pay_config_module, "_load_platform_public_key")

    public_key = load_public_key(str(public_key_file))

    assert isinstance(public_key, rsa.RSAPublicKey)


def test_load_platform_public_key_invalid_file(tmp_path):
    load_public_key = getattr(wechat_pay_config_module, "_load_platform_public_key")
    bad_file = tmp_path / "bad.pem"
    bad_file.write_text("not a pem", encoding="utf-8")

    with pytest.raises(ValueError):
        load_public_key(str(bad_file))


def test_validate_enabled_config_missing_public_key_id(public_key_file):
    validate_enabled_config = getattr(
        wechat_pay_config_module,
        "_validate_enabled_config",
    )
    config = _config(public_key_path=str(public_key_file), platform_public_key_id=None)

    with pytest.raises(RuntimeError, match="WECHAT_PUBLIC_KEY_ID"):
        validate_enabled_config(config)


def test_validate_enabled_config_missing_public_key_path():
    validate_enabled_config = getattr(
        wechat_pay_config_module,
        "_validate_enabled_config",
    )
    config = _config(public_key_path=None, platform_public_key_id="serial-1")

    with pytest.raises(RuntimeError, match="WECHAT_PUBLIC_KEY_PATH"):
        validate_enabled_config(config)


def test_validate_enabled_config_file_not_exists(tmp_path):
    validate_enabled_config = getattr(
        wechat_pay_config_module,
        "_validate_enabled_config",
    )
    config = _config(
        public_key_path=str(tmp_path / "missing.pem"),
        platform_public_key_id="serial-1",
    )

    with pytest.raises(RuntimeError, match="公钥文件不存在"):
        validate_enabled_config(config)


def test_validate_enabled_config_load_failure(tmp_path):
    validate_enabled_config = getattr(
        wechat_pay_config_module,
        "_validate_enabled_config",
    )
    bad_file = tmp_path / "bad.pem"
    bad_file.write_text("not a pem", encoding="utf-8")
    config = _config(
        public_key_path=str(bad_file),
        platform_public_key_id="serial-1",
    )

    with pytest.raises(RuntimeError, match="公钥加载失败"):
        validate_enabled_config(config)


def test_validate_enabled_config_success(public_key_file):
    validate_enabled_config = getattr(
        wechat_pay_config_module,
        "_validate_enabled_config",
    )
    config = _config(
        public_key_path=str(public_key_file),
        platform_public_key_id="serial-1",
    )

    validate_enabled_config(config)

    assert isinstance(config.platform_public_key, rsa.RSAPublicKey)


def test_preload_optional_public_key_skips_missing_path():
    preload_public_key = getattr(
        wechat_pay_config_module,
        "_preload_optional_public_key",
    )
    config = _config(public_key_path=None)

    preload_public_key(config)

    assert config.platform_public_key is None


def test_preload_optional_public_key_success(public_key_file):
    preload_public_key = getattr(
        wechat_pay_config_module,
        "_preload_optional_public_key",
    )
    config = _config(public_key_path=str(public_key_file))

    preload_public_key(config)

    assert isinstance(config.platform_public_key, rsa.RSAPublicKey)


def test_preload_optional_public_key_exception(tmp_path):
    preload_public_key = getattr(
        wechat_pay_config_module,
        "_preload_optional_public_key",
    )
    bad_file = tmp_path / "bad.pem"
    bad_file.write_text("not a pem", encoding="utf-8")
    config = _config(public_key_path=str(bad_file))

    preload_public_key(config)

    assert config.platform_public_key is None


def test_finalize_config_enabled_validation(monkeypatch):
    finalize_config = getattr(wechat_pay_config_module, "_finalize_config")
    config = _config()
    calls = []
    monkeypatch.setattr(wechat_pay_config_module, "_is_wechat_pay_enabled", lambda: True)
    monkeypatch.setattr(
        wechat_pay_config_module,
        "_validate_enabled_config",
        lambda cfg: calls.append(("validate", cfg)),
    )
    monkeypatch.setattr(
        wechat_pay_config_module,
        "_preload_optional_public_key",
        lambda cfg: calls.append(("preload", cfg)),
    )

    result = finalize_config(config)

    assert result is config
    assert calls == [("validate", config)]


def test_finalize_config_disabled_preload(monkeypatch):
    finalize_config = getattr(wechat_pay_config_module, "_finalize_config")
    config = _config()
    calls = []
    monkeypatch.setattr(wechat_pay_config_module, "_is_wechat_pay_enabled", lambda: False)
    monkeypatch.setattr(
        wechat_pay_config_module,
        "_validate_enabled_config",
        lambda cfg: calls.append(("validate", cfg)),
    )
    monkeypatch.setattr(
        wechat_pay_config_module,
        "_preload_optional_public_key",
        lambda cfg: calls.append(("preload", cfg)),
    )

    result = finalize_config(config)

    assert result is config
    assert calls == [("preload", config)]


def test_get_wechat_pay_config_production_mode(monkeypatch):
    get_config = getattr(wechat_pay_config_module, "get_wechat_pay_config")
    expected = _config(app_id="prod-app")
    monkeypatch.setenv("PRODUCTION_MODE", "true")
    monkeypatch.setitem(
        sys.modules,
        "production_wechat_config",
        SimpleNamespace(get_production_config=lambda: expected),
    )
    monkeypatch.setattr(wechat_pay_config_module, "_finalize_config", lambda cfg: cfg)

    result = get_config()

    assert result is expected


def test_get_wechat_pay_config_local_test_mode(monkeypatch):
    get_config = getattr(wechat_pay_config_module, "get_wechat_pay_config")
    expected = _config(app_id="local-app")
    monkeypatch.setenv("LOCAL_TEST_MODE", "true")
    monkeypatch.setitem(
        sys.modules,
        "local_test_config",
        SimpleNamespace(get_local_test_config=lambda: expected),
    )
    monkeypatch.setattr(wechat_pay_config_module, "_finalize_config", lambda cfg: cfg)

    result = get_config()

    assert result is expected


def test_get_wechat_pay_config_local_test_import_fail(monkeypatch):
    get_config = getattr(wechat_pay_config_module, "get_wechat_pay_config")
    real_import = builtins.__import__
    monkeypatch.setenv("LOCAL_TEST_MODE", "true")
    monkeypatch.delitem(sys.modules, "local_test_config", raising=False)

    def fake_import(name, *args, **kwargs):
        if name == "local_test_config":
            raise ImportError("missing local config")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    monkeypatch.setattr(wechat_pay_config_module, "_finalize_config", lambda cfg: cfg)

    result = get_config()

    assert isinstance(result, wechat_pay_config_module.WeChatPayConfig)
    assert result.app_id == ""


def test_get_wechat_pay_config_env_vars(monkeypatch, public_key_file, tmp_path):
    get_config = getattr(wechat_pay_config_module, "get_wechat_pay_config")
    private_key_path = tmp_path / "merchant.pem"
    private_key_path.write_text("merchant key", encoding="utf-8")
    monkeypatch.setenv("WECHAT_APP_ID", "wx-app")
    monkeypatch.setenv("WECHAT_MCH_ID", "mch-id")
    monkeypatch.setenv("WECHAT_PRIVATE_KEY_PATH", str(private_key_path))
    monkeypatch.setenv("WECHAT_API_V3_KEY", "b" * 32)
    monkeypatch.setenv("WECHAT_CERT_SERIAL_NO", "aa:bb-cc dd")
    monkeypatch.setenv("WECHAT_PUBLIC_KEY_PATH", str(public_key_file))
    monkeypatch.setenv("WECHAT_PUBLIC_KEY_ID", "serial-1")
    monkeypatch.setenv("WECHAT_NOTIFY_URL", "https://notify.example/pay")
    monkeypatch.setenv("WECHAT_RETURN_URL", "https://return.example/pay")
    monkeypatch.setenv("WECHAT_SANDBOX", "true")

    config = get_config()

    assert config.app_id == "wx-app"
    assert config.mch_id == "mch-id"
    assert config.api_v3_key == "b" * 32
    assert config.private_key_path == str(private_key_path)
    assert config.cert_serial_no == "AABBCCDD"
    assert config.public_key_path == str(public_key_file)
    assert config.platform_public_key_id == "serial-1"
    assert config.notify_url == "https://notify.example/pay"
    assert config.return_url == "https://return.example/pay"
    assert config.sandbox is True
    assert isinstance(config.platform_public_key, rsa.RSAPublicKey)


def test_get_wechat_pay_config_defaults_cert_dir(monkeypatch):
    get_config = getattr(wechat_pay_config_module, "get_wechat_pay_config")
    monkeypatch.setattr(wechat_pay_config_module, "_finalize_config", lambda cfg: cfg)

    config = get_config()

    assert config.private_key_path.endswith("cert\\apiclient_key.pem") or config.private_key_path.endswith("cert/apiclient_key.pem")


def test_module_import_fallbacks_cover_logger_and_dotenv(monkeypatch):
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "logger_config":
            raise ImportError("missing logger_config")
        if name == "dotenv":
            raise ImportError("missing dotenv")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    monkeypatch.delitem(sys.modules, "wechat_pay_config", raising=False)

    imported = importlib.import_module("wechat_pay_config")

    assert imported.load_dotenv() is False
    assert imported.logger.name == "wechat_pay_config"

    monkeypatch.setitem(sys.modules, "wechat_pay_config", wechat_pay_config_module)


def test_load_platform_public_key_rejects_non_rsa(monkeypatch, tmp_path):
    load_public_key = getattr(wechat_pay_config_module, "_load_platform_public_key")
    pem_path = tmp_path / "anything.pem"
    pem_path.write_text("ignored", encoding="utf-8")

    with patch(
        "wechat_pay_config.serialization.load_pem_public_key",
        return_value=SimpleNamespace(),
    ):
        with pytest.raises(RuntimeError, match="必须是RSA公钥"):
            load_public_key(str(pem_path))
