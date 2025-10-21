# -*- coding: utf-8 -*-
"""
数据库适配器
提供统一的数据库接口，支持SQLite和PostgreSQL
"""

import sqlite3
from contextlib import contextmanager
from typing import Any, Optional, TYPE_CHECKING
from db_config import DB_TYPE, SQLITE_DB_PATH, POSTGRES_CONFIG

# 尝试导入psycopg2（PostgreSQL驱动）
try:
    import psycopg2  # type: ignore
    import psycopg2.extras  # type: ignore
    from psycopg2 import pool  # type: ignore
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    if TYPE_CHECKING:
        # 仅用于类型检查
        from psycopg2 import pool  # type: ignore
    else:
        psycopg2 = None
        pool = None  # type: ignore

# 全局连接池
_connection_pool: Optional[Any] = None


def init_connection_pool():
    """初始化连接池"""
    global _connection_pool

    if DB_TYPE == 'postgresql':
        if not PSYCOPG2_AVAILABLE:
            raise RuntimeError(
                "PostgreSQL驱动未安装，请运行: pip install psycopg2-binary"
            )

        if _connection_pool is None:
            # 类型检查：确保pool不为None
            if pool is None:
                raise RuntimeError("PostgreSQL pool模块未正确加载")

            _connection_pool = pool.ThreadedConnectionPool(
                minconn=5,
                maxconn=20,
                host=POSTGRES_CONFIG['host'],
                port=POSTGRES_CONFIG['port'],
                database=POSTGRES_CONFIG['database'],
                user=POSTGRES_CONFIG['user'],
                password=POSTGRES_CONFIG['password']
            )


def close_connection_pool():
    """关闭连接池"""
    global _connection_pool

    if _connection_pool is not None:
        _connection_pool.closeall()
        _connection_pool = None


@contextmanager
def get_db_connection():
    """
    获取数据库连接（上下文管理器）
    自动处理SQLite和PostgreSQL的差异

    Returns:
        Tuple[connection, cursor]
    """
    if DB_TYPE == 'postgresql':
        # PostgreSQL连接
        if not PSYCOPG2_AVAILABLE:
            raise RuntimeError(
                "PostgreSQL驱动未安装，请运行: pip install psycopg2-binary"
            )

        init_connection_pool()

        # 类型检查：确保连接池已初始化
        if _connection_pool is None:
            raise RuntimeError("连接池未正确初始化")

        conn = _connection_pool.getconn()
        cursor = conn.cursor()

        try:
            yield conn, cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            _connection_pool.putconn(conn)

    else:
        # SQLite连接（现有逻辑）
        conn = sqlite3.connect(SQLITE_DB_PATH, check_same_thread=False)
        cursor = conn.cursor()

        try:
            yield conn, cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()


def adapt_sql(sql: str) -> str:
    """
    适配SQL语句，处理SQLite和PostgreSQL的语法差异

    Args:
        sql: 原始SQL语句

    Returns:
        适配后的SQL语句
    """
    if DB_TYPE == 'postgresql':
        # 替换SQLite特有语法为PostgreSQL语法
        sql = sql.replace('INTEGER PRIMARY KEY AUTOINCREMENT', 'SERIAL PRIMARY KEY')  # noqa: E501
        sql = sql.replace('INTEGER PRIMARY KEY', 'SERIAL PRIMARY KEY')
        sql = sql.replace('AUTOINCREMENT', '')
        sql = sql.replace('datetime(\'now\')', 'CURRENT_TIMESTAMP')
        sql = sql.replace('strftime(\'%s\', \'now\')', 'extract(epoch from now())')  # noqa: E501
        sql = sql.replace('BOOLEAN', 'BOOLEAN')  # PostgreSQL原生支持
        sql = sql.replace('INSERT OR IGNORE', 'INSERT ... ON CONFLICT DO NOTHING')  # noqa: E501
        sql = sql.replace('INSERT OR REPLACE', 'INSERT ... ON CONFLICT DO UPDATE')  # noqa: E501

    return sql


def get_placeholder() -> str:
    """获取SQL占位符"""
    if DB_TYPE == 'postgresql':
        return '%s'  # PostgreSQL使用%s
    else:
        return '?'  # SQLite使用?


def adapt_placeholders(sql: str, param_count: int) -> str:
    """
    适配SQL占位符

    Args:
        sql: SQL语句
        param_count: 参数数量

    Returns:
        适配后的SQL
    """
    if DB_TYPE == 'postgresql':
        # 将?替换为$1, $2, $3...
        result = sql
        for i in range(param_count, 0, -1):
            result = result.replace('?', f'${i}', 1)
        return result
    return sql


def get_last_insert_id(cursor) -> Optional[int]:
    """获取最后插入的ID"""
    if DB_TYPE == 'postgresql':
        return cursor.fetchone()[0] if cursor.rowcount > 0 else None
    else:
        return cursor.lastrowid
