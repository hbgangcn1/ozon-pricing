#!/bin/bash

echo "停止现有服务..."

# 停止 systemd 服务
echo "停止 systemd streamlit 服务..."
sudo systemctl stop streamlit-app.service

# 查找并杀死占用端口的进程
echo "检查端口占用情况..."

# 检查 8081 端口
PID_8081=$(sudo lsof -t -i:8081)
if [ ! -z "$PID_8081" ]; then
    echo "发现端口 8081 被进程 $PID_8081 占用，正在停止..."
    sudo kill -9 $PID_8081
    sleep 2
fi

# 检查 8501 端口
PID_8501=$(sudo lsof -t -i:8501)
if [ ! -z "$PID_8501" ]; then
    echo "发现端口 8501 被进程 $PID_8501 占用，正在停止..."
    sudo kill -9 $PID_8501
    sleep 2
fi

echo "服务已停止，端口已释放"
echo "现在可以运行 ./start_production_gunicorn.sh"
