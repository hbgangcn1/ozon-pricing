# -*- coding: utf-8 -*-
import logging
import threading
from typing import Optional

from fastapi import Request

logger = logging.getLogger(__name__)

try:
    from redis_cache import get_redis_client as _redis_client_factory
except ImportError:
    _redis_client_factory = None

REDIS_AVAILABLE = _redis_client_factory is not None


def get_redis_client():
    if _redis_client_factory is None:
        return None
    return _redis_client_factory()


class DistributedLock:
    def __init__(self, key: str, timeout: int = 10, redis_available: bool = False):
        self.key = key
        self.timeout = timeout
        self.redis_available = redis_available and REDIS_AVAILABLE
        self.lock_acquired = False
        self.local_lock = threading.Lock()

    def acquire(self):
        acquired = self.local_lock.acquire(timeout=self.timeout)
        self.lock_acquired = bool(acquired)
        if not self.lock_acquired:
            return False
        if not self.redis_available:
            return True

        client = get_redis_client()
        if not client:
            return True

        redis_acquired = bool(client.set(self.key, "1", ex=self.timeout, nx=True))
        if not redis_acquired:
            self.local_lock.release()
            self.lock_acquired = False
            return False
        return True

    def release(self):
        if self.lock_acquired:
            if self.redis_available:
                client = get_redis_client()
                if client:
                    client.delete(self.key)
            try:
                self.local_lock.release()
            except RuntimeError:
                pass
            self.lock_acquired = False

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
        return False


def get_client_info(request: Optional[Request] = None) -> dict:
    if request is None:
        return {"ip_address": "unknown", "user_agent": "unknown"}

    try:
        headers = request.headers
        forwarded_for = headers.get("X-Forwarded-For")
        if forwarded_for:
            ip_address = forwarded_for.split(",")[0].strip()
        else:
            ip_address = request.client.host if request.client else "unknown"

        user_agent = (
            headers.get("user-agent")
            or headers.get("User-Agent")
            or "unknown"
        )
        return {"ip_address": ip_address, "user_agent": user_agent}
    except (AttributeError, TypeError):
        return {"ip_address": "unknown", "user_agent": "unknown"}


__all__ = ["DistributedLock", "get_client_info", "REDIS_AVAILABLE", "get_redis_client"]
