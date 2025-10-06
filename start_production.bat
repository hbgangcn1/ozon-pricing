@echo off
echo 启动生产环境 - cbprice.cn
echo.

REM 设置生产环境模式
set PRODUCTION_MODE=true

REM 设置微信支付配置（请替换为您的真实信息）
set WECHAT_APP_ID=your_real_app_id
set WECHAT_MCH_ID=your_real_merchant_id  
set WECHAT_API_KEY=your_real_api_key

REM 可选：证书路径（用于退款等高级功能）
REM set WECHAT_CERT_PATH=path\to\apiclient_cert.pem
REM set WECHAT_KEY_PATH=path\to\apiclient_key.pem

echo 当前配置：
echo - 生产环境模式: %PRODUCTION_MODE%
echo - 域名: https://www.cbprice.cn
echo - 回调地址: https://www.cbprice.cn/wechat/notify
echo - 返回地址: https://www.cbprice.cn/payment/success
echo.

echo 请选择启动方式：
echo 1. 启动主应用 (Streamlit - 端口8501)
echo 2. 启动回调服务器 (Flask - 端口8081)  
echo 3. 同时启动主应用和回调服务器
echo 0. 退出

set /p choice=请输入选择 (0-3): 

if "%choice%"=="1" (
    echo.
    echo 启动主应用...
    echo 访问地址: http://localhost:8501
    echo.
    streamlit run app.py --server.port 8501
) else if "%choice%"=="2" (
    echo.
    echo 启动回调服务器...
    echo 回调地址: http://localhost:8081
    echo.
    python wechat_callback_server.py
) else if "%choice%"=="3" (
    echo.
    echo 同时启动主应用和回调服务器...
    echo 主应用: http://localhost:8501
    echo 回调服务: http://localhost:8081
    echo.
    start "微信支付回调服务" cmd /c "python wechat_callback_server.py"
    timeout /t 2 /nobreak > nul
    start "物流系统主应用" cmd /c "streamlit run app.py --server.port 8501"
    echo.
    echo 两个服务已启动，请查看新打开的窗口
) else if "%choice%"=="0" (
    echo 退出
) else (
    echo 无效选择
)

pause













