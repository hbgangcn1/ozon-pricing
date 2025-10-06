@echo off
echo 设置 ngrok 内网穿透工具
echo.
echo 如果您还没有安装 ngrok，请先访问 https://ngrok.com/ 下载安装
echo.
echo 使用方法：
echo 1. 注册 ngrok 账号并获取 authtoken
echo 2. 运行: ngrok config add-authtoken YOUR_TOKEN
echo 3. 运行此脚本启动穿透
echo.

set /p choice=是否现在启动 ngrok 穿透到端口 8081? (y/n): 

if /i "%choice%"=="y" (
    echo.
    echo 启动 ngrok 穿透到本地 8081 端口...
    echo 请保持此窗口打开，并记录生成的公网地址
    echo.
    ngrok http 8081
) else (
    echo.
    echo 手动启动命令：
    echo ngrok http 8081
    echo.
    echo 或者使用其他内网穿透工具：
    echo - cpolar: https://www.cpolar.com/
    echo - frp: https://github.com/fatedier/frp
    echo - localtunnel: npm install -g localtunnel
)

pause













