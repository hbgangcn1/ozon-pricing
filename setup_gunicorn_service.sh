#!/bin/bash
# 设置 gunicorn 为 systemd 服务

echo "=========================================="
echo "设置 Gunicorn 微信回调服务"
echo "=========================================="

# 创建 systemd 服务文件
cat > /tmp/gunicorn-wechat-callback.service << 'EOF'
[Unit]
Description=Gunicorn Wechat Payment Callback Server
After=network.target

[Service]
Type=notify
User=root
WorkingDirectory=/root/ozon-pricing-private
Environment="PATH=/root/ozon-pricing-private/venv/bin"
ExecStart=/root/ozon-pricing-private/venv/bin/gunicorn \
    -w 2 \
    -b 0.0.0.0:8081 \
    --access-logfile /var/log/gunicorn-wechat-access.log \
    --error-logfile /var/log/gunicorn-wechat-error.log \
    --log-level info \
    --timeout 120 \
    wechat_callback_server:app
    
ExecReload=/bin/kill -s HUP $MAINPID
KillMode=mixed
TimeoutStopSec=5
PrivateTmp=true

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 安装服务文件
sudo cp /tmp/gunicorn-wechat-callback.service /etc/systemd/system/

# 重新加载 systemd
sudo systemctl daemon-reload

# 停止旧的手动启动的进程
echo "停止旧的gunicorn进程..."
pkill -9 -f "gunicorn.*wechat_callback"
sleep 2

# 启用并启动服务
echo "启用并启动服务..."
sudo systemctl enable gunicorn-wechat-callback.service
sudo systemctl start gunicorn-wechat-callback.service

# 检查状态
echo ""
echo "=========================================="
echo "服务状态检查"
echo "=========================================="
sudo systemctl status gunicorn-wechat-callback.service --no-pager

echo ""
echo "=========================================="
echo "✅ 设置完成！"
echo "=========================================="
echo ""
echo "常用命令："
echo "  启动: sudo systemctl start gunicorn-wechat-callback"
echo "  停止: sudo systemctl stop gunicorn-wechat-callback"
echo "  重启: sudo systemctl restart gunicorn-wechat-callback"
echo "  状态: sudo systemctl status gunicorn-wechat-callback"
echo "  日志: sudo journalctl -u gunicorn-wechat-callback -f"
echo ""
echo "代码更新后的重启流程："
echo "  cd /root/ozon-pricing-private"
echo "  git pull private release/v1"
echo "  sudo systemctl restart gunicorn-wechat-callback"
echo "  sudo systemctl restart streamlit-app"
echo ""

