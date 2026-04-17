import time
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

MAX_TRACKED_IPS = 10000


class LoginRateLimiter:
    """Per-IP login attempt limiter. 5 attempts/minute, 15-min lockout."""

    def __init__(
        self,
        max_attempts: int = 5,
        window_seconds: int = 60,
        lockout_seconds: int = 900,
    ):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.lockout_seconds = lockout_seconds
        self.attempts: dict[str, list[float]] = defaultdict(list)
        self.lockouts: dict[str, float] = {}

    def check(self, client_ip: str) -> None:
        """Raises HTTPException(429) if IP is locked out or over attempt limit."""
        now = time.time()

        if client_ip in self.lockouts:
            lockout_until = self.lockouts[client_ip]
            if now < lockout_until:
                remaining = int(lockout_until - now)
                from fastapi import HTTPException

                raise HTTPException(
                    status_code=429,
                    detail=f"登录尝试过多，请在{remaining}秒后重试",
                )
            else:
                del self.lockouts[client_ip]

        self.attempts[client_ip] = [
            t for t in self.attempts[client_ip] if now - t < self.window_seconds
        ]

        if len(self.attempts[client_ip]) >= self.max_attempts:
            self.lockouts[client_ip] = now + self.lockout_seconds
            logger.warning(
                "IP %s locked out for %d seconds after %d failed login attempts",
                client_ip,
                self.lockout_seconds,
                self.max_attempts,
            )
            from fastapi import HTTPException

            raise HTTPException(
                status_code=429,
                detail=f"登录尝试过多，请在{self.lockout_seconds}秒后重试",
            )

        self._evict_old_entries()

    def record_attempt(self, client_ip: str) -> None:
        self.attempts[client_ip].append(time.time())

    def clear(self, client_ip: str) -> None:
        self.attempts.pop(client_ip, None)
        self.lockouts.pop(client_ip, None)

    def _evict_old_entries(self) -> None:
        if len(self.attempts) >= MAX_TRACKED_IPS:
            oldest = sorted(
                self.attempts.keys(),
                key=lambda k: self.attempts[k][-1] if self.attempts[k] else 0,
            )
            for key in oldest[: len(self.attempts) - MAX_TRACKED_IPS + 1]:
                del self.attempts[key]


login_limiter = LoginRateLimiter()
