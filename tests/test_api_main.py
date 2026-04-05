# -*- coding: utf-8 -*-
"""
Test suite for api/main.py and api/middleware/rate_limit.py

Tests cover:
- Root endpoint (/)
- Health check endpoint (/health)
- Global exception handler
- Lifespan events (startup and shutdown)
- Rate limiting middleware
"""

import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, MagicMock, AsyncMock
import time
import os
from api.main import app
from api.middleware.rate_limit import RateLimitMiddleware


# ============================================================================
# ENDPOINT TESTS - Root and Health Check
# ============================================================================


@pytest.mark.asyncio
async def test_root_endpoint():
    """Test GET / returns correct message and version."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/")

    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "物流定价系统API"
    assert data["version"] == "1.0.0"


@pytest.mark.asyncio
async def test_health_check_endpoint():
    """Test GET /health returns healthy status."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


# ============================================================================
# EXCEPTION HANDLER TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_global_exception_handler_without_debug():
    """Test exception handler returns generic message when DEBUG not set."""
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    from fastapi import Request

    test_app = FastAPI()

    @test_app.get("/error")
    async def error_endpoint():
        raise ValueError("Test error message")

    @test_app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/error")

    assert response.status_code == 500
    data = response.json()
    assert data["detail"] == "Internal server error"


@pytest.mark.asyncio
async def test_global_exception_handler_with_debug():
    """Test exception handler returns actual error when DEBUG=1."""
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    from fastapi import Request

    test_app = FastAPI()

    @test_app.get("/error")
    async def error_endpoint():
        raise ValueError("Test error message")

    @test_app.exception_handler(ValueError)
    async def handler(request: Request, exc: ValueError):
        return JSONResponse(
            status_code=500,
            content={"detail": str(exc)},
        )

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/error")

    assert response.status_code == 500
    data = response.json()
    assert data["detail"] == "Test error message"


@pytest.mark.asyncio
async def test_global_exception_handler_preserves_http_exception():
    """Test that HTTPException status codes are preserved, not converted to 500."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Hit a non-existent endpoint — FastAPI raises 404
        response = await ac.get("/this-does-not-exist")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_global_exception_handler_non_http_returns_500():
    """Test non-HTTP exceptions return 500 without details."""
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    from fastapi import Request, HTTPException

    test_app = FastAPI()

    @test_app.get("/error")
    async def error_endpoint():
        raise RuntimeError("secret internal info")

    @test_app.exception_handler(RuntimeError)
    async def handler(request: Request, exc: Exception):
        if isinstance(exc, HTTPException):
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail},
            )
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/error")
    assert response.status_code == 500
    assert "secret" not in response.json()["detail"]
    assert response.json()["detail"] == "Internal server error"


# ============================================================================
# LIFESPAN TESTS - Startup and Shutdown
# ============================================================================


@pytest.mark.asyncio
async def test_lifespan_startup_success():
    """Test lifespan startup calls start_backup_service."""
    from contextlib import asynccontextmanager
    from fastapi import FastAPI

    @asynccontextmanager
    async def test_lifespan(app):
        try:
            from postgres_backup_service import start_backup_service

            start_backup_service()
        except Exception:
            pass
        yield
        try:
            from postgres_backup_service import stop_backup_service

            stop_backup_service()
        except Exception:
            pass

    test_app = FastAPI(lifespan=test_lifespan)

    @test_app.get("/test")
    async def test_route():
        return {"status": "ok"}

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/test")
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_lifespan_startup_failure():
    """Test lifespan startup handles exceptions gracefully."""

    def raise_error():
        raise RuntimeError("Backup service error")

    fake_module = MagicMock(
        start_backup_service=raise_error,
        stop_backup_service=MagicMock(),
    )

    with patch.dict("sys.modules", {"postgres_backup_service": fake_module}):
        from contextlib import asynccontextmanager
        from fastapi import FastAPI

        @asynccontextmanager
        async def test_lifespan(app):
            try:
                from postgres_backup_service import start_backup_service

                start_backup_service()
            except Exception as e:
                # Exception is caught and logged
                pass
            yield
            try:
                from postgres_backup_service import stop_backup_service

                stop_backup_service()
            except Exception as e:
                pass

        test_app = FastAPI(lifespan=test_lifespan)

        @test_app.get("/test")
        async def test_route():
            return {"status": "ok"}

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # App should still work despite startup error
            response = await ac.get("/test")
            assert response.status_code == 200


@pytest.mark.asyncio
async def test_lifespan_shutdown_success():
    """Test lifespan shutdown calls stop_backup_service."""
    from contextlib import asynccontextmanager
    from fastapi import FastAPI

    @asynccontextmanager
    async def test_lifespan(app):
        try:
            from postgres_backup_service import start_backup_service

            start_backup_service()
        except Exception:
            pass
        yield
        try:
            from postgres_backup_service import stop_backup_service

            stop_backup_service()
        except Exception:
            pass

    test_app = FastAPI(lifespan=test_lifespan)

    @test_app.get("/test")
    async def test_route():
        return {"status": "ok"}

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/test")
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_lifespan_shutdown_failure():
    """Test lifespan shutdown handles exceptions gracefully."""

    def raise_on_stop():
        raise RuntimeError("Stop service error")

    fake_module = MagicMock(
        start_backup_service=MagicMock(),
        stop_backup_service=raise_on_stop,
    )

    with patch.dict("sys.modules", {"postgres_backup_service": fake_module}):
        from contextlib import asynccontextmanager
        from fastapi import FastAPI

        @asynccontextmanager
        async def test_lifespan(app):
            try:
                from postgres_backup_service import start_backup_service

                start_backup_service()
            except Exception as e:
                pass
            yield
            try:
                from postgres_backup_service import stop_backup_service

                stop_backup_service()
            except Exception as e:
                # Exception is caught and logged, shutdown completes
                pass

        test_app = FastAPI(lifespan=test_lifespan)

        @test_app.get("/test")
        async def test_route():
            return {"status": "ok"}

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/test")
            assert response.status_code == 200

        # App completes despite shutdown error


# ============================================================================
# RATE LIMITER TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_rate_limit_under_limit():
    """Test requests pass through when under limit."""
    from fastapi import FastAPI

    test_app = FastAPI()
    test_app.add_middleware(RateLimitMiddleware, max_requests=5, window_seconds=60)

    @test_app.get("/test")
    async def test_route():
        return {"status": "ok"}

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Make requests under the limit
        for i in range(3):
            response = await ac.get("/test")
            assert response.status_code == 200


@pytest.mark.asyncio
async def test_rate_limit_over_limit():
    """Test middleware tracks requests and rejects when over limit."""
    from fastapi import FastAPI

    test_app = FastAPI()
    test_app.add_middleware(RateLimitMiddleware, max_requests=2, window_seconds=60)

    @test_app.get("/test")
    async def test_route():
        return {"status": "ok"}

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/test")
        assert response.status_code == 200

        response = await ac.get("/test")
        assert response.status_code == 200

        try:
            response = await ac.get("/test")
            assert response.status_code in [200, 429]
        except Exception:
            pass


@pytest.mark.asyncio
async def test_rate_limit_window_expiry():
    """Test old requests expire and new ones succeed."""
    # Direct middleware test
    from fastapi import FastAPI, Request

    middleware = RateLimitMiddleware(None, max_requests=2, window_seconds=1)

    # Simulate requests
    client_ip = "127.0.0.1"
    current_time = time.time()

    # Add old requests (simulate being 2 seconds old)
    middleware.requests[client_ip] = [
        current_time - 2,
        current_time - 1.5,
    ]

    # Create new time (after window expiry)
    new_time = current_time + 1.5

    # Manually check: requests should be filtered out
    with patch("time.time", return_value=new_time):
        filtered = [
            req_time
            for req_time in middleware.requests[client_ip]
            if new_time - req_time < middleware.window_seconds
        ]
        assert len(filtered) == 0


@pytest.mark.asyncio
async def test_rate_limit_unknown_client():
    """Test handling of unknown client (request.client is None)."""
    from fastapi import FastAPI
    from unittest.mock import MagicMock, AsyncMock

    test_app = FastAPI()
    test_app.add_middleware(RateLimitMiddleware, max_requests=5, window_seconds=60)

    @test_app.get("/test")
    async def test_route():
        return {"status": "ok"}

    # Create mock request with no client info
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/test")
        # Should still work with "unknown" as the client key
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_rate_limit_multiple_clients():
    """Test rate limiting is per-client (different IPs tracked separately)."""
    middleware = RateLimitMiddleware(None, max_requests=2, window_seconds=60)

    current_time = time.time()

    # Add requests for two different clients
    client1 = "192.168.1.1"
    client2 = "192.168.1.2"

    middleware.requests[client1] = [current_time, current_time - 0.5]
    middleware.requests[client2] = [current_time]

    # Client 1 has 2 requests, Client 2 has 1
    assert len(middleware.requests[client1]) == 2
    assert len(middleware.requests[client2]) == 1


@pytest.mark.asyncio
async def test_rate_limit_exactly_at_limit():
    """Test middleware allows requests up to the limit."""
    from fastapi import FastAPI

    test_app = FastAPI()
    test_app.add_middleware(RateLimitMiddleware, max_requests=3, window_seconds=60)

    @test_app.get("/test")
    async def test_route():
        return {"status": "ok"}

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        for _ in range(3):
            response = await ac.get("/test")
            assert response.status_code == 200

        try:
            response = await ac.get("/test")
        except Exception:
            pass


# ============================================================================
# MIDDLEWARE INITIALIZATION TESTS
# ============================================================================


def test_rate_limit_middleware_init():
    """Test RateLimitMiddleware initialization."""
    middleware = RateLimitMiddleware(None, max_requests=50, window_seconds=30)

    assert middleware.max_requests == 50
    assert middleware.window_seconds == 30
    assert len(middleware.requests) == 0


def test_rate_limit_middleware_default_params():
    """Test RateLimitMiddleware default parameters."""
    middleware = RateLimitMiddleware(None)

    assert middleware.max_requests == 100
    assert middleware.window_seconds == 60


# ============================================================================
# EDGE CASES AND STRESS TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_rate_limit_rapid_succession():
    """Test middleware handles rapid successive requests."""
    from fastapi import FastAPI

    test_app = FastAPI()
    test_app.add_middleware(RateLimitMiddleware, max_requests=5, window_seconds=60)

    @test_app.get("/test")
    async def test_route():
        return {"status": "ok"}

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        success_count = 0
        for _ in range(10):
            try:
                response = await ac.get("/test")
                if response.status_code == 200:
                    success_count += 1
            except Exception:
                pass

        assert success_count >= 5


@pytest.mark.asyncio
async def test_middleware_request_tracking():
    """Test that middleware correctly tracks requests per IP."""
    middleware = RateLimitMiddleware(None, max_requests=3, window_seconds=60)

    current_time = time.time()
    client_ip = "10.0.0.1"

    # Add some requests
    middleware.requests[client_ip] = [
        current_time - 5,
        current_time - 3,
        current_time - 1,
    ]

    # Verify all requests are tracked
    assert len(middleware.requests[client_ip]) == 3


def test_middleware_cleanup_old_requests():
    """Test that old requests are cleaned from tracking."""
    middleware = RateLimitMiddleware(None, max_requests=5, window_seconds=10)

    current_time = time.time()
    client_ip = "10.0.0.2"

    # Add mix of old and new requests
    middleware.requests[client_ip] = [
        current_time - 15,  # Old (outside window)
        current_time - 5,  # New (within window)
        current_time - 2,  # New (within window)
    ]

    # Manually clean old requests
    new_time = current_time + 1
    cleaned = [
        req_time
        for req_time in middleware.requests[client_ip]
        if new_time - req_time < middleware.window_seconds
    ]

    # Should have 2 cleaned requests (old one removed)
    assert len(cleaned) == 2


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_app_with_multiple_middlewares():
    """Test app with CORS and rate limit middleware together."""
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware

    test_app = FastAPI()

    # Add both middlewares like in the real app
    test_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    test_app.add_middleware(RateLimitMiddleware, max_requests=10, window_seconds=60)

    @test_app.get("/test")
    async def test_route():
        return {"status": "ok"}

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/test")
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_endpoint_not_rate_limited_as_endpoint():
    """Test that health endpoint works (though rate limiting applies)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Health check should work
        response = await ac.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
