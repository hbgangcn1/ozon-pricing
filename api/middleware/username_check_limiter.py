import time
from collections import defaultdict

from fastapi import HTTPException

MAX_TRACKED_IPS = 10000


class UsernameCheckRateLimiter:
    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.attempts: dict[str, list[float]] = defaultdict(list)

    def check(self, client_ip: str) -> None:
        now = time.time()
        self.attempts[client_ip] = [
            stamp
            for stamp in self.attempts[client_ip]
            if now - stamp < self.window_seconds
        ]
        if len(self.attempts[client_ip]) >= self.max_requests:
            raise HTTPException(
                status_code=429,
                detail="请求过于频繁，请稍后再试",
            )
        self._evict_old_entries()
        self.attempts[client_ip].append(now)

    def reset(self) -> None:
        self.attempts.clear()

    def _evict_old_entries(self) -> None:
        if len(self.attempts) < MAX_TRACKED_IPS:
            return
        oldest = sorted(
            self.attempts.keys(),
            key=lambda key: self.attempts[key][-1] if self.attempts[key] else 0,
        )
        overflow = len(self.attempts) - MAX_TRACKED_IPS + 1
        for key in oldest[:overflow]:
            del self.attempts[key]


username_check_limiter = UsernameCheckRateLimiter()
