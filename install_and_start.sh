#!/bin/bash
#
# 一键启动脚本 - 下载即用
# 复制到项目目录后直接运行:
#
#   chmod +x start.sh && ./start.sh
#
# 或一行命令安装并启动:
#
#   curl -sL https://raw.githubusercontent.com/your-repo/main/start.sh | bash -
#
# 首次运行会自动安装所有依赖

set -e

# 快速安装依赖（如果需要）
install_deps() {
    if command -v python3 &> /dev/null && command -v node &> /dev/null; then
        return 0
    fi

    echo "[安装] 安装系统依赖..."
    sudo apt-get update -qq
    sudo apt-get install -y -qq python3-venv postgresql-client nodejs npm

    # 如果 Node.js 版本过低，使用 n 安装新版
    NODE_VERSION=$(node -v 2>/dev/null | cut -d'v' -f2 | cut -d'.' -f1 || echo "0")
    if [ "$NODE_VERSION" -lt 18 ]; then
        sudo npm install -g n
        sudo n 18
        hash -r
    fi
}

# 快速设置环境
setup_env() {
    if [ ! -f .env ]; then
        cp .env.example .env 2>/dev/null || true
        echo "[配置] 请编辑 .env 文件设置必要的环境变量"
    fi
}

# 启动服务
start_services() {
    # 清理旧进程
    pkill -f "uvicorn.*8003" 2>/dev/null || true
    pkill -f "vite.*3001" 2>/dev/null || true
    pkill -f "gunicorn.*8003" 2>/dev/null || true
    sleep 1

    # 设置 Python 虚拟环境
    [ ! -d .venv ] && python3 -m venv .venv
    .venv/bin/pip install -q -r requirements.txt

    # 安装前端依赖
    [ ! -d frontend/node_modules ] && cd frontend && npm install && cd ..

    # 加载环境变量
    export $(grep -v '^#' .env 2>/dev/null | xargs) 2>/dev/null || true

    # 创建日志目录
    mkdir -p logs

    # 启动后端
    echo "[启动] 后端服务..."
    nohup .venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8003 > logs/backend.log 2>&1 &
    BACKEND_PID=$!

    # 等待后端就绪
    for i in {1..30}; do
        curl -s http://localhost:8003/docs > /dev/null 2>&1 && break
        sleep 1
    done

    # 启动前端
    echo "[启动] 前端服务..."
    cd frontend && nohup npm run dev > ../logs/frontend.log 2>&1 &

    echo ""
    echo "=========================================="
    echo "  物流定价系统已启动"
    echo "=========================================="
    echo "  后端 API : http://localhost:8003"
    echo "  前端     : http://localhost:3001"
    echo "  API文档  : http://localhost:8003/docs"
    echo "=========================================="
    echo ""
    echo "按 Ctrl+C 停止服务"
    echo ""

    # 等待中断信号
    trap "pkill -P $$; echo '[停止] 服务已关闭'; exit 0" SIGINT SIGTERM
    wait
}

# 主流程
install_deps
setup_env
start_services
