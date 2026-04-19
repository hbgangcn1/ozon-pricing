# Dockerfile - 前端服务
FROM node:18-alpine AS builder

WORKDIR /app

# 复制 package files
COPY package*.json ./

# 安装依赖
RUN npm ci

# 复制源代码
COPY . .

# 构建
RUN npm run build

# 生产镜像
FROM node:18-alpine

WORKDIR /app

# 安装 serve 用于静态文件服务
RUN npm install -g serve

# 从构建阶段复制产物
COPY --from=builder /app/dist ./dist

# 复制 index.html 到 dist (如果是单页应用)
RUN if [ -f dist/index.html ]; then echo "SPA build found"; else \
    cp dist/index.html dist/ 2>/dev/null || true; fi

# 暴露端口
EXPOSE 3001

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:3001 || exit 1

# 启动
CMD ["serve", "-s", "dist", "-l", "3001"]
