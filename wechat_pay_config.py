# -*- coding: utf-8 -*-
"""
微信支付配置模块
包含微信支付所需的配置信息和基础设置
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class WeChatPayConfig:
    """微信支付配置类"""
    
    # 基础配置
    app_id: str = ""  # 微信公众号或小程序AppID
    mch_id: str = ""  # 商户号
    api_key: str = ""  # API密钥
    
    # 证书配置
    cert_path: Optional[str] = None  # 商户证书路径
    key_path: Optional[str] = None   # 商户私钥路径
    
    # 回调配置
    notify_url: str = ""  # 支付结果通知地址
    return_url: str = ""  # 支付完成跳转地址
    
    # 环境配置
    sandbox: bool = False  # 是否使用沙箱环境
    
    # API地址
    @property
    def api_base_url(self) -> str:
        """获取API基础地址"""
        if self.sandbox:
            return "https://api.mch.weixin.qq.com/sandboxnew"
        return "https://api.mch.weixin.qq.com"
    
    @property
    def unified_order_url(self) -> str:
        """统一下单接口地址"""
        return f"{self.api_base_url}/pay/unifiedorder"
    
    @property
    def order_query_url(self) -> str:
        """查询订单接口地址"""
        return f"{self.api_base_url}/pay/orderquery"
    
    @property
    def refund_url(self) -> str:
        """申请退款接口地址"""
        return f"{self.api_base_url}/secapi/pay/refund"


def get_wechat_pay_config() -> WeChatPayConfig:
    """
    从环境变量或配置文件获取微信支付配置
    
    Returns:
        WeChatPayConfig: 微信支付配置对象
    """
    # 检查是否为生产环境
    if os.getenv("PRODUCTION_MODE", "false").lower() == "true":
        from production_wechat_config import get_production_config
        return get_production_config()
    
    # 检查是否为本地测试模式
    if os.getenv("LOCAL_TEST_MODE", "false").lower() == "true":
        from local_test_config import get_local_test_config
        return get_local_test_config()
    
    # 默认配置
    config = WeChatPayConfig()
    
    # 从环境变量读取配置
    config.app_id = os.getenv("WECHAT_APP_ID", "")
    config.mch_id = os.getenv("WECHAT_MCH_ID", "")
    config.api_key = os.getenv("WECHAT_API_KEY", "")
    
    # 证书路径
    config.cert_path = os.getenv("WECHAT_CERT_PATH")
    config.key_path = os.getenv("WECHAT_KEY_PATH")
    
    # 回调地址
    config.notify_url = os.getenv("WECHAT_NOTIFY_URL", 
                                  "https://www.cbprice.cn/wechat/notify")
    config.return_url = os.getenv("WECHAT_RETURN_URL", 
                                  "https://www.cbprice.cn/payment/success")
    
    # 是否使用沙箱环境
    config.sandbox = os.getenv("WECHAT_SANDBOX", "false").lower() == "true"
    
    return config


# 全局配置实例
wechat_config = get_wechat_pay_config()
