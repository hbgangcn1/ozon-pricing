# -*- coding: utf-8 -*-
"""
增强会话安全管理模块
解决高优先级安全问题：会话管理竞态条件
实现原子性操作和分布式锁支持
"""

import time
import threading
from typing import Tuple
from contextlib import contextmanager

try:
    from .db_utils import get_db_connection
except ImportError:
    from db_utils import get_db_connection

try:
    from .redis_cache import get_redis_client
    _redis_available = True
except ImportError:
    _redis_available = False
    # 定义占位函数，防止类型检查错误

    def get_redis_client():
        """占位函数，当Redis不可用时返回None"""
        return None

REDIS_AVAILABLE = _redis_available


class DistributedLock:
    """分布式锁实现（支持Redis和数据库锁）"""

    def __init__(
        self, key: str, timeout: int = 10, redis_available: bool = False
    ):
        """
        初始化分布式锁

        Args:
            key: 锁的键名
            timeout: 锁超时时间（秒）
            redis_available: 是否使用Redis
        """
        self.key = key
        self.timeout = timeout
        self.redis_available = redis_available and REDIS_AVAILABLE
        self.lock_acquired = False
        self.local_lock = threading.Lock()

    def _acquire_redis_lock(self) -> bool:
        """使用Redis获取分布式锁"""
        if not self.redis_available:
            return False

        try:
            redis_client = get_redis_client()
            if redis_client is None:
                return False

            # 使用SET NX EX实现分布式锁
            lock_key = f"lock:session:{self.key}"
            result = redis_client.set(
                lock_key,
                str(time.time()),
                nx=True,  # 只在键不存在时设置
                ex=self.timeout  # 设置过期时间
            )
            return result is True
        except (AttributeError, ConnectionError, OSError, TimeoutError):
            # Redis连接错误、超时或其他操作错误
            return False

    def _release_redis_lock(self) -> bool:
        """释放Redis锁"""
        if not self.redis_available:
            return False

        try:
            redis_client = get_redis_client()
            if redis_client is None:
                return False

            lock_key = f"lock:session:{self.key}"
            redis_client.delete(lock_key)
            return True
        except (AttributeError, ConnectionError, OSError, TimeoutError):
            # Redis连接错误、超时或其他操作错误
            return False

    @staticmethod
    def _acquire_db_lock() -> bool:
        """使用数据库锁获取锁（SQLite支持）"""
        try:
            with get_db_connection() as (conn, c):
                # SQLite的BEGIN IMMEDIATE事务会获取写锁
                # 这可以防止并发写入
                # PostgreSQL使用BEGIN TRANSACTION
                try:
                    import psycopg2
                    is_pg = isinstance(conn, psycopg2.extensions.connection)
                except (ImportError, AttributeError):
                    is_pg = False

                if is_pg:
                    c.execute("BEGIN TRANSACTION")
                else:
                    # SQLite特有语法
                    conn.execute("BEGIN IMMEDIATE")
                return True
        except (OSError, ConnectionError, RuntimeError):
            # 数据库连接错误或其他运行时错误
            return False

    @staticmethod
    def _release_db_lock(conn):
        """释放数据库锁"""
        try:
            conn.commit()
            return True
        except (OSError, RuntimeError, AttributeError):
            # 数据库提交错误，回滚并返回失败
            try:
                conn.rollback()
            except (OSError, RuntimeError, AttributeError):
                # 回滚也可能失败，忽略（不影响外部逻辑）
                pass
            return False

    @contextmanager
    def acquire(self):
        """
        获取锁的上下文管理器
        """
        # 优先使用Redis分布式锁
        if self.redis_available:
            if self._acquire_redis_lock():
                self.lock_acquired = True
                try:
                    yield self
                finally:
                    self._release_redis_lock()
                    self.lock_acquired = False
                return
            else:
                # Redis锁获取失败，降级到数据库锁
                pass

        # 使用数据库锁（本地锁+数据库事务）
        with self.local_lock:
            with get_db_connection() as (conn, c):
                # BEGIN IMMEDIATE会获取写锁，防止并发
                try:
                    # 检测数据库类型
                    try:
                        import psycopg2
                        is_pg = isinstance(
                            conn, psycopg2.extensions.connection)
                    except (ImportError, AttributeError):
                        is_pg = False

                    if is_pg:
                        c.execute("BEGIN TRANSACTION")
                    else:
                        # SQLite特有语法
                        conn.execute("BEGIN IMMEDIATE")
                    self.lock_acquired = True
                    try:
                        yield self
                    finally:
                        conn.commit()
                        self.lock_acquired = False
                except (
                    OSError, RuntimeError, ValueError, TypeError,
                    AttributeError
                ):
                    # 数据库操作错误或其他运行时错误
                    conn.rollback()
                    self.lock_acquired = False
                    raise


class SessionSecurityEnhanced:
    """增强会话安全管理类"""

    @staticmethod
    def check_and_create_session_atomic(
        user_id: int,
        session_id: str,
        ip_address: str,
        user_agent: str
    ) -> Tuple[bool, str]:
        """
        原子性地检查并发会话并创建新会话
        解决竞态条件问题

        Args:
            user_id: 用户ID
            session_id: 会话ID
            ip_address: IP地址
            user_agent: User-Agent

        Returns:
            (success, message): 是否成功，提示消息
        """
        from session_security import SessionSecurity

        # 使用分布式锁确保原子性
        lock_key = f"session_create_{user_id}"
        lock = DistributedLock(lock_key, timeout=5, redis_available=True)

        try:
            with lock.acquire():  # type: ignore[misc]
                # 在锁保护下执行检查和创建操作
                # 1. 检查当前活跃会话数
                with get_db_connection() as (conn, c):
                    from db_adapter import adapt_sql
                    sql = adapt_sql("""
                        SELECT COUNT(*) FROM active_sessions
                        WHERE user_id = ? AND is_active = 1
                    """)
                    c.execute(sql, (user_id,))
                    active_count = c.fetchone()[0]

                    # 2. 如果超过限制，下线最旧的会话
                    if active_count >= SessionSecurity.MAX_CONCURRENT_SESSIONS:
                        sql = adapt_sql("""
                            SELECT session_id FROM active_sessions
                            WHERE user_id = ? AND is_active = 1
                            ORDER BY last_activity ASC
                            LIMIT 1
                        """)
                        c.execute(sql, (user_id,))
                        oldest_session = c.fetchone()

                        if oldest_session:
                            SessionSecurity.force_logout_session(
                                oldest_session[0],
                                "超过最大并发会话数限制"
                            )

                    # 3. 创建新会话（在事务中）
                    current_time = time.time()
                    sql = adapt_sql("""
                        INSERT INTO active_sessions
                        (session_id, user_id, created_at, last_activity,
                         ip_address, user_agent, is_active)
                        VALUES (?, ?, ?, ?, ?, ?, 1)
                    """)
                    c.execute(
                        sql, (session_id, user_id, current_time,
                              current_time, ip_address, user_agent))
                    conn.commit()

                    return True, "会话创建成功"
        except (
            OSError, RuntimeError, ValueError, TypeError, AttributeError
        ) as e:
            # 数据库操作错误或其他运行时错误
            return False, f"会话创建失败: {str(e)}"

    @staticmethod
    def update_session_activity_atomic(session_id: str) -> bool:
        """
        原子性地更新会话活动时间

        Args:
            session_id: 会话ID

        Returns:
            是否成功
        """
        lock_key = f"session_update_{session_id}"
        lock = DistributedLock(lock_key, timeout=2, redis_available=True)

        try:
            with lock.acquire():  # type: ignore[misc]
                with get_db_connection() as (conn, c):
                    from db_adapter import adapt_sql
                    current_time = time.time()
                    sql = adapt_sql("""
                        UPDATE active_sessions
                        SET last_activity = ?
                        WHERE session_id = ? AND is_active = 1
                    """)
                    c.execute(sql, (current_time, session_id))
                    conn.commit()
                    return True
        except (
            OSError, RuntimeError, ValueError, TypeError, AttributeError
        ):
            # 数据库操作错误或其他运行时错误
            return False
