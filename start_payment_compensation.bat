@echo off
REM Windows环境下启动支付补偿服务
REM 使用NSSM (Non-Sucking Service Manager) 将其安装为Windows服务

echo ========================================
echo 支付补偿服务启动脚本
echo ========================================
echo.

REM 激活虚拟环境
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
    echo 虚拟环境已激活
) else (
    echo 警告: 未找到虚拟环境，使用系统Python
)

REM 创建日志目录
if not exist logs mkdir logs

echo.
echo 启动支付补偿服务...
echo 日志文件: logs\payment_compensation.log
echo.
echo 提示: 按 Ctrl+C 停止服务
echo.

REM 启动服务
python payment_compensation_service.py

pause



