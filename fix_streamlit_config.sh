#!/bin/bash

echo "修复 Streamlit 配置问题..."

# 方法1：删除可能冲突的配置文件
echo "清理可能冲突的配置文件..."
rm -f ~/.streamlit/config.toml
rm -f /root/.streamlit/config.toml

# 方法2：创建正确的配置文件
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

echo "现在重启服务..."
sudo systemctl restart streamlit-app.service

echo "修复完成！"
