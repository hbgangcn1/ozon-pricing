# -*- coding: utf-8 -*-
"""
微信支付配置模块
包含微信支付v3 API所需的配置信息和基础设置
"""

import os
from dataclasses import dataclass
from typing import Optional

# 尝试加载.env文件
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # 如果没有安装python-dotenv，忽略
    pass


@dataclass
class WeChatPayConfig:
    """微信支付v3配置类"""

    # 基础配置
    app_id: str = ""  # 微信公众号或小程序AppID
    mch_id: str = ""  # 商户号
    api_v3_key: str = ""  # API v3密钥（32位字符串）

    # 证书配置
    private_key_path: Optional[str] = None  # 商户私钥文件路径
    cert_serial_no: Optional[str] = None    # 商户证书序列号

    # 回调配置
    notify_url: str = ""  # 支付结果通知地址
    return_url: str = ""  # 支付完成跳转地址

    # 环境配置
    sandbox: bool = False  # 是否使用沙箱环境

    # v3 API地址
    @property
    def api_base_url(self) -> str:
        """获取API基础地址"""
        if self.sandbox:
            return "https://api.mch.weixin.qq.com"
        return "https://api.mch.weixin.qq.com"

    @property
    def unified_order_url(self) -> str:
        """统一下单接口地址（v3）"""
        return f"{self.api_base_url}/v3/pay/transactions"

    @property
    def jsapi_pay_url(self) -> str:
        """JSAPI支付接口地址"""
        return f"{self.api_base_url}/v3/pay/transactions/jsapi"

    @property
    def native_pay_url(self) -> str:
        """Native支付接口地址"""
        return f"{self.api_base_url}/v3/pay/transactions/native"

    @property
    def h5_pay_url(self) -> str:
        """H5支付接口地址"""
        return f"{self.api_base_url}/v3/pay/transactions/h5"

    @property
    def order_query_url(self) -> str:
        """查询订单接口地址"""
        return f"{self.api_base_url}/v3/pay/transactions/out-trade-no"

    @property
    def refund_url(self) -> str:
        """申请退款接口地址"""
        return f"{self.api_base_url}/v3/refund/domestic/refunds"


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
    config.api_v3_key = os.getenv("WECHAT_API_V3_KEY", "")

    # 证书配置
    config.private_key_path = os.getenv("WECHAT_PRIVATE_KEY_PATH")
    config.cert_serial_no = os.getenv("WECHAT_CERT_SERIAL_NO")

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
