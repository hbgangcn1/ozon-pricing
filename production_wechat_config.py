# -*- coding: utf-8 -*-
"""
生产环境微信支付配置
用于 cbprice.cn 域名的真实环境配置

⚠️ 安全提醒：
- 此文件不包含敏感信息
- 所有敏感配置通过环境变量读取
- 请在生产服务器上设置相应的环境变量
"""

import os
from dotenv import load_dotenv
from wechat_pay_config import WeChatPayConfig
load_dotenv(override=True)


class ProductionWeChatConfig(WeChatPayConfig):
    """生产环境微信支付配置"""

    def __init__(self):
        super().__init__()

        self.domain = "https://www.cbprice.cn"
        self.sandbox = False

        self.app_id = os.getenv("WECHAT_APP_ID", "")
        self.mch_id = os.getenv("WECHAT_MCH_ID", "")
        self.api_v3_key = os.getenv("WECHAT_API_V3_KEY", "")
        self.platform_public_key_id = os.getenv("WECHAT_PUBLIC_KEY_ID", "")

        self.private_key_path = os.getenv("WECHAT_PRIVATE_KEY_PATH")
        self.public_key_path = os.getenv("WECHAT_PUBLIC_KEY_PATH")
        self.cert_serial_no = os.getenv("WECHAT_CERT_SERIAL_NO")

        self.notify_url = f"{self.domain}/api/payments/notify"
        self.return_url = f"{self.domain}/payment/success"

        self._validate_config()

        print("🌐 使用生产环境配置")
        print(f"📡 域名: {self.domain}")
        print(f"🔔 回调地址: {self.notify_url}")
        print(f"🏠 返回地址: {self.return_url}")

    def _validate_config(self):
        """验证配置完整性"""
        required_configs = [
            ("WECHAT_APP_ID", self.app_id),
            ("WECHAT_MCH_ID", self.mch_id),
            ("WECHAT_API_V3_KEY", self.api_v3_key),
            ("WECHAT_PRIVATE_KEY_PATH", self.private_key_path),
            ("WECHAT_PUBLIC_KEY_PATH", self.public_key_path),
            ("WECHAT_CERT_SERIAL_NO", self.cert_serial_no),
            ("WECHAT_PUBLIC_KEY_ID", self.platform_public_key_id),
        ]

        missing_configs = []
        for env_name, value in required_configs:
            if not value:
                missing_configs.append(env_name)

        if missing_configs:
            print(f"⚠️ 警告: 以下环境变量未设置: {', '.join(missing_configs)}")
            print("请在生产服务器上设置这些环境变量")

    @property
    def api_base_url(self) -> str:
        """生产环境API地址"""
        return "https://api.mch.weixin.qq.com"


def get_production_config() -> ProductionWeChatConfig:
    """获取生产环境配置"""
    return ProductionWeChatConfig()