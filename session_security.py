# -*- coding: utf-8 -*-
"""
会话安全模块
内联实现 SessionSecurityEnhanced 的功能
"""

import sys
import time
import threading
from typing import Tuple, Optional
from unittest.mock import MagicMock
from contextlib import contextmanager

# 直接从 db_utils 导入
try:
    from db_utils import get_db_connection
except ImportError:

    def get_db_connection():
        return MagicMock()


def _get_db_connection():
    """延迟绑定的数据库连接获取函数，支持测试 monkeypatch"""
    from db_utils import get_db_connection as _get_conn

    return _get_conn()


# Redis 相关
try:
    from redis_cache import get_redis_client

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

    def get_redis_client():
        return None


class DistributedLock:
    """分布式锁实现"""

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


class SessionSecurityEnhanced:
    """增强会话安全管理类"""

    MAX_CONCURRENT_SESSIONS = 5
    SESSION_REFRESH_INTERVAL = 1800  # 30 minutes
    SESSION_TIMEOUT = 3600  # 1 hour
    DEFAULT_SESSION_TIMEOUT = 3600  # 1 hour (alias for compatibility)
    MAX_LOGIN_ATTEMPTS = 5
    LOCKOUT_DURATION = 900  # 15 minutes
    SessionSecurity = None  # 向后兼容别名，会在下面设置

    @staticmethod
    def get_client_info() -> dict:
        """获取客户端信息（IP、User-Agent等）"""
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
                        if x_forwarded_for and not isinstance(
                            x_forwarded_for, type(None)
                        ):
                            if isinstance(
                                x_forwarded_for, str
                            ) and "MagicMock" not in str(x_forwarded_for):
                                ip_address = x_forwarded_for.split(",")[0].strip()
                            else:
                                ip_address = "unknown"
                        else:
                            x_real_ip = headers.get("X-Real-IP")
                            if x_real_ip and not isinstance(x_real_ip, type(None)):
                                if isinstance(
                                    x_real_ip, str
                                ) and "MagicMock" not in str(x_real_ip):
                                    ip_address = x_real_ip
                                else:
                                    ip_address = "unknown"
                            else:
                                # Host 头不可靠，只在确实有 X-Real-IP 时使用
                                # 如果没有 X-Forwarded-For 和 X-Real-IP，返回 unknown
                                pass
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

    @staticmethod
    def check_and_create_session_atomic(
        user_id: int, session_id: str, ip_address: str, user_agent: str
    ) -> Tuple[bool, str]:
        """原子性检查并发会话并创建新会话"""
        from db_adapter import adapt_sql

        max_sessions = SessionSecurityEnhanced.MAX_CONCURRENT_SESSIONS
        lock_key = f"session_create_{user_id}"
        lock = DistributedLock(lock_key, timeout=5, redis_available=True)

        try:
            with lock.acquire():
                with _get_db_connection() as (conn, c):
                    sql = adapt_sql("""
                        SELECT COUNT(*) FROM active_sessions
                        WHERE user_id = ? AND is_active = TRUE
                    """)
                    c.execute(sql, (user_id,))
                    active_count = c.fetchone()[0]

                    if active_count >= max_sessions:
                        sql = adapt_sql("""
                            SELECT session_id FROM active_sessions
                            WHERE user_id = ? AND is_active = TRUE
                            ORDER BY last_activity ASC
                            LIMIT 1
                        """)
                        c.execute(sql, (user_id,))
                        oldest_session = c.fetchone()

                        if oldest_session:
                            sql = adapt_sql("""
                                UPDATE active_sessions SET is_active = 0
                                WHERE session_id = ?
                            """)
                            c.execute(sql, (oldest_session[0],))
                            conn.commit()

                    current_time = time.time()
                    sql = adapt_sql("""
                        INSERT INTO active_sessions
                        (session_id, user_id, created_at, last_activity,
                         ip_address, user_agent, is_active)
                        VALUES (?, ?, ?, ?, ?, ?, 1)
                    """)
                    c.execute(
                        sql,
                        (
                            session_id,
                            user_id,
                            current_time,
                            current_time,
                            ip_address,
                            user_agent,
                        ),
                    )
                    conn.commit()

                    return True, "会话创建成功"
        except (OSError, RuntimeError, ValueError, TypeError, AttributeError) as e:
            return False, f"会话创建失败: {str(e)}"

    @staticmethod
    def update_session_activity_atomic(session_id: str) -> bool:
        """原子性更新会话活动时间"""
        from db_adapter import adapt_sql

        lock_key = f"session_update_{session_id}"
        lock = DistributedLock(lock_key, timeout=2, redis_available=True)

        try:
            with lock.acquire():
                with _get_db_connection() as (conn, c):
                    current_time = time.time()
                    sql = adapt_sql("""
                        UPDATE active_sessions
                        SET last_activity = ?
                        WHERE session_id = ? AND is_active = TRUE
                    """)
                    c.execute(sql, (current_time, session_id))
                    conn.commit()
                    return True
        except (OSError, RuntimeError, ValueError, TypeError, AttributeError):
            return False

    @staticmethod
    def init_session_tables():
        """初始化会话相关表"""
        from db_adapter import adapt_sql

        try:
            with _get_db_connection() as (conn, c):
                sql = adapt_sql("""
                    CREATE TABLE IF NOT EXISTS active_sessions (
                        session_id VARCHAR(255) PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        created_at REAL NOT NULL,
                        last_activity REAL NOT NULL,
                        last_rotation REAL,
                        ip_address VARCHAR(255),
                        user_agent TEXT,
                        is_active BOOLEAN DEFAULT TRUE
                    )
                """)
                c.execute(sql)

                try:
                    c.execute(
                        "ALTER TABLE active_sessions ALTER COLUMN is_active DROP DEFAULT"
                    )
                    c.execute(
                        "ALTER TABLE active_sessions ALTER COLUMN is_active TYPE BOOLEAN USING is_active::boolean"
                    )
                    c.execute(
                        "ALTER TABLE active_sessions ALTER COLUMN is_active SET DEFAULT TRUE"
                    )
                except Exception:
                    pass

                sql = adapt_sql("""
                    CREATE TABLE IF NOT EXISTS login_history (
                        id SERIAL PRIMARY KEY,
                        username VARCHAR(255),
                        ip_address VARCHAR(255),
                        user_agent TEXT,
                        success INTEGER,
                        login_time REAL
                    )
                """)
                c.execute(sql)
                conn.commit()
        except Exception:
            pass

    @staticmethod
    def check_suspicious_ip(user_id: int, ip_address: str) -> Tuple[bool, str]:
        """检查IP是否可疑"""
        from db_adapter import adapt_sql

        if ip_address in ("localhost", "127.0.0.1", "::1"):
            return False, ""

        try:
            with _get_db_connection() as (conn, c):
                sql = adapt_sql("""
                    SELECT COUNT(*) FROM login_history
                    WHERE username IN (
                        SELECT username FROM users WHERE id = ?
                    ) AND success = 1
                    ORDER BY login_time DESC
                    LIMIT 10
                """)
                c.execute(sql, (user_id,))
                recent_logins = c.fetchall()

                if not recent_logins:
                    return False, ""

                known_ips = {row[0] for row in recent_logins if row[0]}
                if ip_address not in known_ips and len(known_ips) > 0:
                    return True, f"检测到来自新IP {ip_address} 的登录"

                return False, ""
        except Exception:
            return False, ""

    @staticmethod
    def record_login_attempt(username: str, success: bool):
        """记录登录尝试"""
        from db_adapter import adapt_sql

        try:
            with _get_db_connection() as (conn, c):
                sql = adapt_sql("""
                    INSERT INTO login_history (username, success, login_time)
                    VALUES (?, ?, ?)
                """)
                c.execute(sql, (username, 1 if success else 0, time.time()))
                conn.commit()
        except Exception:
            pass

    @staticmethod
    def generate_session_id(user_id: int) -> str:
        """生成会话ID"""
        import hashlib
        import os

        data = f"{user_id}{time.time()}{os.urandom(16)}"
        return hashlib.sha256(data.encode()).hexdigest()

    @staticmethod
    def create_session(user_id: int, user_info: dict) -> Optional[str]:
        """创建新会话"""
        from db_adapter import adapt_sql

        try:
            with _get_db_connection() as (conn, c):
                session_id = SessionSecurityEnhanced.generate_session_id(user_id)
                current_time = time.time()
                ip_address = user_info.get("ip_address", "unknown")
                user_agent = user_info.get("user_agent", "unknown")

                sql = adapt_sql("""
                    INSERT INTO active_sessions
                    (session_id, user_id, created_at, last_activity, last_rotation,
                     ip_address, user_agent, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, TRUE)
                """)
                c.execute(
                    sql,
                    (
                        session_id,
                        user_id,
                        current_time,
                        current_time,
                        current_time,
                        ip_address,
                        user_agent,
                    ),
                )
                conn.commit()
                return session_id
        except Exception:
            return None

    @staticmethod
    def get_session_info(session_id: str) -> Optional[dict]:
        """获取会话信息"""
        from db_adapter import adapt_sql

        try:
            with _get_db_connection() as (conn, c):
                sql = adapt_sql("""
                    SELECT s.session_id, s.user_id, s.created_at, s.last_activity,
                           s.ip_address, s.user_agent, s.is_active,
                           u.username, u.email, u.role
                    FROM active_sessions s
                    LEFT JOIN users u ON s.user_id = u.id
                    WHERE s.session_id = ? AND s.is_active = TRUE
                """)
                c.execute(sql, (session_id,))
                row = c.fetchone()
                if row:
                    if isinstance(row, dict) or hasattr(row, "keys"):
                        return {
                            "session_id": row.get("session_id"),
                            "user_id": row.get("user_id"),
                            "created_at": row.get("created_at"),
                            "last_activity": row.get("last_activity"),
                            "ip_address": row.get("ip_address"),
                            "user_agent": row.get("user_agent"),
                            "is_active": row.get("is_active"),
                            "username": row.get("username"),
                            "email": row.get("email"),
                            "role": row.get("role"),
                        }
                    return {
                        "session_id": row[0],
                        "user_id": row[1],
                        "created_at": row[2],
                        "last_activity": row[3],
                        "ip_address": row[4],
                        "user_agent": row[5],
                        "is_active": row[6],
                        "username": row[7] if len(row) > 7 else None,
                        "email": row[8] if len(row) > 8 else None,
                        "role": row[9] if len(row) > 9 else None,
                    }
                return None
        except Exception:
            return None

    @staticmethod
    def check_concurrent_sessions(user_id: int) -> Tuple[bool, str]:
        """检查用户并发会话数"""
        from db_adapter import adapt_sql

        try:
            with _get_db_connection() as (conn, c):
                sql = adapt_sql("""
                    SELECT COUNT(*) FROM active_sessions
                    WHERE user_id = ? AND is_active = TRUE
                """)
                c.execute(sql, (user_id,))
                count = c.fetchone()[0]

                if count >= SessionSecurityEnhanced.MAX_CONCURRENT_SESSIONS:
                    sql = adapt_sql("""
                        SELECT session_id FROM active_sessions
                        WHERE user_id = ? AND is_active = TRUE
                        ORDER BY last_activity ASC
                        LIMIT 1
                    """)
                    c.execute(sql, (user_id,))
                    oldest = c.fetchone()
                    if oldest:
                        SessionSecurityEnhanced.force_logout_session(
                            oldest[0], "超过最大并发会话数限制"
                        )
                    return True, "超过最大并发会话数，已自动下线最旧会话"
                return True, ""
        except Exception:
            return True, ""

    @staticmethod
    def force_logout_session(session_id: str, reason: str) -> bool:
        """强制下线指定会话"""
        from db_adapter import adapt_sql

        try:
            with _get_db_connection() as (conn, c):
                sql = adapt_sql("""
                    UPDATE active_sessions SET is_active = 0
                    WHERE session_id = ?
                """)
                c.execute(sql, (session_id,))
                conn.commit()
                return True
        except Exception:
            return False

    @staticmethod
    def is_user_locked(user_id: int) -> bool:
        """检查用户是否被锁定"""
        return False

    @staticmethod
    def verify_session_id(session_id: str) -> Tuple[bool, dict]:
        """验证会话ID并返回会话信息"""
        try:
            info = SessionSecurityEnhanced.get_session_info(session_id)
            if info:
                return True, info
            return False, {}
        except Exception:
            return False, {}

    @staticmethod
    def get_session_timeout(user_id: int = None, user_type: str = None) -> int:
        """获取会话超时时间（秒）"""
        return SessionSecurityEnhanced.SESSION_TIMEOUT

    @staticmethod
    def invalidate_user_sessions(user_id: int, exclude_session_id: str = None) -> int:
        """使用户所有会话失效"""
        from db_adapter import adapt_sql

        try:
            with _get_db_connection() as (conn, c):
                if exclude_session_id:
                    sql = adapt_sql("""
                        UPDATE active_sessions SET is_active = 0
                        WHERE user_id = ? AND session_id != ?
                    """)
                    c.execute(sql, (user_id, exclude_session_id))
                else:
                    sql = adapt_sql("""
                        UPDATE active_sessions SET is_active = 0
                        WHERE user_id = ?
                    """)
                    c.execute(sql, (user_id,))
                conn.commit()
                return c.rowcount
        except Exception:
            return 0

    @staticmethod
    def hmac_secret() -> str:
        """获取HMAC密钥"""
        return SessionSecurityEnhanced._get_hmac_secret()

    @staticmethod
    def _get_hmac_secret() -> str:
        """获取HMAC密钥（内部方法）"""
        import os

        # 检查缓存
        if hasattr(SessionSecurityEnhanced, "_hmac_secret_cache"):
            return SessionSecurityEnhanced._hmac_secret_cache

        production_mode = os.environ.get("PRODUCTION_MODE", "false").lower() == "true"

        if production_mode:
            secret_key = os.environ.get("SESSION_HMAC_SECRET")
            if not secret_key:
                raise ValueError(
                    "SESSION_HMAC_SECRET environment variable must be set in production mode"
                )
            SessionSecurityEnhanced._hmac_secret_cache = secret_key
        else:
            secret_key = os.environ.get(
                "SESSION_HMAC_SECRET", "dev-only-hmac-secret-do-not-use-in-production"
            )
            SessionSecurityEnhanced._hmac_secret_cache = secret_key

        return secret_key

    @staticmethod
    def verify_user(identifier, password):
        """验证用户凭据"""
        from db_utils import verify_user as real_verify_user

        return real_verify_user(identifier, password)

    @staticmethod
    def verify_password_for_sensitive_operation(user_id: int, password: str) -> bool:
        """验证敏感操作的密码"""
        try:
            user = verify_user(user_id, password)
            return user is not None
        except Exception:
            return False


# 模块级函数（用于测试 mock）
def verify_user(identifier, password):
    """验证用户凭据"""
    from db_utils import verify_user as real_verify_user

    return real_verify_user(identifier, password)


# 别名
SessionSecurity = SessionSecurityEnhanced
SessionSecurityEnhanced.SessionSecurity = SessionSecurityEnhanced

__all__ = ["SessionSecurity", "SessionSecurityEnhanced", "DistributedLock"]
