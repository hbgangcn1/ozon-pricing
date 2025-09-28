@echo off
REM =================================
REM 生产环境微信支付配置模板
REM 域名: cbprice.cn
REM =================================

REM 启用生产环境模式
set PRODUCTION_MODE=true

REM ==========================================
REM 微信支付配置 - 请替换为您的真实信息
REM ==========================================

REM 微信公众号/小程序 AppID
set WECHAT_APP_ID=wx1234567890abcdef

REM 微信支付商户号
set WECHAT_MCH_ID=1234567890

REM 微信支付API密钥（32位）
set WECHAT_API_KEY=your32characterlongapikeyhere123

REM ==========================================
REM 回调地址配置（已自动配置为您的域名）
REM ==========================================

REM 支付结果通知地址
set WECHAT_NOTIFY_URL=https://www.cbprice.cn/wechat/notify

REM 支付完成跳转地址  
set WECHAT_RETURN_URL=https://www.cbprice.cn/payment/success

REM ==========================================
REM 可选配置
REM ==========================================

REM 商户证书路径（用于退款等需要证书的接口）
REM set WECHAT_CERT_PATH=C:\path\to\apiclient_cert.pem
REM set WECHAT_KEY_PATH=C:\path\to\apiclient_key.pem

REM 是否启用沙箱模式（生产环境应设为false）
set WECHAT_SANDBOX=false

echo ==========================================
echo 微信支付生产环境配置已设置
echo ==========================================
echo 域名: https://www.cbprice.cn
echo 回调地址: %WECHAT_NOTIFY_URL%
echo 返回地址: %WECHAT_RETURN_URL%
echo 沙箱模式: %WECHAT_SANDBOX%
echo ==========================================
echo.
echo 请确保在微信商户平台配置：
echo 1. Native支付回调链接: %WECHAT_NOTIFY_URL%
echo 2. 支付授权目录: https://www.cbprice.cn/
echo 3. 服务器IP白名单
echo ==========================================









