#!/bin/bash

set -e

echo "启动生产环境 — Gunicorn + Uvicorn Workers"
echo

export PRODUCTION_MODE=true

if [ -z "$JWT_SECRET_KEY" ]; then
    echo "ERROR: JWT_SECRET_KEY 环境变量未设置"
    echo "请设置: export JWT_SECRET_KEY='your-secret-key'"
    exit 1
fi

if [ -z "$ALLOWED_ORIGINS" ]; then
    echo "WARNING: ALLOWED_ORIGINS 未设置，CORS 将默认限制为 localhost"
fi

echo "当前配置："
echo "  PRODUCTION_MODE=$PRODUCTION_MODE"
echo "  ALLOWED_ORIGINS=${ALLOWED_ORIGINS:-未设置}"
echo

WORKERS=${GUNICORN_WORKERS:-4}
BIND=${GUNICORN_BIND:-0.0.0.0:8003}

echo "启动 Gunicorn (workers=$WORKERS, bind=$BIND) ..."
exec gunicorn api.main:app \
    -k uvicorn.workers.UvicornWorker \
    -w "$WORKERS" \
    -b "$BIND" \
    --access-logfile - \
    --error-logfile - \
    --timeout 120
