#!/bin/bash

echo "彻底修复 Streamlit 配置问题..."

# 查找所有可能的配置文件位置
echo "查找所有 Streamlit 配置文件..."
find /root -name "config.toml" -path "*streamlit*" 2>/dev/null
find /home -name "config.toml" -path "*streamlit*" 2>/dev/null
find /etc -name "config.toml" -path "*streamlit*" 2>/dev/null

echo "删除所有可能冲突的配置文件..."
# 删除所有可能的配置文件
rm -f ~/.streamlit/config.toml
rm -f /root/.streamlit/config.toml
rm -f /home/root/.streamlit/config.toml
rm -f /etc/streamlit/config.toml
rm -f /root/ozon-pricing-private/.streamlit/config.toml
rm -f /root/ozon-pricing-private/streamlit_config.toml

echo "检查 systemd 服务文件中的启动命令..."
# 检查 systemd 服务文件
if [ -f /etc/systemd/system/streamlit-app.service ]; then
    echo "当前 systemd 服务配置："
    cat /etc/systemd/system/streamlit-app.service
    echo ""
    echo "建议修改 ExecStart 为："
    echo "ExecStart=/bin/bash -lc 'source venv/bin/activate && streamlit run app.py --server.port 8501 --server.enableXsrfProtection=true --server.enableCORS=true'"
fi

echo "创建正确的配置文件..."
mkdir -p ~/.streamlit
cat > ~/.streamlit/config.toml << 'EOF'
[server]
enableXsrfProtection = true
enableCORS = true
port = 8501
maxUploadSize = 200

[browser]
gatherUsageStats = false
EOF

echo "配置文件已创建：~/.streamlit/config.toml"
echo "内容："
cat ~/.streamlit/config.toml

echo ""
echo "如果问题仍然存在，请手动修改 systemd 服务文件："
echo "sudo nano /etc/systemd/system/streamlit-app.service"
echo ""
echo "将 ExecStart 行修改为："
echo "ExecStart=/bin/bash -lc 'source venv/bin/activate && streamlit run app.py --server.port 8501 --server.enableXsrfProtection=true --server.enableCORS=true'"
echo ""
echo "然后运行："
echo "sudo systemctl daemon-reload"
echo "sudo systemctl restart streamlit-app.service"
