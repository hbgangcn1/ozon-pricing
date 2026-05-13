import logging
import os
import time
from collections import defaultdict
from typing import Dict, List

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from api.dependencies import get_request_ip

logger = logging.getLogger(__name__)

MAX_TRACKED_KEYS = 10000
MAX_TIMESTAMPS_PER_IP = 500
_RATE_LIMIT_PREFIX = "ratelimit:"


def _try_get_redis():
    try:
        from redis_cache import get_redis_client
        return get_redis_client()
    except Exception:
        return None


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        max_requests: int = 100,
        window_seconds: int = 60,
    ):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, List[float]] = defaultdict(list)
        self._is_production = os.environ.get("PRODUCTION_MODE", "").lower() == "true"

    def _get_client_ip(self, request: Request) -> str:
        return get_request_ip(request)

    def _check_rate_limit_redis(self, client_ip: str, redis_client) -> bool:
        key = f"{_RATE_LIMIT_PREFIX}{client_ip}"
        pipe = redis_client.pipeline(transaction=True)
        now = time.time()
        window_start = now - self.window_seconds
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zcard(key)
        pipe.zadd(key, {str(now): now})
        pipe.expire(key, self.window_seconds)
        results = pipe.execute()
        current_count = results[1]
        if current_count >= self.max_requests:
            redis_client.zrem(key, str(now))
            return False
        return True

    def _check_rate_limit_memory(self, client_ip: str) -> bool:
        current_time = time.time()
        self.requests[client_ip] = [
            req_time
            for req_time in self.requests[client_ip]
            if current_time - req_time < self.window_seconds
        ][-MAX_TIMESTAMPS_PER_IP:]

        if len(self.requests[client_ip]) >= self.max_requests:
            return False

        self._evict_oldest_keys()
        self.requests[client_ip].append(current_time)
        return True

    def _evict_oldest_keys(self):
        if len(self.requests) >= MAX_TRACKED_KEYS:
            oldest_keys = sorted(
                self.requests.keys(),
                key=lambda k: self.requests[k][-1] if self.requests[k] else 0,
            )
            for key in oldest_keys[: len(self.requests) - MAX_TRACKED_KEYS + 1]:
                del self.requests[key]

    _LOCALHOST_IPS = {"127.0.0.1", "::1", "localhost"}

    async def dispatch(self, request: Request, call_next):
        client_ip = self._get_client_ip(request)
        retry_after_seconds = self.window_seconds

        if not self._is_production and client_ip in self._LOCALHOST_IPS:
            return await call_next(request)

        redis_client = _try_get_redis()
        if redis_client is not None:
            try:
                allowed = self._check_rate_limit_redis(client_ip, redis_client)
            except Exception:
                logger.warning("Redis限流检查失败，回退到内存限流", exc_info=True)
                allowed = self._check_rate_limit_memory(client_ip)
        else:
            allowed = self._check_rate_limit_memory(client_ip)

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "请求过于频繁"},
                headers={"Retry-After": str(retry_after_seconds)},
            )

        response = await call_next(request)
        return response
