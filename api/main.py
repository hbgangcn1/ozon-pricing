import asyncio
import logging
import os
import time
import traceback
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

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
from api.routes.auth_security import router as auth_security_router
from api.middleware.rate_limit import RateLimitMiddleware

logger = logging.getLogger(__name__)


def _is_testing_environment() -> bool:
    return bool(os.getenv("PYTEST_CURRENT_TEST") or os.getenv("E2E_TEST"))


def _get_app_environment() -> str:
    app_env = os.getenv("APP_ENV") or os.getenv("ENVIRONMENT")
    if app_env:
        return app_env.lower()
    if os.getenv("PRODUCTION_MODE", "").lower() == "true":
        return "production"
    if _is_testing_environment():
        return "testing"
    return "development"


def _get_docs_config() -> dict:
    if _is_production:
        return {"docs_url": None, "redoc_url": None, "openapi_url": None}
    return {}


def _check_redis_ok() -> bool:
    try:
        from redis_cache import REDIS_AVAILABLE, get_redis_client
    except Exception:
        return False
    if not REDIS_AVAILABLE:
        return False
    client = get_redis_client()
    if client is None:
        return False
    try:
        client.ping()
        return True
    except Exception:
        return False


def _check_wechat_cert_expiry_days():
    try:
        from cryptography import x509
        from wechat_pay_v3_api import wechat_config
    except Exception:
        return None
    try:
        cert_path = getattr(wechat_config, "public_key_path", None)
        if not cert_path or not os.path.exists(cert_path):
            return None
        with open(cert_path, "rb") as fh:
            data = fh.read()
        cert = x509.load_pem_x509_certificate(data)
        if hasattr(cert, "not_valid_after_utc"):
            not_after = cert.not_valid_after_utc
        else:
            not_after = cert.not_valid_after.replace(tzinfo=timezone.utc)
        delta = not_after - datetime.now(timezone.utc)
        return int(delta.total_seconds() // 86400)
    except Exception:
        return None


_APP_ENV = _get_app_environment()
_is_production = _APP_ENV == "production"
_START_TIME = time.time()
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
_HSTS_POLICY = "max-age=31536000; includeSubDomains"
_MAX_BODY_BYTES = int(os.getenv("LOGISTICS_MAX_BODY_BYTES", str(10 * 1024 * 1024)))


class RequestBodySizeLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_body_bytes: int) -> None:
        super().__init__(app)
        self.max_body_bytes = max_body_bytes

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                body_size = int(content_length)
            except ValueError:
                body_size = 0
            if body_size > self.max_body_bytes:
                return JSONResponse(
                    status_code=413,
                    content={"detail": "Request body too large"},
                )
        return await call_next(request)


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

# [SEC-W12-14] Reject oversized requests before body parsing.
app.add_middleware(RequestBodySizeLimitMiddleware, max_body_bytes=_MAX_BODY_BYTES)

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
app.include_router(auth_security_router, prefix="/api")


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
    # [SEC-W12-06] Baseline browser response hardening headers.
    response.headers["Strict-Transport-Security"] = _HSTS_POLICY
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = _CSP_POLICY
    response.headers["Permissions-Policy"] = _PERMISSIONS_POLICY
    return response


@app.get("/")
async def root():
    return {"message": "物流定价系统API", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    from sqlalchemy import text

    db_ok = False
    try:
        async with engine.connect() as conn:
            await asyncio.wait_for(conn.execute(text("SELECT 1")), timeout=2.0)
        db_ok = True
    except Exception:
        logger.warning("健康检查数据库连接失败", exc_info=True)

    try:
        redis_ok = await asyncio.wait_for(
            asyncio.to_thread(_check_redis_ok), timeout=1.5
        )
    except Exception:
        redis_ok = False

    try:
        cert_days = await asyncio.wait_for(
            asyncio.to_thread(_check_wechat_cert_expiry_days), timeout=1.0
        )
    except Exception:
        cert_days = None
    wechat_cert_ok = True

    if not db_ok:
        status = "down"
        code = 503
    elif cert_days is not None and cert_days < 30:
        status = "degraded"
        code = 200
    elif not redis_ok:
        status = "degraded"
        code = 200
    else:
        status = "ok"
        code = 200

    body = {
        "status": status,
        "db_ok": db_ok,
        "redis_ok": redis_ok,
        "uptime_s": int(time.time() - _START_TIME),
        "wechat_pay_cert_expires_in_days": cert_days,
        "wechat_cert_days_left": cert_days,
        "wechat_cert_ok": wechat_cert_ok,
        "version": os.environ.get("GIT_SHA", "unknown"),
    }
    return JSONResponse(content=body, status_code=code)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )
    request_id = getattr(request.state, "request_id", None)
    if not request_id:
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    # [API-W12-14] Always log full traceback server-side; never expose
    # internals to the client regardless of environment.
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
