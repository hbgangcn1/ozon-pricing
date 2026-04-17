import logging
import os
import time
from collections import defaultdict
from typing import Dict, List, Set

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

MAX_TRACKED_KEYS = 10000
MAX_TIMESTAMPS_PER_IP = 500


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        max_requests: int = 100,
        window_seconds: int = 60,
        trusted_proxies: Set[str] | None = None,
    ):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, List[float]] = defaultdict(list)
        self.trusted_proxies: Set[str] = trusted_proxies or {
            "127.0.0.1",
            "::1",
        }
        self._is_production = os.environ.get("PRODUCTION_MODE", "").lower() == "true"

    def _get_client_ip(self, request: Request) -> str:
        peer_ip = request.client.host if request.client else "unknown"

        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for and peer_ip in self.trusted_proxies:
            return forwarded_for.split(",")[0].strip()

        return peer_ip

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

        if not self._is_production and client_ip in self._LOCALHOST_IPS:
            return await call_next(request)

        current_time = time.time()

        self.requests[client_ip] = [
            req_time
            for req_time in self.requests[client_ip]
            if current_time - req_time < self.window_seconds
        ][-MAX_TIMESTAMPS_PER_IP:]

        if len(self.requests[client_ip]) >= self.max_requests:
            raise HTTPException(status_code=429, detail="Too many requests")

        self._evict_oldest_keys()
        self.requests[client_ip].append(current_time)
        response = await call_next(request)
        return response
