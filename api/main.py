from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os

from database import run_migrations, engine
from api.routes import (
    auth,
    products,
    logistics,
    pricing,
    subscriptions,
    orders,
    admin,
    settings,
    statistics,
    exchange,
)
from api.middleware.rate_limit import RateLimitMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时：执行数据库迁移
    try:
        run_migrations()
    except Exception as e:
        print(f"[lifespan] 数据库迁移失败: {e}")
        raise  # 迁移失败不应启动

    # 启动时：启动自动备份服务
    try:
        from postgres_backup_service import start_backup_service

        start_backup_service()
    except Exception as e:
        print(f"[lifespan] 启动备份服务失败: {e}")

    yield

    # 关闭时：停止自动备份服务
    try:
        from postgres_backup_service import stop_backup_service

        stop_backup_service()
    except Exception as e:
        print(f"[lifespan] 停止备份服务失败: {e}")

    await engine.dispose()


app = FastAPI(
    title="物流定价系统API",
    description="提供商品管理、物流规则管理和定价计算的HTTP接口",
    version="1.0.0",
    lifespan=lifespan,
)

_cors_origins = os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if not os.getenv("E2E_TEST"):
    app.add_middleware(RateLimitMiddleware, max_requests=100, window_seconds=60)

app.include_router(auth.router)
app.include_router(products.router)
app.include_router(logistics.router)
app.include_router(pricing.router)
app.include_router(subscriptions.router)
app.include_router(orders.router)
app.include_router(admin.router)
app.include_router(settings.router)
app.include_router(statistics.router)
app.include_router(exchange.router)


@app.get("/")
async def root():
    return {"message": "物流定价系统API", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8003)
