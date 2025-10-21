#!/bin/bash
# 支付补偿服务systemd配置脚本
# 用于Linux生产环境

# 检查是否以root权限运行
if [ "$EUID" -ne 0 ]; then 
    echo "请使用sudo运行此脚本"
    exit 1
fi

# 获取项目目录
PROJECT_DIR=$(cd "$(dirname "$0")" && pwd)
PYTHON_PATH=$(which python3)

# 如果存在虚拟环境，使用虚拟环境的python
if [ -d "$PROJECT_DIR/.venv" ]; then
    PYTHON_PATH="$PROJECT_DIR/.venv/bin/python"
fi

# 创建systemd服务文件
cat > /etc/systemd/system/payment-compensation.service << EOF
[Unit]
Description=Payment Compensation Service
After=network.target

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$PROJECT_DIR/.venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=$PYTHON_PATH $PROJECT_DIR/payment_compensation_service.py
Restart=always
RestartSec=10

# 日志配置
StandardOutput=append:$PROJECT_DIR/logs/payment_compensation.log
StandardError=append:$PROJECT_DIR/logs/payment_compensation_error.log

# 安全配置
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

# 创建日志目录
mkdir -p "$PROJECT_DIR/logs"

# 重新加载systemd配置
systemctl daemon-reload

# 启用服务（开机自启）
systemctl enable payment-compensation.service

# 启动服务
systemctl start payment-compensation.service

# 显示服务状态
systemctl status payment-compensation.service

echo ""
echo "========================================="
echo "支付补偿服务已配置完成！"
echo "========================================="
echo ""
echo "常用命令："
echo "  启动服务: sudo systemctl start payment-compensation"
echo "  停止服务: sudo systemctl stop payment-compensation"
echo "  重启服务: sudo systemctl restart payment-compensation"
echo "  查看状态: sudo systemctl status payment-compensation"
echo "  查看日志: sudo journalctl -u payment-compensation -f"
echo "  查看应用日志: tail -f $PROJECT_DIR/logs/payment_compensation.log"
echo ""



