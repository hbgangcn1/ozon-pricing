# -*- coding: utf-8 -*-
"""
生产环境微信支付配置
从环境变量读取真实密钥，避免把敏感信息写进代码仓库
"""

from typing import TYPE_CHECKING
import os

if TYPE_CHECKING:
    from wechat_pay_config import WeChatPayConfig


def require_env(name: str) -> str:
    """
    获取必需的环境变量，如果不存在则抛出异常

    Args:
        name: 环境变量名

    Returns:
        环境变量值

    Raises:
        RuntimeError: 如果环境变量不存在
    """
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"缺少环境变量: {name}")
    return value


def get_production_config() -> "WeChatPayConfig":
    """
    返回微信支付生产配置（WeChatPayConfig 实例）。
    所有值来源于环境变量：

    - WECHAT_APP_ID
    - WECHAT_MCH_ID
    - WECHAT_API_V3_KEY
    - WECHAT_CERT_SERIAL_NO
    - WECHAT_PRIVATE_KEY_PATH
    - WECHAT_PUBLIC_KEY_PATH
    - WECHAT_NOTIFY_URL
    - WECHAT_RETURN_URL
    - WECHAT_SANDBOX（可选）
    """
    from wechat_pay_config import WeChatPayConfig

    cert_serial_raw = require_env("WECHAT_CERT_SERIAL_NO")
    cert_serial_no = (
        cert_serial_raw.replace(":", "")
        .replace(" ", "")
        .replace("-", "")
        .upper()
    )

    return WeChatPayConfig(
        app_id=require_env("WECHAT_APP_ID"),
        mch_id=require_env("WECHAT_MCH_ID"),
        api_v3_key=require_env("WECHAT_API_V3_KEY"),
        private_key_path=require_env("WECHAT_PRIVATE_KEY_PATH"),
        cert_serial_no=cert_serial_no,
        public_key_path=require_env("WECHAT_PUBLIC_KEY_PATH"),
        notify_url=require_env("WECHAT_NOTIFY_URL"),
        return_url=require_env("WECHAT_RETURN_URL"),
        sandbox=os.getenv("WECHAT_SANDBOX", "false").lower() == "true",
    )
