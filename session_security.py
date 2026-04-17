# -*- coding: utf-8 -*-
import asyncio
import time
import logging
from typing import Tuple, Optional

from database import AsyncSessionLocal
from session_security_helpers import DistributedLock, get_client_info
from db.sessions_crud import (
    count_active_sessions,
    get_oldest_active_session,
    deactivate_session,
    insert_session,
    get_session_with_user,
    update_session_activity,
    deactivate_all_sessions,
    add_login_attempt,
)
from db.users import verify_user as verify_user_db

logger = logging.getLogger(__name__)


class SessionSecurityEnhanced:
    MAX_CONCURRENT_SESSIONS = 5
    SESSION_REFRESH_INTERVAL = 1800
    SESSION_TIMEOUT = 3600
    DEFAULT_SESSION_TIMEOUT = 3600
    MAX_LOGIN_ATTEMPTS = 5
    LOCKOUT_DURATION = 900
    SessionSecurity = None  # type: ignore[assignment]
    _hmac_secret_cache: Optional[str] = None

    @staticmethod
    def get_client_info() -> dict:
        return get_client_info()

    @staticmethod
    async def check_and_create_session_atomic(
        user_id: int, session_id: str, ip_address: str, user_agent: str
    ) -> Tuple[bool, str]:
        max_sessions = SessionSecurityEnhanced.MAX_CONCURRENT_SESSIONS
        lock_key = f"session_create_{user_id}"
        lock = DistributedLock(lock_key, timeout=5, redis_available=True)
        loop = asyncio.get_event_loop()
        acquired = False
        try:
            acquired = await loop.run_in_executor(None, lock.acquire)
            async with AsyncSessionLocal() as session:
                try:
                    active_count = await count_active_sessions(session, user_id)
                    if active_count >= max_sessions:
                        oldest = await get_oldest_active_session(session, user_id)
                        if oldest:
                            await deactivate_session(session, oldest.session_id)
                            await session.commit()
                    now = time.time()
                    await insert_session(
                        session, session_id, user_id, ip_address, user_agent, now
                    )
                    await session.commit()
                    return True, "会话创建成功"
                except Exception as e:
                    await session.rollback()
                    return False, f"会话创建失败: {str(e)}"
        finally:
            if acquired:
                await loop.run_in_executor(None, lock.release)

    @staticmethod
    async def update_session_activity_atomic(session_id: str) -> bool:
        lock_key = f"session_update_{session_id}"
        lock = DistributedLock(lock_key, timeout=2, redis_available=True)
        loop = asyncio.get_event_loop()
        acquired = False
        try:
            acquired = await loop.run_in_executor(None, lock.acquire)
            async with AsyncSessionLocal() as session:
                try:
                    await update_session_activity(session, session_id, time.time())
                    await session.commit()
                    return True
                except Exception:
                    await session.rollback()
                    return False
        finally:
            if acquired:
                await loop.run_in_executor(None, lock.release)

    @staticmethod
    async def check_suspicious_ip(user_id: int, ip_address: str) -> Tuple[bool, str]:
        if ip_address in ("localhost", "127.0.0.1", "::1"):
            return False, ""
        return False, ""

    @staticmethod
    async def record_login_attempt(username: str, success: bool) -> None:
        try:
            async with AsyncSessionLocal() as session:
                await add_login_attempt(
                    session, username, "unknown", success, "unknown"
                )
                await session.commit()
        except Exception as e:
            logger.warning("登录记录失败: %s", e)

    @staticmethod
    def generate_session_id(user_id: int) -> str:
        import hashlib
        import os

        data = f"{user_id}{time.time()}{os.urandom(16)}"
        return hashlib.sha256(data.encode()).hexdigest()

    @staticmethod
    async def create_session(user_id: int, user_info: dict) -> Optional[str]:
        try:
            async with AsyncSessionLocal() as session:
                session_id = SessionSecurityEnhanced.generate_session_id(user_id)
                now = time.time()
                ip_address = user_info.get("ip_address", "unknown")
                user_agent = user_info.get("user_agent", "unknown")
                await insert_session(
                    session, session_id, user_id, ip_address, user_agent, now
                )
                await session.commit()
                return session_id
        except Exception as e:
            logger.error("创建会话失败: %s", e)
            return None

    @staticmethod
    async def get_session_info(session_id: str) -> Optional[dict]:
        try:
            async with AsyncSessionLocal() as session:
                return await get_session_with_user(session, session_id)
        except Exception as e:
            logger.warning("获取会话信息失败: %s", e)
            return None

    @staticmethod
    async def check_concurrent_sessions(user_id: int) -> Tuple[bool, str]:
        try:
            async with AsyncSessionLocal() as session:
                count = await count_active_sessions(session, user_id)
                if count >= SessionSecurityEnhanced.MAX_CONCURRENT_SESSIONS:
                    oldest = await get_oldest_active_session(session, user_id)
                    if oldest:
                        await deactivate_session(session, oldest.session_id)
                        await session.commit()
                    return True, "超过最大并发会话数，已自动下线最旧会话"
                return True, ""
        except Exception as e:
            logger.error("检查并发会话失败: %s", e)
            return True, ""

    @staticmethod
    async def force_logout_session(session_id: str, reason: str) -> bool:
        try:
            async with AsyncSessionLocal() as session:
                await deactivate_session(session, session_id)
                await session.commit()
                return True
        except Exception as e:
            logger.error("强制登出会话失败: %s", e)
            return False

    @staticmethod
    def is_user_locked(user_id: int) -> bool:
        return False

    @staticmethod
    async def verify_session_id(session_id: str) -> Tuple[bool, dict]:
        try:
            info = await SessionSecurityEnhanced.get_session_info(session_id)
            if info:
                return True, info
            return False, {}
        except Exception as e:
            logger.warning("验证会话ID失败: %s", e)
            return False, {}

    @staticmethod
    def get_session_timeout(
        user_id: Optional[int] = None, user_type: Optional[str] = None
    ) -> int:
        return SessionSecurityEnhanced.SESSION_TIMEOUT

    @staticmethod
    async def invalidate_user_sessions(
        user_id: int, exclude_session_id: Optional[str] = None
    ) -> int:
        try:
            async with AsyncSessionLocal() as session:
                await deactivate_all_sessions(
                    session, user_id, exclude_session_id=exclude_session_id
                )
                await session.commit()
                return 1
        except Exception as e:
            logger.error("使会话失效失败: %s", e)
            return 0

    @staticmethod
    def hmac_secret() -> str:
        return SessionSecurityEnhanced._get_hmac_secret()

    @staticmethod
    def _get_hmac_secret() -> str:
        import os
        import sys

        if SessionSecurityEnhanced._hmac_secret_cache is not None:
            return SessionSecurityEnhanced._hmac_secret_cache

        secret_key = os.environ.get("SESSION_HMAC_SECRET")
        if not secret_key:
            # Only allow default in test environment
            is_testing = "pytest" in sys.modules or os.environ.get(
                "PYTEST_CURRENT_TEST"
            )
            if is_testing:
                secret_key = "dev-only-hmac-secret-do-not-use-in-production"
            else:
                raise ValueError("SESSION_HMAC_SECRET environment variable must be set")
        SessionSecurityEnhanced._hmac_secret_cache = secret_key
        return secret_key

    @staticmethod
    async def verify_user(identifier, password):
        async with AsyncSessionLocal() as session:
            return await verify_user_db(session, identifier, password)

    @staticmethod
    async def verify_password_for_sensitive_operation(
        user_id: int, password: str
    ) -> bool:
        try:
            user = await verify_user(user_id, password)
            return user is not None
        except Exception:
            return False


async def verify_user(identifier, password):
    async with AsyncSessionLocal() as session:
        return await verify_user_db(session, identifier, password)


SessionSecurity = SessionSecurityEnhanced
SessionSecurityEnhanced.SessionSecurity = SessionSecurityEnhanced  # type: ignore[assignment]

__all__ = [
    "SessionSecurity",
    "SessionSecurityEnhanced",
    "DistributedLock",
]
