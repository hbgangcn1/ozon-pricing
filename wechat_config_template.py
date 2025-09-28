# -*- coding: utf-8 -*-
"""
微信支付配置模板
请复制此文件为production_wechat_config.py或local_test_config.py
并根据实际情况填写配置信息
"""

from wechat_pay_config import WeChatPayConfig


def get_production_config() -> WeChatPayConfig:
    """
    生产环境微信支付配置
    
    请填写以下信息：
    1. 在微信支付商户平台获取商户号（mch_id）
    2. 在微信公众平台或小程序平台获取AppID
    3. 在微信支付商户平台设置API v3密钥
    4. 下载商户证书并配置证书路径
    """
    config = WeChatPayConfig()
    
    # 基础配置 - 请填写您的实际信息
    config.app_id = "YOUR_APP_ID"  # 微信公众号或小程序AppID
    config.mch_id = "YOUR_MCH_ID"  # 商户号
    config.api_v3_key = "YOUR_API_V3_KEY"  # API v3密钥（32位字符串）
    
    # 证书配置 - 请填写证书文件路径
    config.private_key_path = "path/to/your/private_key.pem"  # 商户私钥文件路径
    config.cert_serial_no = "YOUR_CERT_SERIAL_NO"  # 商户证书序列号
    
    # 回调配置 - 请填写您的域名
    config.notify_url = "https://your-domain.com/wechat/notify"  # 支付结果通知地址
    config.return_url = "https://your-domain.com/payment/success"  # 支付完成跳转地址
    
    # 环境配置
    config.sandbox = False  # 生产环境请设置为False
    
    return config


def get_local_test_config() -> WeChatPayConfig:
    """
    本地测试环境微信支付配置
    
    注意：本地测试需要配置内网穿透工具（如ngrok或cpolar）
    将本地回调地址映射到公网地址
    """
    config = WeChatPayConfig()
    
    # 基础配置 - 请填写您的测试信息
    config.app_id = "YOUR_TEST_APP_ID"  # 测试公众号或小程序AppID
    config.mch_id = "YOUR_TEST_MCH_ID"  # 测试商户号
    config.api_v3_key = "YOUR_TEST_API_V3_KEY"  # 测试API v3密钥
    
    # 证书配置
    config.private_key_path = "path/to/your/test_private_key.pem"
    config.cert_serial_no = "YOUR_TEST_CERT_SERIAL_NO"
    
    # 回调配置 - 使用内网穿透地址
    # 例如：https://abc123.ngrok.io 或 https://abc123.cpolar.cn
    config.notify_url = "https://your-ngrok-domain.ngrok.io/wechat/notify"
    config.return_url = "https://your-ngrok-domain.ngrok.io/payment/success"
    
    # 环境配置
    config.sandbox = True  # 测试环境建议使用沙箱
    
    return config


# 配置说明
"""
微信支付配置步骤：

1. 注册微信支付商户号
   - 访问 https://pay.weixin.qq.com
   - 申请商户号并完成资质审核
   - 获取商户号（mch_id）

2. 获取AppID
   - 公众号：微信公众平台 https://mp.weixin.qq.com
   - 小程序：微信小程序平台 https://mp.weixin.qq.com
   - 获取AppID

3. 配置API密钥
   - 登录微信支付商户平台
   - 进入【账户中心】->【API安全】
   - 设置API v3密钥（32位字符串）

4. 下载商户证书
   - 在【API安全】页面下载商户证书
   - 获取证书序列号
   - 保存私钥文件

5. 配置回调地址
   - 在【开发配置】中设置支付回调地址
   - 确保域名已备案且支持HTTPS

6. 测试环境配置
   - 使用沙箱环境进行测试
   - 配置内网穿透工具映射本地地址
   - 测试支付流程

注意事项：
- 生产环境必须使用HTTPS
- 证书文件路径使用绝对路径
- API v3密钥必须为32位字符串
- 回调地址必须是公网可访问的HTTPS地址
"""
