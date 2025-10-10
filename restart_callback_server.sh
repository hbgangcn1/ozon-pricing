#!/bin/bash
# 重启微信支付回调服务器

echo "=========================================="
echo "重启微信支付回调服务器"
echo "=========================================="

echo ""
echo "【1. 停止所有gunicorn进程】"
pkill -9 -f "gunicorn"
sleep 2

echo "【2. 确认进程已停止】"
PROCESSES=$(ps aux | grep gunicorn | grep -v grep | wc -l)
if [ $PROCESSES -eq 0 ]; then
    echo "  ✅ 所有gunicorn进程已停止"
else
    echo "  ⚠️  仍有 $PROCESSES 个进程在运行"
    ps aux | grep gunicorn | grep -v grep
fi

echo ""
echo "【3. 启动新的gunicorn进程】"
cd /root/ozon-pricing-private
nohup gunicorn -w 2 -b 0.0.0.0:8081 wechat_callback_server:app \
    --access-logfile gunicorn_access.log \
    --error-logfile gunicorn_error.log \
    --log-level info \
    > gunicorn_wechat.log 2>&1 &

GUNICORN_PID=$!
echo "  启动PID: $GUNICORN_PID"

sleep 3

echo ""
echo "【4. 检查新进程状态】"
NEW_PROCESSES=$(ps aux | grep gunicorn | grep wechat | grep -v grep | wc -l)
if [ $NEW_PROCESSES -gt 0 ]; then
    echo "  ✅ gunicorn已启动，共 $NEW_PROCESSES 个进程"
    ps aux | grep gunicorn | grep wechat | grep -v grep | head -3
else
    echo "  ❌ gunicorn启动失败"
    echo "  查看错误日志:"
    tail -20 gunicorn_error.log
    exit 1
fi

echo ""
echo "【5. 检查端口监听】"
if netstat -tlnp 2>/dev/null | grep :8081 > /dev/null || ss -tlnp 2>/dev/null | grep :8081 > /dev/null; then
    echo "  ✅ 8081端口正在监听"
else
    echo "  ❌ 8081端口未监听"
    exit 1
fi

echo ""
echo "【6. 查看启动日志】"
tail -15 gunicorn_wechat.log

echo ""
echo "=========================================="
echo "✅ 回调服务器重启完成"
echo "=========================================="

