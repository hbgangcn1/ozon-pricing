#!/bin/bash
# 生产服务器回滚脚本
# 使用方法: bash rollback_production.sh

set -e

echo "=========================================="
echo "生产服务器回滚脚本"
echo "=========================================="

cd /var/www/ozon-pricing

# 1. 查看当前状态
echo "📋 当前状态："
git log --oneline -3

# 2. 拉取最新代码（包含回滚）
echo ""
echo "📥 拉取回滚后的代码..."
git pull origin release/v1

# 3. 重启Streamlit服务
echo ""
echo "🔄 重启Streamlit服务..."
sudo systemctl stop fastapi-app.service 2>/dev/null || true
sudo systemctl start streamlit-app.service

# 4. 验证
echo ""
echo "✅ 验证服务状态..."
sleep 2
sudo systemctl status streamlit-app.service --no-pager

echo ""
echo "=========================================="
echo "✅ 回滚完成！"
echo "=========================================="
