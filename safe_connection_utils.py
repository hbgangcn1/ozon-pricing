
"""
安全的数据库连接工具
提供自动关闭连接的包装函数
"""

import atexit
import weakref
from typing import Tuple, Optional
import sqlite3
from db_utils import get_db, _decrement_connection_counter

# 跟踪所有活跃连接
_active_connections = weakref.WeakSet()

def safe_get_db() -> Tuple[sqlite3.Connection, sqlite3.Cursor]:
    """
    安全的数据库连接获取函数
    自动注册清理函数，确保连接在程序退出时被关闭
    """
    conn, cursor = get_db()
    
    # 添加到活跃连接集合
    _active_connections.add(conn)
    
    # 注册清理函数
    def cleanup_connection():
        try:
            if conn and not conn.closed:
                conn.close()
                _decrement_connection_counter()
                _active_connections.discard(conn)
        except:
            pass
    
    # 使用弱引用避免循环引用
    weak_conn = weakref.ref(conn, lambda _: cleanup_connection())
    
    return conn, cursor

def close_all_connections():
    """关闭所有活跃连接"""
    for conn in list(_active_connections):
        try:
            if conn and not conn.closed:
                conn.close()
                _decrement_connection_counter()
        except:
            pass
    _active_connections.clear()

# 注册程序退出时的清理函数
atexit.register(close_all_connections)

def get_active_connection_count() -> int:
    """获取当前活跃连接数"""
    return len(_active_connections)
