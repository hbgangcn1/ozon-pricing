#!/bin/bash
# CBPrice 生产回滚脚本
# 用法:
#   bash deploy/rollback.sh [TAG] [--auto-schema-rollback] [--restore-db-snapshot=PATH] [--yes]
#
# 默认行为: 仅代码回滚 + nginx + 旧服务恢复, 不动 DB schema (会发出警告)
#
# Flags:
#   TAG                          回滚目标 git tag (默认: 最新 pre-deploy-* tag)
#   --auto-schema-rollback       同时跑 alembic downgrade 到 tag 时刻的 head
#   --restore-db-snapshot=PATH   从 pg_dump 备份文件恢复 DB (危险, 需 --yes 跳过 prompt)
#   --yes                        跳过所有交互确认 (CI / 紧急回滚使用)

set -euo pipefail

PROJECT_DIR="/var/www/ozon-pricing"
VENV="$PROJECT_DIR/venv"
NGINX_CONF="/etc/nginx/sites-enabled/cbprice.cn"
NGINX_BACKUP_DIR="/var/backups/cbprice-nginx"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()   { echo -e "${GREEN}[ROLLBACK]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# ===== 解析参数 =====
TARGET_TAG=""
AUTO_SCHEMA_ROLLBACK=0
RESTORE_SNAPSHOT=""
ASSUME_YES=0

for arg in "$@"; do
    case "$arg" in
        --auto-schema-rollback) AUTO_SCHEMA_ROLLBACK=1 ;;
        --restore-db-snapshot=*) RESTORE_SNAPSHOT="${arg#*=}" ;;
        --yes|-y) ASSUME_YES=1 ;;
        --help|-h)
            grep -E '^#( |$)' "$0" | sed 's/^# \?//'
            exit 0
            ;;
        --*) error "未知参数: $arg" ;;
        *) TARGET_TAG="$arg" ;;
    esac
done

cd "$PROJECT_DIR" || error "无法进入项目目录"

echo "=========================================="
echo "  CBPrice 生产回滚"
echo "=========================================="
echo ""

log "当前 git 状态:"
git log --oneline -3
echo ""

if [ -z "$TARGET_TAG" ]; then
    TARGET_TAG=$(git tag -l 'pre-deploy-*' --sort=-creatordate | head -1)
fi
[ -n "$TARGET_TAG" ] || error "没有找到 pre-deploy-* 备份标签 (也未通过参数指定 TAG)"
git rev-parse "$TARGET_TAG" >/dev/null 2>&1 || error "tag 不存在: $TARGET_TAG"

log "回滚目标: $TARGET_TAG"
log "auto-schema-rollback = $AUTO_SCHEMA_ROLLBACK"
log "restore-db-snapshot  = ${RESTORE_SNAPSHOT:-<none>}"

if [ "$ASSUME_YES" -ne 1 ]; then
    read -p "确认回滚? (y/N) " -r
    [[ $REPLY =~ ^[Yy]$ ]] || { log "取消回滚"; exit 0; }
fi

# ===== 解析 tag 时刻 alembic head (用于可选 schema 回滚) =====
TARGET_REVISION=""
if [ "$AUTO_SCHEMA_ROLLBACK" -eq 1 ]; then
    log "===== 解析 tag 时刻 alembic head ====="
    # 列 tag 时刻 alembic/versions/ 下所有迁移脚本, 找出 head (down_revision 不被任何文件依赖的那个)
    VERSION_FILES=$(git show "$TARGET_TAG" --name-only --pretty=format: 2>/dev/null | grep -E '^alembic/versions/.*\.py$' || true)
    if [ -z "$VERSION_FILES" ]; then
        VERSION_FILES=$(git ls-tree -r --name-only "$TARGET_TAG" -- alembic/versions/ 2>/dev/null | grep -E '\.py$' || true)
    fi
    [ -n "$VERSION_FILES" ] || error "无法在 tag $TARGET_TAG 下找到 alembic/versions/*.py"

    # 解析所有 revision / down_revision 对, 找出无被依赖的 revision (head)
    REVISIONS_FILE=$(mktemp)
    DOWN_FILE=$(mktemp)
    trap 'rm -f "$REVISIONS_FILE" "$DOWN_FILE"' EXIT
    for vf in $VERSION_FILES; do
        content=$(git show "$TARGET_TAG:$vf" 2>/dev/null || true)
        rev=$(echo "$content" | grep -E "^revision[[:space:]]*[:=]" | head -1 | sed -E "s/.*['\"]([^'\"]+)['\"].*/\1/")
        down=$(echo "$content" | grep -E "^down_revision[[:space:]]*[:=]" | head -1 | sed -E "s/.*['\"]([^'\"]+)['\"].*/\1/")
        [ -n "$rev" ] && echo "$rev" >> "$REVISIONS_FILE"
        [ -n "$down" ] && echo "$down" >> "$DOWN_FILE"
    done
    TARGET_REVISION=$(comm -23 <(sort -u "$REVISIONS_FILE") <(sort -u "$DOWN_FILE") | head -1 || true)
    [ -n "$TARGET_REVISION" ] || error "解析 tag $TARGET_TAG 的 alembic head 失败"
    log "tag 时刻 alembic head = $TARGET_REVISION"
fi

log "===== 停止 FastAPI 服务 ====="
sudo systemctl stop fastapi-app.service 2>/dev/null || true

# ===== 可选: pg_restore 数据库快照 =====
if [ -n "$RESTORE_SNAPSHOT" ]; then
    [ -f "$RESTORE_SNAPSHOT" ] || error "数据库快照文件不存在: $RESTORE_SNAPSHOT"
    : "${POSTGRES_DB:=logistics}"
    [ -f "$PROJECT_DIR/.env" ] && source "$PROJECT_DIR/.env" 2>/dev/null || true
    DB_NAME="${POSTGRES_DB:-logistics}"
    warn "即将用 pg_restore 恢复数据库 $DB_NAME (会清空所有现有数据)"
    if [ "$ASSUME_YES" -ne 1 ]; then
        read -p "确认 pg_restore? (y/N) " -r
        [[ $REPLY =~ ^[Yy]$ ]] || { warn "跳过 pg_restore"; RESTORE_SNAPSHOT=""; }
    fi
    if [ -n "$RESTORE_SNAPSHOT" ]; then
        log "执行 pg_restore --clean --if-exists -d $DB_NAME $RESTORE_SNAPSHOT"
        pg_restore --clean --if-exists -d "$DB_NAME" "$RESTORE_SNAPSHOT" || \
            error "pg_restore 失败, 请手工恢复数据库, 命令模板: pg_restore --clean --if-exists -d $DB_NAME <snapshot.dump>"
        log "pg_restore 完成 ✓"
    fi
fi

# ===== 可选: alembic schema 回滚 =====
if [ "$AUTO_SCHEMA_ROLLBACK" -eq 1 ] && [ -n "$TARGET_REVISION" ]; then
    log "===== 执行 alembic downgrade $TARGET_REVISION ====="
    if ! "$VENV/bin/python" -m alembic downgrade "$TARGET_REVISION"; then
        error "alembic downgrade 失败! 请手工恢复:
    1. 检查当前 head:  $VENV/bin/python -m alembic current
    2. 手工降级:       $VENV/bin/python -m alembic downgrade $TARGET_REVISION
    3. 或从快照恢复:   pg_restore --clean --if-exists -d \$POSTGRES_DB <snapshot.dump>"
    fi
    log "alembic schema 已回滚到 $TARGET_REVISION ✓"
fi

log "===== 回滚代码 ====="
git checkout "$TARGET_TAG"
log "已回滚到 $TARGET_TAG"

if [ "$AUTO_SCHEMA_ROLLBACK" -ne 1 ] && [ -z "$RESTORE_SNAPSHOT" ]; then
    warn "未自动回滚 schema. 如果新版本曾跑过 alembic upgrade, DB 仍处于新 schema 状态."
    warn "如需 schema 回滚, 请重跑: bash deploy/rollback.sh $TARGET_TAG --auto-schema-rollback"
fi

log "===== 恢复 nginx 配置 ====="
LATEST_BAK=$(ls -t "$NGINX_BACKUP_DIR"/cbprice.cn.bak.* 2>/dev/null | head -1)
if [ -n "$LATEST_BAK" ]; then
    sudo cp "$LATEST_BAK" "$NGINX_CONF"
    sudo nginx -t && sudo systemctl reload nginx
    log "nginx 配置已恢复"
else
    warn "未找到 nginx 备份, 请手动恢复"
fi

log "===== 重启 FastAPI 服务 ====="
sudo systemctl start fastapi-app.service 2>/dev/null || warn "fastapi-app 启动失败, 请检查 journalctl"
sleep 3

if systemctl is-active --quiet fastapi-app.service 2>/dev/null; then
    log "FastAPI 服务已恢复 ✓"
else
    warn "FastAPI 未激活, 请检查: sudo journalctl -u fastapi-app -n 50"
fi

log "===== 健康检查 ====="
HTTP_CODE=$(curl --max-time 10 -fsS -o /dev/null -w "%{http_code}" http://127.0.0.1:8003/health 2>/dev/null || echo "000")
log "本地 /health 响应: HTTP $HTTP_CODE"

echo ""
echo "=========================================="
log "回滚完成"
echo "=========================================="
echo "  恢复到: $TARGET_TAG"
echo "  schema 回滚: $([ "$AUTO_SCHEMA_ROLLBACK" -eq 1 ] && echo "已执行 ($TARGET_REVISION)" || echo "未执行")"
echo "  数据库快照恢复: ${RESTORE_SNAPSHOT:-<未执行>}"
echo "  如需重新部署: bash deploy/deploy.sh"
echo ""
