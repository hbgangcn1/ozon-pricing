#!/bin/bash

echo "修复 systemd 服务配置..."

# 备份原始服务文件
if [ -f /etc/systemd/system/streamlit-app.service ]; then
    echo "备份原始服务文件..."
    sudo cp /etc/systemd/system/streamlit-app.service /etc/systemd/system/streamlit-app.service.backup
fi

# 创建新的服务文件
echo "创建新的服务文件..."
sudo tee /etc/systemd/system/streamlit-app.service > /dev/null << 'EOF'
[Unit]
Description=Streamlit Pricing Application
After=network.target

[Service]
Type=simple
WorkingDirectory=/root/ozon-pricing-private
Environment=PRODUCTION_MODE=true
EnvironmentFile=-/root/ozon-pricing-private/.env
ExecStart=/bin/bash -lc 'source venv/bin/activate && streamlit run app.py --server.port 8501 --server.enableXsrfProtection=true --server.enableCORS=true'
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF

echo "重新加载 systemd 配置..."
sudo systemctl daemon-reload

echo "重启服务..."
sudo systemctl restart streamlit-app.service

echo "检查服务状态..."
sudo systemctl status streamlit-app.service --no-pager

echo "修复完成！"
