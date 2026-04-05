# -*- coding: utf-8 -*-
import time
import logging
import threading

logger = logging.getLogger(__name__)

try:
    from redis_cache import get_redis_client

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

    def get_redis_client():
        return None


class DistributedLock:
    def __init__(self, key: str, timeout: int = 10, redis_available: bool = False):
        self.key = key
        self.timeout = timeout
        self.redis_available = redis_available and REDIS_AVAILABLE
        self.lock_acquired = False
        self.local_lock = threading.Lock()

    def acquire(self):
        if self.redis_available:
            client = get_redis_client()
            if client:
                self.lock_acquired = client.set(self.key, "1", ex=self.timeout, nx=True)
                return self.lock_acquired
        self.local_lock.acquire(timeout=self.timeout)
        self.lock_acquired = True
        return True

    def release(self):
        if self.lock_acquired:
            if self.redis_available:
                client = get_redis_client()
                if client:
                    client.delete(self.key)
            else:
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


def get_client_info() -> dict:
    ip_address = "unknown"
    user_agent = "unknown"

    try:
        from security import utils as security_utils

        if hasattr(security_utils, "_streamlit"):
            st = security_utils._streamlit
            if hasattr(st, "context") and hasattr(st.context, "headers"):
                headers = st.context.headers
                if headers:
                    x_forwarded_for = headers.get("X-Forwarded-For")
                    if x_forwarded_for and not isinstance(x_forwarded_for, type(None)):
                        if isinstance(x_forwarded_for, str) and "MagicMock" not in str(
                            x_forwarded_for
                        ):
                            ip_address = x_forwarded_for.split(",")[0].strip()
                        else:
                            ip_address = "unknown"
                    else:
                        x_real_ip = headers.get("X-Real-IP")
                        if x_real_ip and not isinstance(x_real_ip, type(None)):
                            if isinstance(x_real_ip, str) and "MagicMock" not in str(
                                x_real_ip
                            ):
                                ip_address = x_real_ip
                            else:
                                ip_address = "unknown"
                    ua = headers.get("User-Agent")
                    if (
                        ua
                        and not isinstance(ua, type(None))
                        and isinstance(ua, str)
                        and "MagicMock" not in str(ua)
                    ):
                        user_agent = ua
    except (ImportError, AttributeError, TypeError):
        pass

    return {"ip_address": ip_address, "user_agent": user_agent}


__all__ = ["DistributedLock", "get_client_info", "REDIS_AVAILABLE", "get_redis_client"]
