#!/bin/bash
#
# 物流定价系统 - Ubuntu 单命令启动脚本
# 用法: ./start.sh [--production]
#
# 前置要求:
#   - Ubuntu 20.04+
#   - PostgreSQL 已安装并运行
#   - Node.js 18+ 已安装
#
# 如需安装前置依赖:
#   sudo apt update && sudo apt install -y postgresql nodejs npm python3-venv
#

set -e

# === 配置 ===
BACKEND_PORT=8003
FRONTEND_PORT=3001
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_ROOT/.venv"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
LOG_DIR="$PROJECT_ROOT/logs"
PID_DIR="$PROJECT_ROOT/.pids"

# === 颜色输出 ===
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()  { echo -e "${BLUE}[INFO]${NC} $1"; }
log_ok()    { echo -e "${GREEN}[ OK ]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# === 帮助信息 ===
show_help() {
    cat << EOF
用法: ./start.sh [选项]

选项:
    --production    使用生产模式启动 (Gunicorn)
    --backend-only  仅启动后端
    --frontend-only 仅启动前端
    --help          显示此帮助信息

示例:
    ./start.sh              # 开发模式启动
    ./start.sh --production # 生产模式启动

环境变量:
    JWT_SECRET_KEY          JWT密钥 (必填)
    POSTGRES_PASSWORD       PostgreSQL密码
    ALLOWED_ORIGINS         CORS允许的源

EOF
}

# === 检查依赖 ===
check_dependencies() {
    log_info "检查系统依赖..."

    # Node.js
    if ! command -v node &> /dev/null; then
        log_error "Node.js 未安装"
        log_info "安装: sudo apt install -y nodejs npm"
        exit 1
    fi
    NODE_VERSION=$(node -v | cut -d'v' -f2 | cut -d'.' -f1)
    if [ "$NODE_VERSION" -lt 18 ]; then
        log_warn "Node.js 版本低于 18，当前版本: $(node -v)"
    fi

    # Python
    if ! command -v python3 &> /dev/null; then
        log_error "Python3 未安装"
        exit 1
    fi

    # PostgreSQL
    if ! command -v psql &> /dev/null; then
        log_warn "PostgreSQL 客户端未安装 (如果只需要开发模式可忽略)"
    fi

    log_ok "依赖检查完成"
}

# === 创建目录 ===
setup_directories() {
    log_info "创建必要目录..."
    mkdir -p "$LOG_DIR"
    mkdir -p "$PID_DIR"
    mkdir -p "$FRONTEND_DIR/node_modules"
    log_ok "目录创建完成"
}

# === Python 环境设置 ===
setup_python_env() {
    log_info "设置 Python 虚拟环境..."

    if [ ! -d "$VENV_DIR" ]; then
        log_info "创建虚拟环境..."
        python3 -m venv "$VENV_DIR"
    fi

    log_info "安装 Python 依赖..."
    "$VENV_DIR/bin/pip" install --upgrade pip -q
    "$VENV_DIR/bin/pip" install -r "$PROJECT_ROOT/requirements.txt" -q

    log_ok "Python 环境设置完成"
}

# === 前端依赖设置 ===
setup_frontend() {
    log_info "设置前端依赖..."

    if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
        log_info "安装前端依赖 (可能需要几分钟)..."
        cd "$FRONTEND_DIR" && npm install
    fi

    log_ok "前端依赖设置完成"
}

# === 清理旧进程 ===
cleanup_old_processes() {
    log_info "清理旧进程..."

    # 清理后端
    if lsof -Pi :$BACKEND_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
        log_warn "端口 $BACKEND_PORT 已被占用，尝试终止..."
        kill $(lsof -t -i:$BACKEND_PORT) 2>/dev/null || true
        sleep 1
    fi

    # 清理前端
    if lsof -Pi :$FRONTEND_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
        log_warn "端口 $FRONTEND_PORT 已被占用，尝试终止..."
        kill $(lsof -t -i:$FRONTEND_PORT) 2>/dev/null || true
        sleep 1
    fi

    log_ok "进程清理完成"
}

# === 启动后端 (开发模式) ===
start_backend_dev() {
    log_info "启动 FastAPI 后端 (开发模式)..."

    cd "$PROJECT_ROOT"

    nohup "$VENV_DIR/bin/uvicorn" api.main:app \
        --host 0.0.0.0 \
        --port $BACKEND_PORT \
        --reload \
        > "$LOG_DIR/backend.log" 2>&1 &

    echo $! > "$PID_DIR/backend.pid"

    # 等待后端启动
    for i in {1..30}; do
        if curl -s "http://localhost:$BACKEND_PORT/docs" > /dev/null 2>&1; then
            log_ok "后端已启动: http://localhost:$BACKEND_PORT"
            return 0
        fi
        sleep 1
    done

    log_error "后端启动失败，请查看日志: $LOG_DIR/backend.log"
    return 1
}

# === 启动后端 (生产模式) ===
start_backend_prod() {
    log_info "启动 FastAPI 后端 (生产模式)..."

    if [ -z "$JWT_SECRET_KEY" ]; then
        log_error "生产模式需要设置 JWT_SECRET_KEY 环境变量"
        log_info "示例: export JWT_SECRET_KEY=\$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
        exit 1
    fi

    cd "$PROJECT_ROOT"

    WORKERS=${GUNICORN_WORKERS:-$(( 2 * $(nproc) + 1 ))}

    nohup "$VENV_DIR/bin/gunicorn" api.main:app \
        -k uvicorn.workers.UvicornWorker \
        -w "$WORKERS" \
        -b 0.0.0.0:$BACKEND_PORT \
        --access-logfile "$LOG_DIR/backend_access.log" \
        --error-logfile "$LOG_DIR/backend_error.log" \
        --timeout 120 \
        > "$LOG_DIR/backend.log" 2>&1 &

    echo $! > "$PID_DIR/backend.pid"

    # 等待后端启动
    for i in {1..30}; do
        if curl -s "http://localhost:$BACKEND_PORT/docs" > /dev/null 2>&1; then
            log_ok "后端已启动 (workers=$WORKERS): http://localhost:$BACKEND_PORT"
            return 0
        fi
        sleep 1
    done

    log_error "后端启动失败，请查看日志: $LOG_DIR/backend_error.log"
    return 1
}

# === 启动前端 ===
start_frontend() {
    log_info "启动前端..."

    cd "$FRONTEND_DIR"

    nohup npm run dev \
        > "$LOG_DIR/frontend.log" 2>&1 &

    echo $! > "$PID_DIR/frontend.pid"

    # 等待前端启动
    for i in {1..30}; do
        if curl -s "http://localhost:$FRONTEND_PORT" > /dev/null 2>&1; then
            log_ok "前端已启动: http://localhost:$FRONTEND_PORT"
            return 0
        fi
        sleep 1
    done

    log_error "前端启动失败，请查看日志: $LOG_DIR/frontend.log"
    return 1
}

# === 停止服务 ===
stop_services() {
    log_info "停止服务..."

    # 停止后端
    if [ -f "$PID_DIR/backend.pid" ]; then
        BACKEND_PID=$(cat "$PID_DIR/backend.pid")
        if kill -0 "$BACKEND_PID" 2>/dev/null; then
            kill "$BACKEND_PID" 2>/dev/null || true
            log_info "后端进程 $BACKEND_PID 已终止"
        fi
        rm -f "$PID_DIR/backend.pid"
    fi

    # 停止前端
    if [ -f "$PID_DIR/frontend.pid" ]; then
        FRONTEND_PID=$(cat "$PID_DIR/frontend.pid")
        if kill -0 "$FRONTEND_PID" 2>/dev/null; then
            kill "$FRONTEND_PID" 2>/dev/null || true
            log_info "前端进程 $FRONTEND_PID 已终止"
        fi
        rm -f "$PID_DIR/frontend.pid"
    fi

    # 使用端口终止残留进程
    pkill -f "uvicorn.*8003" 2>/dev/null || true
    pkill -f "vite.*3001" 2>/dev/null || true

    log_ok "所有服务已停止"
}

# === 主函数 ===
main() {
    # 解析参数
    MODE="dev"
    BACKEND_ONLY=false
    FRONTEND_ONLY=false

    for arg in "$@"; do
        case $arg in
            --production)
                MODE="prod"
                ;;
            --backend-only)
                BACKEND_ONLY=true
                ;;
            --frontend-only)
                FRONTEND_ONLY=true
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
        esac
    done

    # 清理旧进程
    cleanup_old_processes

    # 检查依赖
    check_dependencies

    # 创建目录
    setup_directories

    # 检查 .env 文件
    if [ ! -f "$PROJECT_ROOT/.env" ]; then
        log_warn ".env 文件不存在，已创建示例"
        cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"
        log_info "请编辑 $PROJECT_ROOT/.env 填写必要配置"
    fi

    # 加载环境变量
    export $(grep -v '^#' "$PROJECT_ROOT/.env" | xargs) 2>/dev/null || true

    # 仅停止模式
    if [ "$1" = "--stop" ]; then
        stop_services
        exit 0
    fi

    # 仅前端模式
    if [ "$FRONTEND_ONLY" = true ]; then
        setup_frontend
        start_frontend
        show_status
        wait
        exit 0
    fi

    # 仅后端模式
    if [ "$BACKEND_ONLY" = true ]; then
        setup_python_env
        if [ "$MODE" = "prod" ]; then
            start_backend_prod
        else
            start_backend_dev
        fi
        show_status
        wait
        exit 0
    fi

    # 完整启动
    setup_python_env
    setup_frontend

    if [ "$MODE" = "prod" ]; then
        start_backend_prod
    else
        start_backend_dev
    fi

    start_frontend

    show_status

    # 等待信号
    trap 'stop_services; exit 0' SIGINT SIGTERM

    log_info "按 Ctrl+C 停止服务"
    echo

    # 保持脚本运行
    while true; do
        sleep 1
        # 检查进程是否存活
        if [ -f "$PID_DIR/backend.pid" ]; then
            if ! kill -0 $(cat "$PID_DIR/backend.pid") 2>/dev/null; then
                log_error "后端进程已退出"
                break
            fi
        fi
    done
}

# === 显示状态 ===
show_status() {
    echo ""
    echo "=========================================="
    echo -e "  ${GREEN}物流定价系统已启动${NC}"
    echo "=========================================="
    echo -e "  ${YELLOW}后端 API${NC} : http://localhost:$BACKEND_PORT"
    echo -e "  ${YELLOW}前端${NC}    : http://localhost:$FRONTEND_PORT"
    echo -e "  ${YELLOW}API文档${NC} : http://localhost:$BACKEND_PORT/docs"
    echo "=========================================="
    echo ""
    echo "日志文件: $LOG_DIR/"
    echo ""
}

# === 执行 ===
main "$@"
