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
    # 如果没有安装python-dotenv，定义一个占位符函数
    def load_dotenv(*args, **kwargs) -> bool:
        # 占位符函数，忽略所有参数
        _ = args, kwargs  # 明确标记参数为未使用
        return False


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
    public_key_path: Optional[str] = None  # 微信支付公钥文件路径

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
    
    # 调试信息：检查环境变量是否被正确加载
    print(f"🔧 环境变量调试信息:")
    print(f"  WECHAT_APP_ID: {'已设置' if config.app_id else '未设置'}")
    print(f"  WECHAT_MCH_ID: {'已设置' if config.mch_id else '未设置'}")
    print(f"  WECHAT_API_V3_KEY: {'已设置' if config.api_v3_key else '未设置'}")
    if config.api_v3_key:
        print(f"  API_V3_KEY长度: {len(config.api_v3_key)}")

    # 证书配置
    config.private_key_path = os.getenv("WECHAT_PRIVATE_KEY_PATH")
    config.public_key_path = os.getenv("WECHAT_PUBLIC_KEY_PATH")
    cert_serial_raw = os.getenv("WECHAT_CERT_SERIAL_NO")

    # 清理证书序列号格式（移除空格、冒号等）
    if cert_serial_raw:
        config.cert_serial_no = (
            cert_serial_raw.replace(":", "")
            .replace(" ", "")
            .replace("-", "")
            .upper()
        )
    else:
        config.cert_serial_no = None

    # 调试信息
    print("🔧 微信支付配置加载:")
    print(f"  AppID: {config.app_id[:10] if config.app_id else 'None'}...")
    print(f"  商户号: {config.mch_id}")
    print(f"  私钥路径: {config.private_key_path}")
    print(f"  公钥路径: {config.public_key_path}")
    print(f"  证书序列号: {config.cert_serial_no}")
    print(f"  API密钥: {'已设置' if config.api_v3_key else '未设置'}")

    # 回调地址
    config.notify_url = os.getenv("WECHAT_NOTIFY_URL",
                                  "https://www.cbprice.cn/wechat/notify")
    config.return_url = os.getenv("WECHAT_RETURN_URL",
                                  "https://www.cbprice.cn/payment/success")

    # 是否使用沙箱环境
    config.sandbox = os.getenv("WECHAT_SANDBOX", "false").lower() == "true"

    return config


# 全局配置实例
print("🔍 开始创建微信支付配置实例...")
wechat_config = get_wechat_pay_config()
print("✅ 微信支付配置实例创建完成")
