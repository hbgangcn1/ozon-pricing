# -*- coding: utf-8 -*-
"""
生产环境微信支付配置
用于 cbprice.cn 域名的真实环境配置
"""

import os
from wechat_pay_config import WeChatPayConfig


class ProductionWeChatConfig(WeChatPayConfig):
    """生产环境微信支付配置"""
    
    def __init__(self):
        super().__init__()
        
        # 生产环境域名配置
        self.domain = "https://www.cbprice.cn"
        
        # 关闭沙箱模式
        self.sandbox = False
        
        # 从环境变量读取真实配置
        self.app_id = os.getenv("WECHAT_APP_ID", "")
        self.mch_id = os.getenv("WECHAT_MCH_ID", "")  
        self.api_key = os.getenv("WECHAT_API_KEY", "")
        
        # 生产环境回调地址
        self.notify_url = f"{self.domain}/wechat/notify"
        self.return_url = f"{self.domain}/payment/success"
        
        # 证书路径（生产环境推荐使用）
        self.cert_path = os.getenv("WECHAT_CERT_PATH")
        self.key_path = os.getenv("WECHAT_KEY_PATH")
        
        print(f"🌐 使用生产环境配置")
        print(f"📡 域名: {self.domain}")
        print(f"🔔 回调地址: {self.notify_url}")
        print(f"🏠 返回地址: {self.return_url}")
    
    @property
    def api_base_url(self) -> str:
        """生产环境API地址"""
        return "https://api.mch.weixin.qq.com"


def get_production_config() -> ProductionWeChatConfig:
    """获取生产环境配置"""
    return ProductionWeChatConfig()


# 生产环境配置实例
production_config = get_production_config()









