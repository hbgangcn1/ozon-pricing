# -*- coding: utf-8 -*-
"""微信支付配置模块。"""

import logging
import os
from dataclasses import dataclass
from typing import Optional

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

try:
    from logger_config import logger
except ImportError:
    logger = logging.getLogger(__name__)

try:
    from dotenv import load_dotenv

    load_dotenv(override=True)
except ImportError:
    def load_dotenv(*args, **kwargs) -> bool:
        _ = args, kwargs
        return False


@dataclass
class WeChatPayConfig:
    """微信支付v3配置类。"""

    app_id: str = ""
    mch_id: str = ""
    api_v3_key: str = ""
    private_key_path: Optional[str] = None
    cert_serial_no: Optional[str] = None
    public_key_path: Optional[str] = None
    platform_public_key_id: Optional[str] = None
    platform_public_key: Optional[rsa.RSAPublicKey] = None
    notify_url: str = ""
    return_url: str = ""
    sandbox: bool = False

    @property
    def api_base_url(self) -> str:
        return "https://api.mch.weixin.qq.com"

    @property
    def unified_order_url(self) -> str:
        return f"{self.api_base_url}/v3/pay/transactions"

    @property
    def jsapi_pay_url(self) -> str:
        return f"{self.api_base_url}/v3/pay/transactions/jsapi"

    @property
    def native_pay_url(self) -> str:
        return f"{self.api_base_url}/v3/pay/transactions/native"

    @property
    def h5_pay_url(self) -> str:
        return f"{self.api_base_url}/v3/pay/transactions/h5"

    @property
    def order_query_url(self) -> str:
        return f"{self.api_base_url}/v3/pay/transactions/out-trade-no"

    @property
    def refund_url(self) -> str:
        return f"{self.api_base_url}/v3/refund/domestic/refunds"


def _clean_cert_serial(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return value.replace(":", "").replace(" ", "").replace("-", "").upper()


def _is_wechat_pay_enabled() -> bool:
    return all(
        [
            os.getenv("WECHAT_APP_ID"),
            os.getenv("WECHAT_MCH_ID"),
            os.getenv("WECHAT_PRIVATE_KEY_PATH"),
        ]
    )


def _load_platform_public_key(public_key_path: str) -> rsa.RSAPublicKey:
    with open(public_key_path, "rb") as key_file:
        public_key = serialization.load_pem_public_key(key_file.read())
    if not isinstance(public_key, rsa.RSAPublicKey):
        raise RuntimeError("微信支付平台公钥必须是RSA公钥")
    return public_key


def _validate_enabled_config(config: WeChatPayConfig) -> None:
    if not config.platform_public_key_id:
        raise RuntimeError("微信支付启用时必须配置 WECHAT_PUBLIC_KEY_ID")
    if not config.public_key_path:
        raise RuntimeError("微信支付启用时必须配置 WECHAT_PUBLIC_KEY_PATH")
    if not os.path.exists(config.public_key_path):
        raise RuntimeError("微信支付平台公钥文件不存在")
    try:
        config.platform_public_key = _load_platform_public_key(
            config.public_key_path
        )
    except Exception as exc:
        raise RuntimeError("微信支付平台公钥加载失败") from exc


def _preload_optional_public_key(config: WeChatPayConfig) -> None:
    if not config.public_key_path or not os.path.exists(config.public_key_path):
        return
    try:
        config.platform_public_key = _load_platform_public_key(config.public_key_path)
    except Exception:
        logger.warning("微信支付平台公钥预加载失败，已跳过", exc_info=True)


def _finalize_config(config: WeChatPayConfig) -> WeChatPayConfig:
    if _is_wechat_pay_enabled():
        _validate_enabled_config(config)
    else:
        _preload_optional_public_key(config)
    return config


def get_wechat_pay_config() -> WeChatPayConfig:
    """从环境变量或配置文件获取微信支付配置。"""
    if os.getenv("PRODUCTION_MODE", "false").lower() == "true":
        from production_wechat_config import get_production_config

        return _finalize_config(get_production_config())

    if os.getenv("LOCAL_TEST_MODE", "false").lower() == "true":
        try:
            from local_test_config import get_local_test_config  # type: ignore[import-untyped]

            return _finalize_config(get_local_test_config())
        except ImportError:
            logger.warning("本地测试配置模块未找到，将使用默认配置")

    cert_dir = os.getenv("WECHAT_CERT_DIR", "cert")
    config = WeChatPayConfig(
        app_id=os.getenv("WECHAT_APP_ID", ""),
        mch_id=os.getenv("WECHAT_MCH_ID", ""),
        api_v3_key=os.getenv("WECHAT_API_V3_KEY", ""),
        private_key_path=os.getenv(
            "WECHAT_PRIVATE_KEY_PATH", os.path.join(cert_dir, "apiclient_key.pem")
        ),
        cert_serial_no=_clean_cert_serial(os.getenv("WECHAT_CERT_SERIAL_NO")),
        public_key_path=os.getenv("WECHAT_PUBLIC_KEY_PATH"),
        platform_public_key_id=os.getenv("WECHAT_PUBLIC_KEY_ID"),
        notify_url=os.getenv(
            "WECHAT_NOTIFY_URL", "https://www.cbprice.cn/api/payments/notify"
        ),
        return_url=os.getenv(
            "WECHAT_RETURN_URL", "https://www.cbprice.cn/payment/success"
        ),
        sandbox=os.getenv("WECHAT_SANDBOX", "false").lower() == "true",
    )

    config = _finalize_config(config)

    logger.debug("🔧 微信支付配置加载: AppID=%s, 商户号=%s", bool(config.app_id), bool(config.mch_id))
    return config


logger.debug("🔍 开始创建微信支付配置实例...")
wechat_config = get_wechat_pay_config()
logger.debug("✅ 微信支付配置实例创建完成")
