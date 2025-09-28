@echo off
echo 设置 cpolar 内网穿透工具（推荐国内用户使用）
echo.
echo cpolar 是一个稳定的内网穿透工具，特别适合国内环境
echo.
echo 安装步骤：
echo 1. 访问 https://www.cpolar.com/ 注册账号
echo 2. 下载客户端并安装
echo 3. 登录账号: cpolar authtoken YOUR_TOKEN
echo 4. 运行此脚本
echo.

set /p choice=是否现在启动 cpolar 穿透到端口 8080? (y/n): 

if /i "%choice%"=="y" (
    echo.
    echo 启动 cpolar 穿透到本地 8080 端口...
    echo 请保持此窗口打开，并记录生成的公网地址
    echo.
    cpolar http 8080
) else (
    echo.
    echo 手动启动命令：
    echo cpolar http 8080
    echo.
    echo 获取到公网地址后，请设置环境变量：
    echo set TUNNEL_DOMAIN=your-domain.cpolar.cn
)

echo.
echo 注意：免费版cpolar每次重启会变更域名
echo 建议升级到付费版获得固定域名
echo.
pause









