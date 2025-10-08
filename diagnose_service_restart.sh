#!/bin/bash
# 诊断Streamlit服务频繁重启的原因

echo "🔍 诊断Streamlit服务重启问题"
echo "================================"
echo ""

# 1. 检查服务状态
echo "1️⃣ 检查服务当前状态:"
systemctl status streamlit-app.service --no-pager | head -20
echo ""

# 2. 检查最近的重启记录
echo "2️⃣ 最近10次服务重启记录:"
journalctl -u streamlit-app.service --since "1 hour ago" | grep -E "Started|Stopped|Stopping" | tail -20
echo ""

# 3. 检查文件监控配置
echo "3️⃣ 检查Streamlit文件监控配置:"
echo "📁 .streamlit/config.toml:"
if [ -f ".streamlit/config.toml" ]; then
    grep -A2 -B2 "fileWatcher" .streamlit/config.toml || echo "未找到fileWatcher配置"
else
    echo "❌ 配置文件不存在"
fi
echo ""

# 4. 检查systemd服务配置
echo "4️⃣ systemd服务配置:"
if [ -f "/etc/systemd/system/streamlit-app.service" ]; then
    echo "ExecStart命令:"
    grep "ExecStart" /etc/systemd/system/streamlit-app.service
    echo ""
    echo "Restart策略:"
    grep -E "Restart|RestartSec" /etc/systemd/system/streamlit-app.service || echo "未设置"
else
    echo "❌ 服务文件不存在"
fi
echo ""

# 5. 检查是否有监控脚本
echo "5️⃣ 检查是否有自动重启的cron任务或监控脚本:"
crontab -l 2>/dev/null | grep -i streamlit || echo "未找到cron任务"
echo ""

# 6. 检查文件变化监控
echo "6️⃣ 使用inotify监控文件变化（10秒）:"
echo "提示：如果看到大量文件变化，说明有程序在修改代码文件"
timeout 10 inotifywait -m -r -e modify,create,delete,move . 2>/dev/null | head -20 || echo "inotify-tools未安装"
echo ""

# 7. 检查进程
echo "7️⃣ Streamlit进程信息:"
ps aux | grep streamlit | grep -v grep
echo ""

# 8. 检查内存和CPU
echo "8️⃣ 系统资源:"
free -h
echo ""
top -b -n 1 | head -10
echo ""

echo "================================"
echo "✅ 诊断完成"
echo ""
echo "💡 常见原因："
echo "1. fileWatcherType未正确设置为none"
echo "2. 代码文件被频繁修改（如rsync同步）"
echo "3. Restart策略设置为always"
echo "4. 内存不足导致OOM被杀"
echo "5. 有外部监控脚本定期重启服务"

