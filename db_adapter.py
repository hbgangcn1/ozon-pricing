# -*- coding: utf-8 -*-
"""
数据库适配器
提供PostgreSQL数据库接口
"""

import re
from contextlib import contextmanager
from typing import Any, Optional, TYPE_CHECKING, cast
from db_config import POSTGRES_CONFIG

# 尝试导入psycopg2（PostgreSQL驱动）
try:
    import psycopg2  # type: ignore
    import psycopg2.extras  # type: ignore
    from psycopg2 import pool  # type: ignore
    from psycopg2 import InterfaceError  # type: ignore

    _psycopg2_available = True
except ImportError:
    _psycopg2_available = False
    if TYPE_CHECKING:
        # 仅用于类型检查
        from psycopg2 import pool, InterfaceError  # type: ignore
    else:
        psycopg2 = None
        pool = None  # type: ignore
        InterfaceError = ConnectionError  # 回退到通用异常

PSYCOPG2_AVAILABLE = _psycopg2_available

# 全局连接池
_connection_pool: Optional[Any] = None

# 导入连接计数函数（在模块级别导入，避免循环导入）
try:
    from db_utils import (
        _increment_connection_counter,  # pyright: ignore[reportPrivateUsage]
        _decrement_connection_counter,  # pyright: ignore[reportPrivateUsage]
    )
except ImportError:
    # 如果导入失败，尝试使用相对导入
    try:
        from .db_utils import (
            _increment_connection_counter,  # pyright: ignore[reportPrivateUsage]
            _decrement_connection_counter,  # pyright: ignore[reportPrivateUsage]
        )
    except ImportError:
        # 如果都失败，定义占位函数（向后兼容）
        # 这些函数应该不做任何操作，但保持函数签名一致
        def _increment_connection_counter() -> int:
            """占位函数：增加连接计数"""
            return 0

        def _decrement_connection_counter() -> int:
            """占位函数：减少连接计数"""
            return 0


if pool is not None:
    _pool_error_type = getattr(pool, "PoolError", Exception)
else:

    class _DummyPoolError(Exception):
        """占位PoolError，确保异常捕获范围有限"""

        pass

    _pool_error_type = _DummyPoolError

POOL_ERROR_TYPE = _pool_error_type


def init_connection_pool():
    """初始化连接池"""
    global _connection_pool

    if not PSYCOPG2_AVAILABLE:
        raise RuntimeError("PostgreSQL驱动未安装，请运行: pip install psycopg2-binary")

    if _connection_pool is None:
        # 类型检查：确保pool不为None
        if pool is None:
            raise RuntimeError("PostgreSQL pool模块未正确加载")

        # 在测试环境中增加连接池大小，避免连接池耗尽
        import os

        is_test = os.getenv("PYTEST_CURRENT_TEST") is not None
        # 进一步增加连接池大小，确保测试不会耗尽连接
        min_conn = 30 if is_test else 5
        max_conn = 300 if is_test else 20

        _connection_pool = pool.ThreadedConnectionPool(
            minconn=min_conn,  # 最小连接数
            maxconn=max_conn,  # 最大连接数（测试时增加到100）
            host=POSTGRES_CONFIG["host"],
            port=POSTGRES_CONFIG["port"],
            database=POSTGRES_CONFIG["database"],
            user=POSTGRES_CONFIG["user"],
            password=POSTGRES_CONFIG["password"],
            connect_timeout=30,  # 连接超时30秒
            options="-c statement_timeout=30000",  # 语句超时30秒
        )


def close_connection_pool():
    """关闭连接池"""
    global _connection_pool

    if _connection_pool is not None:
        # 类型检查：在 None 检查后，_connection_pool 不为 None
        connection_pool = cast(Any, _connection_pool)
        connection_pool.closeall()
        _connection_pool = None


@contextmanager
def get_db_connection():
    """
    获取数据库连接（上下文管理器）

    Returns:
        Tuple[connection, cursor]
    """
    if not PSYCOPG2_AVAILABLE:
        raise RuntimeError("PostgreSQL驱动未安装，请运行: pip install psycopg2-binary")

    init_connection_pool()

    if _connection_pool is None:
        raise RuntimeError("连接池未正确初始化")

    try:
        _increment_connection_counter()
    except Exception as e:
        print(f"警告：连接计数增加失败: {e}")
        import traceback

        traceback.print_exc()

    conn = None
    cursor = None
    try:
        conn = _connection_pool.getconn()
        cursor = conn.cursor()

        try:
            yield conn, cursor
            conn_is_open = (
                conn is not None and hasattr(conn, "closed") and conn.closed == 0
            )
            if conn_is_open:
                try:
                    conn.commit()
                except (
                    AttributeError,
                    RuntimeError,
                    OSError,
                    ConnectionError,
                ) as commit_err:
                    import os

                    if not os.getenv("PYTEST_CURRENT_TEST"):
                        print(f"警告：提交事务时连接已关闭: {commit_err}")
        except Exception as e:
            conn_is_open = (
                conn is not None and hasattr(conn, "closed") and conn.closed == 0
            )
            if conn_is_open:
                try:
                    conn.rollback()
                except (
                    AttributeError,
                    RuntimeError,
                    OSError,
                    ConnectionError,
                    InterfaceError,
                ) as rollback_err:
                    import os

                    if not os.getenv("PYTEST_CURRENT_TEST"):
                        print(f"警告：回滚事务时连接已关闭: {rollback_err}")
            raise e
    finally:
        if cursor is not None:
            try:
                cursor.close()
            except (AttributeError, RuntimeError, OSError):
                pass

        if conn is not None:
            try:
                if conn.closed == 0:
                    _connection_pool.putconn(conn)
                else:
                    pass
            except POOL_ERROR_TYPE:
                try:
                    if hasattr(conn, "close"):
                        conn.close()
                except (AttributeError, RuntimeError, OSError, ConnectionError):
                    pass
            except (
                AttributeError,
                RuntimeError,
                OSError,
                ConnectionError,
                TypeError,
            ) as e:
                try:
                    if hasattr(conn, "close"):
                        conn.close()
                except (
                    AttributeError,
                    RuntimeError,
                    OSError,
                    ConnectionError,
                    TypeError,
                ):
                    pass
                import os

                if os.getenv("PYTEST_CURRENT_TEST"):
                    pass
                else:
                    print(f"警告：无法将连接放回池中: {e}")

        try:
            _decrement_connection_counter()
        except (AttributeError, RuntimeError, TypeError):
            pass


def adapt_sql(sql: str) -> str:
    """
    适配SQL语句，处理SQLite到PostgreSQL的语法转换

    Args:
        sql: 原始SQL语句

    Returns:
        适配后的SQL语句
    """
    sql = re.sub(
        r"INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT",
        "SERIAL PRIMARY KEY",
        sql,
        flags=re.IGNORECASE,
    )
    sql = re.sub(r"\s+AUTOINCREMENT", "", sql, flags=re.IGNORECASE)
    sql = re.sub(
        r"INTEGER\s+PRIMARY\s+KEY(?!\s+\w)",
        "SERIAL PRIMARY KEY",
        sql,
        flags=re.IGNORECASE,
    )
    sql = sql.replace("datetime('now')", "CURRENT_TIMESTAMP")
    sql = re.sub(
        r"strftime\(['\"]%s['\"],\s*['\"]now['\"]\)",
        "extract(epoch from now())",
        sql,
        flags=re.IGNORECASE,
    )
    sql = sql.replace("BOOLEAN", "BOOLEAN")

    if re.search(r"INSERT\s+OR\s+IGNORE", sql, re.IGNORECASE):
        sql = re.sub(r"INSERT\s+OR\s+IGNORE", "INSERT", sql, flags=re.IGNORECASE)
        sql = sql.rstrip(";") + " ON CONFLICT DO NOTHING"

    if "INSERT OR REPLACE" in sql:
        match = re.search(
            r"INSERT OR REPLACE INTO\s+(\w+)\s*\(([^)]+)\)", sql, re.IGNORECASE
        )
        if match:
            table_name = match.group(1)
            columns = match.group(2)
            if "identifier" in columns:
                pk_col = "identifier"
            elif "config_key" in columns:
                pk_col = "config_key"
            elif "cache_key" in columns:
                pk_col = "cache_key"
            elif "id" in columns:
                pk_col = "id"
            else:
                pk_col = columns.split(",")[0].strip()
            update_cols = [
                col.strip() for col in columns.split(",") if col.strip() != pk_col
            ]
            update_set = ", ".join([f"{col}=EXCLUDED.{col}" for col in update_cols])
            sql = re.sub(
                r"INSERT OR REPLACE INTO\s+\w+\s*\([^)]+\)\s*VALUES",
                f"INSERT INTO {table_name} ({columns}) VALUES",
                sql,
                flags=re.IGNORECASE,
            )
            sql = (
                sql.rstrip(";") + f" ON CONFLICT ({pk_col}) DO UPDATE SET {update_set}"
            )

    sql = re.sub(
        r"datetime\s*\(\s*(\?|%\w+)\s*,\s*['\"]unixepoch['\"]\s*\)",
        r"to_timestamp(\1)",
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    )
    sql = re.sub(
        r"datetime\s*\(\s*(\?|%\w+)\s*,\s*unixepoch\s*\)",
        r"to_timestamp(\1)",
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    )

    sql = sql.replace("?", "%s")

    sql = re.sub(
        r"\b(success|is_test_user)\s*=\s*1\b",
        r"\1 = TRUE",
        sql,
        flags=re.IGNORECASE,
    )
    sql = re.sub(
        r"\b(success|is_test_user)\s*=\s*0\b",
        r"\1 = FALSE",
        sql,
        flags=re.IGNORECASE,
    )

    return sql


def get_placeholder() -> str:
    """获取SQL占位符"""
    return "%s"


def adapt_placeholders(sql: str, param_count: int) -> str:
    """
    适配SQL占位符

    Args:
        sql: SQL语句
        param_count: 参数数量

    Returns:
        适配后的SQL
    """
    placeholder_count = sql.count("?")
    if placeholder_count != param_count:
        raise ValueError(
            f"占位符数量({placeholder_count})与参数数量({param_count})不匹配"
        )
    return sql.replace("?", "%s")


def get_last_insert_id(cursor) -> Optional[int]:
    """获取最后插入的ID"""
    cursor.execute("SELECT lastval()")
    result = cursor.fetchone()
    return result[0] if result else None
