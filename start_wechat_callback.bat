@echo off
echo 启动微信支付回调服务器...
echo.
echo 确保已经安装所有依赖：
echo pip install -r requirements.txt
echo.
echo 确保已经配置环境变量（参考 wechat_config_example.txt）
echo.
python wechat_callback_server.py
pause













