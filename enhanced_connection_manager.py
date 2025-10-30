#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
增强数据库连接管理器
提供连接池、泄漏检测和自动修复功能
"""

import sqlite3
import threading
import time
from typing import Dict, List, Any, Optional
from contextlib import contextmanager
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ConnectionPool:
    """数据库连接池"""

    def __init__(
        self,
        db_path: str,
        max_connections: int = 10,
        connection_timeout: int = 30
    ):
        self.db_path = db_path
        self.max_connections = max_connections
        self.connection_timeout = connection_timeout
        self._pool: List[sqlite3.Connection] = []
        self._in_use: Dict[int, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._stats = {
            'total_created': 0,
            'total_used': 0,
            'total_leaked': 0,
            'total_recycled': 0
        }

    def acquire(self) -> sqlite3.Connection:
        """获取连接"""
        with self._lock:
            # 检查是否有可用连接
            if self._pool:
                db_conn = self._pool.pop()
                conn_id = id(db_conn)
            else:
                # 创建新连接
                db_conn = sqlite3.connect(
                    self.db_path,
                    timeout=self.connection_timeout
                )
                conn_id = id(db_conn)
                self._stats['total_created'] += 1

            # 记录连接状态
            self._in_use[conn_id] = {
                'conn': db_conn,
                'acquired_at': time.time(),
                'stack_trace': self._get_stack_trace()
            }
            self._stats['total_used'] += 1

            return db_conn

    def release(self, db_conn: sqlite3.Connection):
        """释放连接"""
        conn_id = id(db_conn)
        with self._lock:
            if conn_id in self._in_use:
                del self._in_use[conn_id]
                # 回收连接（如果池未满）
                if len(self._pool) < self.max_connections:
                    self._pool.append(db_conn)
                    self._stats['total_recycled'] += 1
                else:
                    db_conn.close()

    def detect_leaks(self) -> List[Dict[str, Any]]:
        """检测连接泄漏"""
        leaks = []
        current_time = time.time()
        with self._lock:
            for conn_id, info in self._in_use.items():
                age = current_time - info['acquired_at']
                if age > 300:  # 超过5分钟认为是泄漏
                    leaks.append({
                        'conn_id': conn_id,
                        'age': age,
                        'stack_trace': info['stack_trace']
                    })
                    self._stats['total_leaked'] += 1
        return leaks

    def cleanup_old_connections(self):
        """清理旧连接"""
        with self._lock:
            # 关闭超过30分钟未使用的池内连接
            connections_to_remove = []
            for pool_conn in self._pool:
                # 简单检查：如果连接被关闭，从池中移除
                try:
                    pool_conn.execute("SELECT 1")
                except sqlite3.ProgrammingError:
                    connections_to_remove.append(pool_conn)

            for pool_conn in connections_to_remove:
                self._pool.remove(pool_conn)
                try:
                    pool_conn.close()
                except (sqlite3.Error, AttributeError, OSError):
                    pass

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            return {
                'pool_size': len(self._pool),
                'in_use': len(self._in_use),
                'total_created': self._stats['total_created'],
                'total_used': self._stats['total_used'],
                'total_leaked': self._stats['total_leaked'],
                'total_recycled': self._stats['total_recycled']
            }

    def close_all(self):
        """关闭所有池内连接"""
        with self._lock:
            for pool_conn in self._pool:
                try:
                    pool_conn.close()
                except (sqlite3.Error, AttributeError, OSError):
                    pass
            self._pool.clear()

    @staticmethod
    def _get_stack_trace() -> str:
        """获取调用堆栈（简化版）"""
        import traceback
        try:
            stack = traceback.extract_stack()[:-2]
            return '\n'.join(traceback.format_list(stack))
        except (AttributeError, IndexError, ValueError):
            return 'Unable to get stack trace'


# 全局连接池实例
_global_pool: Optional[ConnectionPool] = None
_pool_lock = threading.Lock()


def init_connection_pool(db_path: str = 'pricing_system.db', **kwargs):
    """初始化全局连接池"""
    global _global_pool
    with _pool_lock:
        if _global_pool is None:
            _global_pool = ConnectionPool(db_path, **kwargs)
            logger.info(
                f"连接池初始化成功: max_connections={_global_pool.max_connections}"
            )
        return _global_pool


def get_connection_pool() -> ConnectionPool:
    """获取全局连接池"""
    if _global_pool is None:
        return init_connection_pool()
    return _global_pool


@contextmanager
def get_enhanced_db_connection():
    """
    获取增强的数据库连接（上下文管理器）
    自动处理连接的获取和释放
    """
    pool = get_connection_pool()
    db_connection = None
    try:
        db_connection = pool.acquire()
        db_cursor = db_connection.cursor()
        yield db_connection, db_cursor
    finally:
        if db_connection is not None:
            try:
                pool.release(db_connection)
            except (sqlite3.Error, AttributeError, OSError) as release_error:
                logger.error(f"释放连接时出错: {release_error}")
                try:
                    db_connection.close()
                except (sqlite3.Error, AttributeError, OSError):
                    pass


def get_connection_stats() -> Dict[str, Any]:
    """获取连接统计信息"""
    try:
        pool = get_connection_pool()
        pool_stats = pool.get_stats()
        # 检测泄漏
        leaks = pool.detect_leaks()
        pool_stats['leak_count'] = len(leaks)
        if leaks:
            logger.warning(
                f"检测到 {len(leaks)} 个连接泄漏"
            )
        # 清理旧连接
        pool.cleanup_old_connections()
        return pool_stats
    except Exception as stats_error:
        logger.error(f"获取连接统计信息失败: {stats_error}")
        return {'error': str(stats_error)}


def force_cleanup():
    """强制清理所有连接"""
    global _global_pool
    with _pool_lock:
        if _global_pool is not None:
            try:
                # 关闭所有池内连接
                _global_pool.close_all()
                logger.info("已强制清理所有池内连接")
                _global_pool = None
            except Exception as cleanup_error:
                logger.error(f"强制清理失败: {cleanup_error}")
                _global_pool = None


if __name__ == "__main__":
    # 测试连接池
    print("测试增强连接管理器...")

    # 初始化连接池
    init_connection_pool(max_connections=5)

    # 测试基本连接
    try:
        with get_enhanced_db_connection() as (conn, cursor):
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            print(f"连接测试成功: {result}")

        # 获取统计信息
        stats = get_connection_stats()
        print(f"连接池统计: {stats}")

        print("✅ 增强连接管理器测试通过")
    except Exception as e:
        print(f"❌ 测试失败: {e}")
