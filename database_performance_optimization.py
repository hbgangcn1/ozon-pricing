#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据库性能优化兼容层

为测试用例提供 `DatabaseConnectionPool` 与 `DatabaseCache` 接口，
内部复用现有的连接池与缓存实现，避免重复代码。
"""

from __future__ import annotations

import time
import threading
from contextlib import contextmanager
from typing import Any, Dict, Optional

import sqlite3

try:
    from enhanced_connection_manager import ConnectionPool
except ImportError:  # pragma: no cover
    ConnectionPool = None  # type: ignore


class DatabaseConnectionPool:
    """为测试提供的简化连接池接口。

    参数名称与测试保持一致，但内部映射到现有实现。
    """

    def __init__(
        self,
        db_path: str,
        pool_size: int = 10,
        max_overflow: int = 0,
        connection_timeout: int = 30,
    ) -> None:
        self.db_path = db_path
        self.pool_size = pool_size
        self.max_overflow = max_overflow  # 为接口兼容保留
        self.connection_timeout = connection_timeout

        if ConnectionPool is not None:
            self._pool = ConnectionPool(
                db_path=db_path,
                max_connections=pool_size,
                connection_timeout=connection_timeout,
            )
        else:
            self._pool = None

        self._fallback_lock = threading.Lock()
        self._fallback_connections = []  # 退化模式下的连接集合

    @contextmanager
    def get_connection(self):
        """返回上下文管理器，测试将使用 with 语法。"""
        conn: Optional[sqlite3.Connection] = None
        try:
            if self._pool is not None:
                conn = self._pool.acquire()
            else:
                # 退化为直接创建连接
                conn = sqlite3.connect(
                    self.db_path, timeout=self.connection_timeout
                )
                with self._fallback_lock:
                    self._fallback_connections.append(conn)
            yield conn
        finally:
            if conn is not None:
                try:
                    if self._pool is not None:
                        self._pool.release(conn)
                    else:
                        conn.close()
                except (sqlite3.Error, AttributeError, OSError):
                    try:
                        conn.close()
                    except (sqlite3.Error, AttributeError, OSError):
                        pass

    def close(self) -> None:
        if self._pool is not None:
            try:
                self._pool.close_all()
            except (sqlite3.Error, AttributeError, OSError):
                pass
        else:
            with self._fallback_lock:
                for c in self._fallback_connections:
                    try:
                        c.close()
                    except (sqlite3.Error, AttributeError, OSError):
                        pass
                self._fallback_connections.clear()


class DatabaseCache:
    """为测试提供的轻量级内存缓存（带TTL与统计）。"""

    def __init__(self, max_size: int = 100, ttl: int = 60) -> None:
        self.max_size = max_size
        self.ttl = ttl
        self._cache: Dict[str, Any] = {}
        self._exp: Dict[str, float] = {}
        self._hits = 0
        self._misses = 0
        self._lock = threading.RLock()

    def get(self, key: str) -> Optional[Any]:
        now = time.time()
        with self._lock:
            if key in self._cache and self._exp.get(key, 0) > now:
                self._hits += 1
                return self._cache[key]
            # 过期或不存在
            if key in self._cache:
                del self._cache[key]
                self._exp.pop(key, None)
            self._misses += 1
            return None

    def set(self, key: str, value: Any) -> bool:
        with self._lock:
            if len(self._cache) >= self.max_size and key not in self._cache:
                # 简单移除最早过期或任意一个键
                victim = None
                oldest = float("inf")
                for k, exp in self._exp.items():
                    if exp < oldest:
                        oldest = exp
                        victim = k
                if victim is None and self._cache:
                    victim = next(iter(self._cache.keys()))
                if victim is not None:
                    self._cache.pop(victim, None)
                    self._exp.pop(victim, None)

            self._cache[key] = value
            self._exp[key] = time.time() + self.ttl
            return True

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            total = self._hits + self._misses
            hit_rate = (self._hits / total) if total > 0 else 0.0
            return {
                'cache_size': len(self._cache),
                'hit_rate': hit_rate,
                'hits': self._hits,
                'misses': self._misses,
                'ttl': self.ttl,
                'max_size': self.max_size,
            }
