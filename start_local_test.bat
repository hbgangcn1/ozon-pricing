@echo off
echo 启动微信支付本地测试环境
echo.

REM 设置本地测试模式
set LOCAL_TEST_MODE=true
set TUNNEL_DOMAIN=localhost

echo 当前配置：
echo - 本地测试模式: %LOCAL_TEST_MODE%
echo - 隧道域名: %TUNNEL_DOMAIN%
echo.

echo 请选择启动方式：
echo 1. 启动主应用 (Streamlit)
echo 2. 启动回调服务器 (Flask)
echo 3. 运行微信支付测试工具
echo 4. 同时启动主应用和回调服务器
echo 0. 退出

set /p choice=请输入选择 (0-4): 

if "%choice%"=="1" (
    echo.
    echo 启动主应用...
    echo 访问地址: http://localhost:8501
    echo.
    streamlit run app.py --server.port 8501
) else if "%choice%"=="2" (
    echo.
    echo 启动回调服务器...
    echo 回调地址: http://localhost:8080
    echo.
    python wechat_callback_server.py
) else if "%choice%"=="3" (
    echo.
    echo 启动微信支付测试工具...
    echo.
    python local_wechat_test.py
) else if "%choice%"=="4" (
    echo.
    echo 同时启动主应用和回调服务器...
    echo 主应用: http://localhost:8501
    echo 回调服务: http://localhost:8080
    echo.
    start "回调服务器" cmd /c "python wechat_callback_server.py"
    timeout /t 2 /nobreak > nul
    start "主应用" cmd /c "streamlit run app.py --server.port 8501"
    echo.
    echo 两个服务已启动，请查看新打开的窗口
) else if "%choice%"=="0" (
    echo 退出
) else (
    echo 无效选择
)

pause













