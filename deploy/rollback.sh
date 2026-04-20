#!/bin/bash
# CBPrice 生产回滚脚本 — 恢复到旧 Streamlit 架构
# 在服务器上运行: bash deploy/rollback.sh

set -euo pipefail

PROJECT_DIR="/var/www/ozon-pricing"
NGINX_CONF="/etc/nginx/sites-enabled/cbprice.cn"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()   { echo -e "${GREEN}[ROLLBACK]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

cd "$PROJECT_DIR" || error "无法进入项目目录"

echo "=========================================="
echo "  CBPrice 生产回滚"
echo "=========================================="
echo ""

log "当前 git 状态:"
git log --oneline -3
echo ""

LATEST_BACKUP=$(git tag -l 'pre-deploy-*' --sort=-creatordate | head -1)
if [ -z "$LATEST_BACKUP" ]; then
    error "没有找到 pre-deploy-* 备份标签"
fi

log "回滚目标: $LATEST_BACKUP"
read -p "确认回滚? (y/N) " -r
[[ $REPLY =~ ^[Yy]$ ]] || { log "取消回滚"; exit 0; }

log "===== 停止 FastAPI 服务 ====="
sudo systemctl stop fastapi-app.service 2>/dev/null || true
sudo systemctl disable fastapi-app.service 2>/dev/null || true

log "===== 回滚代码 ====="
git checkout "$LATEST_BACKUP"
log "已回滚到 $LATEST_BACKUP"

log "===== 恢复 nginx 配置 ====="
LATEST_BAK=$(ls -t "${NGINX_CONF}".bak.* 2>/dev/null | head -1)
if [ -n "$LATEST_BAK" ]; then
    sudo cp "$LATEST_BAK" "$NGINX_CONF"
    sudo nginx -t && sudo systemctl reload nginx
    log "nginx 配置已恢复"
else
    warn "未找到 nginx 备份，请手动恢复"
fi

log "===== 重启旧服务 ====="
sudo systemctl enable streamlit-app.service 2>/dev/null || true
sudo systemctl enable pricing-api.service 2>/dev/null || true
sudo systemctl start streamlit-app.service
sleep 3

if systemctl is-active --quiet streamlit-app.service; then
    log "Streamlit 服务已恢复 ✓"
else
    error "Streamlit 恢复失败！请检查: sudo journalctl -u streamlit-app -n 30"
fi

log "===== 健康检查 ====="
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8501/ 2>/dev/null || echo "000")
log "Streamlit 响应: HTTP $HTTP_CODE"

echo ""
echo "=========================================="
log "回滚完成"
echo "=========================================="
echo "  恢复到: $LATEST_BACKUP"
echo "  Streamlit: http://127.0.0.1:8501"
echo "  如需重新部署: bash deploy/deploy.sh"
echo ""
