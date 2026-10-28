#!/bin/bash
# ==========================================================
# 物流定价系统 生产部署脚本（11 步，可复用）
# 在服务器上运行: bash deploy/deploy.sh
#
# 说明：原实例 cbprice.cn 已停止运营；本脚本连同 deploy/ 下其它文件作为**通用部署脚手架**保留。
#       所有路径/域名都能用环境变量覆盖，默认值只是原作者实例的值，例如：
#         PROJECT_DIR=/srv/myapp SITE_URL=https://example.com NGINX_CONF=/etc/nginx/sites-enabled/myapp.conf \
#           bash deploy/deploy.sh
#       完整自部署说明见 deploy/README.md。
#
# 前置条件:
#   1. 本地已构建前端: cd frontend && npm run build
#   2. 已将 frontend/dist/ 上传到服务器（或在服务器上构建）:
#      scp -r frontend/dist/ <user>@<host>:/var/www/<your-app>/frontend/dist/
#   3. .env 已配置好所有必需的环境变量
# ==========================================================

set -euo pipefail

# ===== 配置 =====
# 以下全部可用环境变量覆盖（换机器/换域名不用改脚本），默认值=原作者实例
PROJECT_DIR="${PROJECT_DIR:-/var/www/ozon-pricing-private}"
VENV="$PROJECT_DIR/venv"
LOG_DIR="${LOG_DIR:-/var/log/cbprice}"
NGINX_CONF="${NGINX_CONF:-/etc/nginx/sites-enabled/cbprice.cn}"
# nginx 备份目录: /etc/nginx/sites-enabled/ 之外, 否则 nginx 会把 .bak.* 当作活跃站点配置
# 加载,导致 limit_req_zone 重复定义 emergency 错误 (历史教训 2026-05-13)
NGINX_BACKUP_DIR="${NGINX_BACKUP_DIR:-/var/backups/cbprice-nginx}"
# 站点地址（第 11 步 HTTPS 健康检查用）
SITE_URL="${SITE_URL:-https://www.cbprice.cn}"
# nginx 备份文件名前缀：派生自实际配置文件名，换域名无需改这里
NGINX_BAK_PREFIX="$(basename "$NGINX_CONF").bak"
BACKUP_TAG="pre-deploy-$(date +%Y%m%d-%H%M%S)"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()   { echo -e "${GREEN}[DEPLOY]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

cd "$PROJECT_DIR" || error "无法进入项目目录 $PROJECT_DIR"

# ===== 1. 预检 =====
log "===== 第1步: 预检 ====="

# 部署前环境变量强校验：fail-fast，避免缺失密钥/错误 DB URL 进入迁移或启动阶段。
python3 scripts/validate_env.py || exit 1

# 检查是否为 ozon 用户
[ "$(whoami)" = "ozon" ] || error "请以 ozon 用户运行此脚本"

# 检查 .env 必需变量
source "$PROJECT_DIR/.env" 2>/dev/null || true
[ -n "${JWT_SECRET_KEY:-}" ]      || error ".env 缺少 JWT_SECRET_KEY"
[ -n "${POSTGRES_PASSWORD:-}" ]   || error ".env 缺少 POSTGRES_PASSWORD"
[ -n "${SESSION_SECRET:-}" ]      || warn ".env 缺少 SESSION_SECRET（CSRF 保护将使用默认值）"
[ -n "${ALLOWED_ORIGINS:-}" ]     || warn ".env 缺少 ALLOWED_ORIGINS（CORS 将限制为 localhost）"

# 检查磁盘空间 (至少 2GB)
AVAIL_KB=$(df -k "$PROJECT_DIR" | tail -1 | awk '{print $4}')
[ "$AVAIL_KB" -gt 2097152 ] || error "磁盘空间不足（需要 2GB+，当前 $((AVAIL_KB/1024))MB）"

# 检查 PostgreSQL
pg_isready -q || error "PostgreSQL 未运行"

log "预检通过 ✓"

# ===== 2. 备份当前状态 =====
log "===== 第2步: 备份当前状态 ====="
git tag "$BACKUP_TAG" 2>/dev/null || warn "创建 git tag 失败（可能已存在）"
log "已创建备份标签: $BACKUP_TAG"

# 备份当前 nginx 配置
if [ -f "$NGINX_CONF" ]; then
    sudo mkdir -p "$NGINX_BACKUP_DIR"
    sudo cp "$NGINX_CONF" "$NGINX_BACKUP_DIR/$NGINX_BAK_PREFIX.$(date +%Y%m%d-%H%M%S)"
    log "已备份 nginx 配置到 $NGINX_BACKUP_DIR"
fi

# ===== 3. 拉取最新代码 =====
log "===== 第3步: 拉取代码 ====="
git fetch origin main
git checkout main
git pull origin main
log "代码更新完成"

# ===== 4. 安装 Python 依赖 =====
log "===== 第4步: 安装 Python 依赖 ====="
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet -r requirements.txt
log "Python 依赖安装完成"

# ===== 4.1 执行数据库迁移 =====
log "===== 第4.1步: 执行数据库迁移 ====="
"$VENV/bin/python" -m alembic upgrade head
log "数据库迁移完成"

# ===== 4.2 数据库 schema 完整性校验 =====
# 防止 stamp-but-not-applied drift（例如从 dump 恢复后 alembic stamp head
# 但部分迁移 DDL 实际未执行）。alembic check 受历史 SQLite→PG 类型
# 残留影响暂不可用，先用 check_schema_integrity.py 守关键 CHECK 约束。
log "===== 第4.2步: schema 完整性校验 ====="
"$VENV/bin/python" "$PROJECT_DIR/scripts/check_schema_integrity.py" || error "schema 完整性校验失败：关键 CHECK 约束缺失，部署中止"
log "schema 完整性校验通过 ✓"

# ===== 5. 检查前端构建产物 =====
log "===== 第5步: 检查前端 ====="
if [ -f "$PROJECT_DIR/frontend/dist/index.html" ]; then
    log "前端构建产物已就位 ✓"
else
    error "frontend/dist/index.html missing; build frontend and upload dist before deploy"
fi

# 修复 scp 上传后可能继承自 Windows 的 700 目录权限,确保 nginx (www-data) 可读
# 历史教训: scp -r 从 Windows 上传后 dist/assets/ 经常变成 drwx------,导致 nginx 404 全站白屏
log "修复前端静态资源权限 (dir 755 / file 644) ..."
find "$PROJECT_DIR/frontend/dist" -type d -exec chmod 755 {} \;
find "$PROJECT_DIR/frontend/dist" -type f -exec chmod 644 {} \;
log "前端静态资源权限就绪 ✓"

# ===== 6. 创建日志目录 =====
log "===== 第6步: 创建日志目录 ====="
sudo mkdir -p "$LOG_DIR"
sudo chown ozon:ozon "$LOG_DIR"
log "日志目录 $LOG_DIR 就绪"

# ===== 7. 停止旧服务 =====
log "===== 第7步: 停止旧服务 ====="

# 停止旧的 Streamlit + pricing-api
if systemctl is-active --quiet streamlit-app.service 2>/dev/null; then
    sudo systemctl stop streamlit-app.service
    log "已停止 streamlit-app"
fi
if systemctl is-active --quiet pricing-api.service 2>/dev/null; then
    sudo systemctl stop pricing-api.service
    log "已停止 pricing-api"
fi

# 禁用旧服务（防止重启后自动启动）
sudo systemctl disable streamlit-app.service 2>/dev/null || true
sudo systemctl disable pricing-api.service 2>/dev/null || true
log "旧服务已禁用"

# 杀掉占用 8003 端口的孤儿 gunicorn（非 systemd 管理的历史进程）
# 否则第 10 步 fastapi-app.service 会因 "Connection in use" 反复 restart 失败
if command -v fuser >/dev/null 2>&1; then
    fuser -k -TERM 8003/tcp 2>/dev/null || true
    sleep 2
    fuser -k -KILL 8003/tcp 2>/dev/null || true
fi
log "端口 8003 已释放"

# 停止 fastapi-app（如果已存在）
if systemctl is-active --quiet fastapi-app.service 2>/dev/null; then
    sudo systemctl stop fastapi-app.service
    log "已停止旧的 fastapi-app"
fi

# ===== 8. 安装新服务 =====
log "===== 第8步: 安装 systemd 服务 ====="
sudo cp "$PROJECT_DIR/deploy/fastapi-app.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable fastapi-app.service
log "systemd 服务安装完成"

# ===== 9. 安装 nginx 配置 =====
log "===== 第9步: 安装 nginx 配置 ====="
sudo cp "$PROJECT_DIR/deploy/nginx-cbprice.conf" "$NGINX_CONF"

# 验证 nginx 配置
if sudo nginx -t 2>&1; then
    sudo systemctl reload nginx
    log "nginx 配置更新并重载完成"
else
    # nginx 配置有误，恢复备份
    warn "nginx 配置验证失败！恢复旧配置..."
    LATEST_BAK=$(ls -t "$NGINX_BACKUP_DIR/$NGINX_BAK_PREFIX".* 2>/dev/null | head -1)
    if [ -n "$LATEST_BAK" ]; then
        sudo cp "$LATEST_BAK" "$NGINX_CONF"
        sudo systemctl reload nginx
    fi
    error "nginx 配置有误，已恢复旧配置。请检查 deploy/nginx-cbprice.conf"
fi

# ===== 10. 启动新服务 =====
log "===== 第10步: 启动 FastAPI 服务 ====="
sudo systemctl start fastapi-app.service
sleep 3

# 检查服务状态
if systemctl is-active --quiet fastapi-app.service; then
    log "FastAPI 服务启动成功 ✓"
else
    error "FastAPI 服务启动失败！查看日志: sudo journalctl -u fastapi-app -n 50"
fi

# ===== 11. 健康检查 =====
log "===== 第11步: 健康检查 ====="

# 检查后端 API
RETRY=0
MAX_RETRY=10
while [ $RETRY -lt $MAX_RETRY ]; do
    HTTP_CODE=$(curl --max-time 10 -fsS -o /dev/null -w "%{http_code}" http://127.0.0.1:8003/health 2>/dev/null || echo "000")
    if [ "$HTTP_CODE" = "200" ]; then
        log "后端健康端点响应正常 (HTTP $HTTP_CODE) ✓"
        break
    fi
    RETRY=$((RETRY + 1))
    warn "后端未就绪 (HTTP $HTTP_CODE)，等待 5 秒... ($RETRY/$MAX_RETRY)"
    sleep 5
done

if [ $RETRY -eq $MAX_RETRY ]; then
    warn "后端健康检查失败，输出 /var/log/cbprice/error.log 最后 50 行："
    tail -50 /var/log/cbprice/error.log 2>/dev/null || true
    error "后端健康检查失败！建议运行: bash deploy/rollback.sh"
fi

if systemctl is-active --quiet fastapi-app.service; then
    log "fastapi-app systemd 状态二次确认 active ✓"
else
    warn "健康端点通过后 fastapi-app 已非 active，输出错误日志最后 50 行："
    tail -50 /var/log/cbprice/error.log 2>/dev/null || true
    error "fastapi-app systemd 状态二次确认失败"
fi

# 检查 HTTPS（通过 nginx）
HTTPS_CODE=$(curl --max-time 15 -fsSk -o /dev/null -w "%{http_code}" "$SITE_URL/" 2>/dev/null || echo "000")
if [ "$HTTPS_CODE" = "200" ]; then
    log "HTTPS 前端响应正常 (HTTP $HTTPS_CODE) ✓"
else
    error "HTTPS 前端检查失败 (HTTP $HTTPS_CODE)"
fi

HTTPS_API=$(curl --max-time 15 -fsSk -o /dev/null -w "%{http_code}" "$SITE_URL/api/exchange/rates" 2>/dev/null || echo "000")
if [ "$HTTPS_API" = "200" ]; then
    log "HTTPS API 代理正常 (HTTP $HTTPS_API) ✓"
else
    error "HTTPS API 检查失败 (HTTP $HTTPS_API)"
fi

# ===== 11.1 安装 trial-check timer (cross-process-safe scheduler) =====
# gunicorn -w 3 多 worker 不能在 lifespan 启动定时任务（重复触发）。
# 用 systemd timer + oneshot service 集中调度，FOR UPDATE SKIP LOCKED 兜底。
log "===== 第11.1步: 安装 trial-check 定时器 ====="
sudo cp "$PROJECT_DIR/deploy/trial-check.service" /etc/systemd/system/
sudo cp "$PROJECT_DIR/deploy/trial-check.timer"   /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now trial-check.timer

if [ "$(systemctl is-active trial-check.timer)" = "active" ]; then
    log "trial-check.timer is-active=active ✓"
else
    error "trial-check.timer 未激活，部署中止"
fi
if [ "$(systemctl is-enabled trial-check.timer)" = "enabled" ]; then
    log "trial-check.timer is-enabled=enabled ✓"
else
    error "trial-check.timer 未启用，部署中止"
fi

# ===== 完成 =====
echo ""
echo "=========================================="
log "🎉 部署完成！"
echo "=========================================="
echo ""
echo "  前端: https://www.cbprice.cn"
echo "  API:  https://www.cbprice.cn/api/docs"
echo "  日志: sudo journalctl -u fastapi-app -f"
echo "  回滚: bash deploy/rollback.sh"
echo "  备份标签: $BACKUP_TAG"
echo ""
