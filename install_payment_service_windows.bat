@echo off
REM Windows服务安装脚本
REM 需要下载NSSM: https://nssm.cc/download

echo ========================================
echo 安装支付补偿服务为Windows服务
echo ========================================
echo.

REM 检查NSSM是否存在
where nssm >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo 错误: 未找到NSSM
    echo 请从 https://nssm.cc/download 下载NSSM
    echo 并将nssm.exe放到PATH路径中或当前目录
    pause
    exit /b 1
)

REM 获取当前目录
set PROJECT_DIR=%cd%

REM 获取Python路径
if exist .venv\Scripts\python.exe (
    set PYTHON_PATH=%PROJECT_DIR%\.venv\Scripts\python.exe
) else (
    for /f "tokens=*" %%i in ('where python') do set PYTHON_PATH=%%i
)

echo Python路径: %PYTHON_PATH%
echo 项目路径: %PROJECT_DIR%
echo.

REM 安装服务
echo 安装服务中...
nssm install PaymentCompensation "%PYTHON_PATH%" "%PROJECT_DIR%\payment_compensation_service.py"

REM 配置服务
nssm set PaymentCompensation AppDirectory "%PROJECT_DIR%"
nssm set PaymentCompensation DisplayName "Payment Compensation Service"
nssm set PaymentCompensation Description "支付回调补偿服务，定期检查并处理未完成的支付订单"
nssm set PaymentCompensation Start SERVICE_AUTO_START

REM 配置日志
if not exist logs mkdir logs
nssm set PaymentCompensation AppStdout "%PROJECT_DIR%\logs\payment_compensation.log"
nssm set PaymentCompensation AppStderr "%PROJECT_DIR%\logs\payment_compensation_error.log"

REM 配置重启策略
nssm set PaymentCompensation AppExit Default Restart
nssm set PaymentCompensation AppRestartDelay 10000

echo.
echo ========================================
echo 服务安装成功！
echo ========================================
echo.
echo 常用命令:
echo   启动服务: nssm start PaymentCompensation
echo   停止服务: nssm stop PaymentCompensation
echo   重启服务: nssm restart PaymentCompensation
echo   查看状态: nssm status PaymentCompensation
echo   卸载服务: nssm remove PaymentCompensation confirm
echo.
echo 或使用Windows服务管理器 (services.msc)
echo.

REM 询问是否立即启动
set /p START_NOW="是否立即启动服务? (Y/N): "
if /i "%START_NOW%"=="Y" (
    echo 启动服务中...
    nssm start PaymentCompensation
    echo 服务已启动！
)

pause



