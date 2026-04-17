import logging
import os
import traceback
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from database import run_migrations, engine
from api.routes import (
    auth,
    products,
    logistics,
    pricing,
    subscriptions,
    orders,
    payment,
    admin,
    settings,
    statistics,
    exchange,
    commission_categories,
    logistics_pool,
)
from api.middleware.rate_limit import RateLimitMiddleware

logger = logging.getLogger(__name__)

_is_production = os.environ.get("PRODUCTION_MODE", "").lower() == "true"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 生产环境必要环境变量检查
    if _is_production:
        _required_vars = [
            "JWT_SECRET_KEY",
            "POSTGRES_PASSWORD",
            "SESSION_HMAC_SECRET",
            "ALLOWED_ORIGINS",
        ]
        for var in _required_vars:
            if not os.environ.get(var):
                raise RuntimeError(
                    f"Missing required environment variable for production: {var}"
                )

    # 启动时：执行数据库迁移
    try:
        await run_migrations()
    except Exception as e:
        logger.error("数据库迁移失败: %s", e)
        raise

    try:
        from postgres_backup_service import start_backup_service

        start_backup_service()
        logger.info("自动备份服务已启动")
    except Exception as e:
        logger.warning("启动备份服务失败: %s", e)

    yield

    # 关闭时：停止自动备份服务
    try:
        from postgres_backup_service import stop_backup_service

        stop_backup_service()
    except Exception as e:
        logger.warning("停止备份服务失败: %s", e)

    try:
        from redis_cache import get_redis_client

        client = get_redis_client()
        if client:
            client.close()
    except Exception:
        pass

    await engine.dispose()


app = FastAPI(
    title="物流定价系统API",
    description="提供商品管理、物流规则管理和定价计算的HTTP接口",
    version="1.0.0",
    lifespan=lifespan,
)

_cors_origins_env = os.environ.get("ALLOWED_ORIGINS")
if _is_production and not _cors_origins_env:
    logger.warning("ALLOWED_ORIGINS not set in production, defaulting to localhost")
_cors_origins = (_cors_origins_env or "http://localhost:5173").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

_skip_rate_limit = not _is_production and os.getenv("E2E_TEST")
if not _skip_rate_limit:
    app.add_middleware(RateLimitMiddleware, max_requests=100, window_seconds=60)
    if _is_production:
        logger.warning(
            "Rate limiter is per-process only. "
            "With multiple Gunicorn workers, each worker has its own counter. "
            "Consider Redis-backed rate limiting for accurate cross-worker limits."
        )

app.include_router(auth.router)
app.include_router(products.router)
app.include_router(logistics.router)
app.include_router(pricing.router)
app.include_router(subscriptions.router)
app.include_router(orders.router)
app.include_router(payment.router)
app.include_router(admin.router)
app.include_router(settings.router)
app.include_router(statistics.router)
app.include_router(exchange.router)
app.include_router(commission_categories.router)
app.include_router(logistics_pool.router)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if _is_production:
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
    return response


@app.get("/")
async def root():
    return {"message": "物流定价系统API", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    import time as _time

    checks: dict = {"api": "ok"}
    try:
        from sqlalchemy import text

        start = _time.monotonic()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
        checks["db_latency_ms"] = round((_time.monotonic() - start) * 1000, 1)
    except Exception as exc:
        checks["database"] = "error"
        checks["db_error"] = str(type(exc).__name__)
    status = "healthy" if checks.get("database") == "ok" else "degraded"
    code = 200 if status == "healthy" else 503
    return JSONResponse(content={"status": status, **checks}, status_code=code)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )
    request_id = getattr(request.state, "request_id", None)
    logging.getLogger("api.error").error(
        "Unhandled %s at %s %s (request_id=%s):\n%s",
        type(exc).__name__,
        request.method,
        request.url.path,
        request_id,
        traceback.format_exc(),
    )
    body: dict = {"detail": "Internal server error"}
    if request_id:
        body["request_id"] = request_id
    return JSONResponse(status_code=500, content=body)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8003)
