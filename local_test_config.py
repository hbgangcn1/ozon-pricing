# -*- coding: utf-8 -*-
"""
本地测试配置
用于在本地环境进行微信支付沙箱测试
"""

import os
from wechat_pay_config import WeChatPayConfig


class LocalTestConfig(WeChatPayConfig):
    """本地测试配置类"""

    def __init__(self):
        super().__init__()

        # 强制启用沙箱模式
        self.sandbox = True

        # 本地测试配置
        self.app_id = "wx_sandbox_app_id"  # 沙箱AppID
        self.mch_id = "1234567890"  # 沙箱商户号
        self.api_key = "sandbox_api_key_32_characters_long"  # 沙箱API密钥

        # 本地回调地址（使用内网穿透工具）
        tunnel_domain = os.getenv("TUNNEL_DOMAIN", "localhost")
        self.notify_url = f"https://{tunnel_domain}:8081/wechat/notify"
        self.return_url = f"https://{tunnel_domain}:8081/payment/success"

        print("🧪 使用本地测试配置（沙箱模式）")
        print(f"📡 回调地址: {self.notify_url}")

    @property
    def api_base_url(self) -> str:
        """沙箱环境API地址"""
        return "https://api.mch.weixin.qq.com/sandboxnew"


def get_local_test_config() -> LocalTestConfig:
    """获取本地测试配置"""
    return LocalTestConfig()


# 本地测试时使用的配置
local_config = get_local_test_config()
