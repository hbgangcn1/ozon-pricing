import asyncio
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


def _get_app_environment() -> str:
    app_env = os.getenv("APP_ENV") or os.getenv("ENVIRONMENT")
    if app_env:
        return app_env.lower()
    if os.getenv("PRODUCTION_MODE", "").lower() == "true":
        return "production"
    return "development"


def _get_docs_config() -> dict:
    if _is_production:
        return {"docs_url": None, "redoc_url": None, "openapi_url": None}
    return {}


def _check_redis_health() -> dict:
    import time as _time

    from redis_cache import REDIS_AVAILABLE, get_redis_client

    if not REDIS_AVAILABLE:
        return {"redis_status": "not_configured"}

    client = get_redis_client()
    if client is None:
        return {"redis_status": "unavailable"}

    start = _time.monotonic()
    client.ping()
    return {
        "redis_status": "ok",
        "redis_latency_ms": round((_time.monotonic() - start) * 1000, 1),
    }


_APP_ENV = _get_app_environment()
_is_production = _APP_ENV == "production"
_CSP_POLICY = os.getenv(
    "CSP_POLICY",
    "default-src 'self'; script-src 'self'; style-src 'self' "
    "'unsafe-inline'; img-src 'self' data: https:; font-src 'self'; "
    "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; "
    "form-action 'self'",
)
_PERMISSIONS_POLICY = (
    "camera=(), microphone=(), geolocation=(), payment=(), usb=(), "
    "magnetometer=(), gyroscope=(), accelerometer=()"
)
_HSTS_POLICY = "max-age=63072000; includeSubDomains; preload"


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
        logger.exception("数据库迁移失败: %s", e)
        raise

    try:
        from postgres_backup_service import start_backup_service

        start_backup_service()
        logger.info("自动备份服务已启动")
    except Exception as e:
        logger.warning("启动备份服务失败: %s", e, exc_info=True)

    yield

    # 关闭时：停止自动备份服务
    try:
        from postgres_backup_service import stop_backup_service

        stop_backup_service()
    except Exception as e:
        logger.warning("停止备份服务失败: %s", e, exc_info=True)

    try:
        from payment_callback_enhanced import stop_payment_callback_monitor

        stop_payment_callback_monitor()
    except Exception as e:
        logger.warning("停止支付回调监控失败: %s", e, exc_info=True)

    try:
        from redis_cache import close_redis_client

        close_redis_client()
    except Exception:
        logger.warning("关闭Redis客户端失败", exc_info=True)

    try:
        from exchange_service_providers import ExchangeRateProvider

        ExchangeRateProvider.close_shared_session()
    except Exception:
        logger.warning("关闭汇率服务HTTP会话失败", exc_info=True)

    try:
        await engine.dispose()
    except Exception:
        logger.warning("engine.dispose() failed", exc_info=True)


app = FastAPI(
    title="物流定价系统API",
    description="提供商品管理、物流规则管理和定价计算的HTTP接口",
    version="1.0.0",
    lifespan=lifespan,
    **_get_docs_config(),
)

_cors_origins_env = os.environ.get("ALLOWED_ORIGINS")
if _is_production and not _cors_origins_env:
    logger.warning("ALLOWED_ORIGINS not set in production, defaulting to localhost")
_cors_origins = [o.strip() for o in (_cors_origins_env or "http://localhost:5173").split(",")]

# Security: wildcard origins with allow_credentials=True is insecure (browsers reject it anyway,
# but it signals a misconfiguration). Fail fast in production; warn in development.
if "*" in _cors_origins:
    if _is_production:
        raise RuntimeError(
            "ALLOWED_ORIGINS='*' is not allowed with allow_credentials=True in production. "
            "Set ALLOWED_ORIGINS to explicit origin(s), e.g. 'https://yourdomain.com'."
        )
    else:
        logger.warning(
            "ALLOWED_ORIGINS contains '*' — this is insecure with allow_credentials=True. "
            "Use explicit origins in production."
        )

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
)

_skip_rate_limit = not _is_production and os.getenv("E2E_TEST")
if not _skip_rate_limit:
    app.add_middleware(RateLimitMiddleware, max_requests=100, window_seconds=60)

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
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = _CSP_POLICY
    response.headers["Permissions-Policy"] = _PERMISSIONS_POLICY
    if _is_production:
        response.headers["Strict-Transport-Security"] = _HSTS_POLICY
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
        checks["db_status"] = "ok"
        checks["db_latency_ms"] = round((_time.monotonic() - start) * 1000, 1)
    except Exception:
        checks["db_status"] = "error"
        checks["db_error"] = "database connection failed"
        logger.warning("健康检查数据库连接失败", exc_info=True)

    try:
        checks.update(await asyncio.to_thread(_check_redis_health))
    except Exception:
        checks["redis_status"] = "unavailable"
        checks["redis_error"] = "service check failed"
        logger.warning("健康检查Redis连接失败", exc_info=True)

    redis_ok = checks.get("redis_status") in ("ok", "not_configured", "unavailable")
    status = "healthy" if checks.get("db_status") == "ok" and redis_ok else "degraded"
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
