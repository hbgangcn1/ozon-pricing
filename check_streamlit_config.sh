#!/bin/bash
# 检查和修复Streamlit配置

echo "🔍 检查Streamlit配置..."

# 1. 检查配置文件
echo ""
echo "📁 检查.streamlit/config.toml文件:"
if [ -f ".streamlit/config.toml" ]; then
    echo "✅ 配置文件存在"
    echo "📄 fileWatcherType设置:"
    grep -n "fileWatcherType" .streamlit/config.toml || echo "⚠️ 未找到fileWatcherType配置"
else
    echo "❌ 配置文件不存在"
fi

# 2. 检查systemd服务配置
echo ""
echo "📁 检查systemd服务配置:"
if [ -f "/etc/systemd/system/streamlit-app.service" ]; then
    echo "✅ 服务文件存在"
    echo "📄 ExecStart命令:"
    grep "ExecStart" /etc/systemd/system/streamlit-app.service
else
    echo "❌ 服务文件不存在"
fi

# 3. 检查Streamlit进程
echo ""
echo "🔍 检查当前Streamlit进程:"
ps aux | grep streamlit | grep -v grep

echo ""
echo "✅ 检查完成"
echo ""
echo "💡 建议："
echo "1. 如果fileWatcherType设置正确但仍频繁重启，请检查systemd服务的ExecStart命令"
echo "2. 确保命令中包含 --server.fileWatcherType=none"
echo "3. 或者在~/.streamlit/config.toml中也添加此配置"


