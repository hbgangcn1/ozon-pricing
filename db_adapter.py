# -*- coding: utf-8 -*-
"""
数据库适配器
提供统一的数据库接口，支持SQLite和PostgreSQL
"""

import re
import sqlite3
from contextlib import contextmanager
from typing import Any, Optional, TYPE_CHECKING
from db_config import DB_TYPE, SQLITE_DB_PATH, POSTGRES_CONFIG

# 尝试导入psycopg2（PostgreSQL驱动）
try:
    import psycopg2  # type: ignore
    import psycopg2.extras  # type: ignore
    from psycopg2 import pool  # type: ignore
    from psycopg2 import InterfaceError  # type: ignore
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    if TYPE_CHECKING:
        # 仅用于类型检查
        from psycopg2 import pool, InterfaceError  # type: ignore
    else:
        psycopg2 = None
        pool = None  # type: ignore
        InterfaceError = ConnectionError  # 回退到通用异常

# 全局连接池
_connection_pool: Optional[Any] = None

# 导入连接计数函数（在模块级别导入，避免循环导入）
try:
    from db_utils import (
        _increment_connection_counter,
        _decrement_connection_counter
    )
except ImportError:
    # 如果导入失败，尝试使用相对导入
    try:
        from .db_utils import (
            _increment_connection_counter,
            _decrement_connection_counter
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
    POOL_ERROR_TYPE = getattr(pool, 'PoolError', Exception)
else:
    class _DummyPoolError(Exception):
        """占位PoolError，确保异常捕获范围有限"""
        pass

    POOL_ERROR_TYPE = _DummyPoolError


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

            # 在测试环境中增加连接池大小，避免连接池耗尽
            import os
            is_test = os.getenv('PYTEST_CURRENT_TEST') is not None
            # 进一步增加连接池大小，确保测试不会耗尽连接
            min_conn = 30 if is_test else 5
            max_conn = 300 if is_test else 20

            _connection_pool = pool.ThreadedConnectionPool(
                minconn=min_conn,  # 最小连接数
                maxconn=max_conn,  # 最大连接数（测试时增加到100）
                host=POSTGRES_CONFIG['host'],
                port=POSTGRES_CONFIG['port'],
                database=POSTGRES_CONFIG['database'],
                user=POSTGRES_CONFIG['user'],
                password=POSTGRES_CONFIG['password'],
                connect_timeout=30,  # 连接超时30秒
                options='-c statement_timeout=30000'  # 语句超时30秒
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

        # 增加连接计数（用于连接监控）
        try:
            _increment_connection_counter()
        except Exception as e:
            # 如果计数失败，记录但不阻止连接获取
            print(f"警告：连接计数增加失败: {e}")
            import traceback
            traceback.print_exc()

        # psycopg2的getconn默认阻塞等待，直到有可用连接
        # 如果连接池已满，会一直等待，这符合连接池的正常行为
        conn = None
        cursor = None
        try:
            conn = _connection_pool.getconn()
            cursor = conn.cursor()

            try:
                yield conn, cursor
                # 在提交前检查连接状态
                conn_is_open = (
                    conn is not None and
                    hasattr(conn, 'closed') and
                    conn.closed == 0
                )
                if conn_is_open:
                    try:
                        conn.commit()
                    except (AttributeError, RuntimeError, OSError,
                            ConnectionError) as commit_err:
                        # 连接可能在提交时关闭，记录但不阻止清理
                        import os
                        if not os.getenv('PYTEST_CURRENT_TEST'):
                            print(f"警告：提交事务时连接已关闭: {commit_err}")
            except Exception as e:
                # 在回滚前检查连接状态
                conn_is_open = (
                    conn is not None and
                    hasattr(conn, 'closed') and
                    conn.closed == 0
                )
                if conn_is_open:
                    try:
                        conn.rollback()
                    except (AttributeError, RuntimeError, OSError,
                            ConnectionError, InterfaceError) as rollback_err:
                        # 连接可能在回滚时关闭，记录但不阻止异常传播
                        import os
                        if not os.getenv('PYTEST_CURRENT_TEST'):
                            print(f"警告：回滚事务时连接已关闭: {rollback_err}")
                raise e
        finally:
            # 确保cursor被关闭
            if cursor is not None:
                try:
                    cursor.close()
                except (AttributeError, RuntimeError, OSError):
                    pass  # 忽略cursor关闭错误

            # 检查连接状态，只有在连接有效时才放回池中
            if conn is not None:
                try:
                    # 检查连接是否仍然打开
                    if conn.closed == 0:  # 0表示连接打开
                        _connection_pool.putconn(conn)
                    else:
                        # 连接已关闭，丢弃它
                        pass
                except POOL_ERROR_TYPE:
                    try:
                        if hasattr(conn, 'close'):
                            conn.close()
                    except (AttributeError, RuntimeError, OSError,
                            ConnectionError):
                        pass
                except (AttributeError, RuntimeError, OSError,
                        ConnectionError, TypeError) as e:
                    # 如果putconn失败（比如连接已损坏），尝试强制关闭连接
                    try:
                        if hasattr(conn, 'close'):
                            conn.close()
                    except (AttributeError, RuntimeError, OSError,
                            ConnectionError, TypeError):
                        # 关闭连接时可能出现的异常：
                        # - AttributeError: 连接对象没有close方法
                        # - RuntimeError: 连接已关闭或处于无效状态
                        # - OSError: 底层网络或文件系统错误
                        # - ConnectionError: 连接相关的错误
                        # - TypeError: 连接对象类型错误
                        # 这些异常都应该被静默处理，因为这是清理代码
                        pass
                    # 记录错误但不抛出异常，这样不会影响其他清理工作
                    # 在测试环境中减少输出噪音
                    import os
                    if os.getenv('PYTEST_CURRENT_TEST'):
                        # 测试环境中静默处理
                        pass
                    else:
                        print(f"警告：无法将连接放回池中: {e}")

            # 减少连接计数（确保总是执行，即使前面的清理失败）
            try:
                _decrement_connection_counter()
            except (AttributeError, RuntimeError, TypeError):
                pass  # 忽略计数错误

    else:
        # SQLite连接（现有逻辑）
        # 增加连接计数（用于连接监控）
        try:
            _increment_connection_counter()
        except Exception as e:
            # 如果计数失败，记录但不阻止连接获取
            print(f"警告：连接计数增加失败: {e}")
            import traceback
            traceback.print_exc()

        # SQLite连接：使用超时设置以处理并发访问
        # timeout参数允许在数据库锁定时等待（默认5秒）
        conn = sqlite3.connect(
            SQLITE_DB_PATH,
            check_same_thread=False,
            timeout=10.0  # 增加超时时间以处理并发访问
        )
        # 启用性能优化和外键约束
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA busy_timeout=5000")
            conn.execute("PRAGMA foreign_keys=ON")
        except sqlite3.Error:
            pass

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
            # 减少连接计数
            try:
                _decrement_connection_counter()
            except Exception as e:
                print(f"警告：连接计数减少失败: {e}")


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
        # 注意：替换顺序很重要，必须先替换完整的模式，再替换部分模式
        # 使用正则表达式处理多行SQL中的AUTOINCREMENT
        # 先替换完整的 INTEGER PRIMARY KEY AUTOINCREMENT
        sql = re.sub(
            r'INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT',
            'SERIAL PRIMARY KEY',
            sql,
            flags=re.IGNORECASE
        )
        # 然后替换单独的 AUTOINCREMENT（在已处理过的SQL中不应该存在，但作为保险）
        sql = re.sub(r'\s+AUTOINCREMENT', '', sql, flags=re.IGNORECASE)
        # 最后替换 INTEGER PRIMARY KEY（不包含AUTOINCREMENT的）
        sql = re.sub(
            r'INTEGER\s+PRIMARY\s+KEY(?!\s+\w)',  # 后面不跟其他单词
            'SERIAL PRIMARY KEY',
            sql,
            flags=re.IGNORECASE
        )
        sql = sql.replace('datetime(\'now\')', 'CURRENT_TIMESTAMP')
        # 替换strftime('%s', 'now')，包括在DEFAULT子句中的情况
        sql = re.sub(
            r"strftime\(['\"]%s['\"],\s*['\"]now['\"]\)",
            'extract(epoch from now())',
            sql,
            flags=re.IGNORECASE
        )
        sql = sql.replace('BOOLEAN', 'BOOLEAN')  # PostgreSQL原生支持

        # 转换SQLite的datetime函数为PostgreSQL语法（必须在占位符转换前）
        # 处理INSERT OR IGNORE -> PostgreSQL ON CONFLICT语法
        # 直接使用无目标的 ON CONFLICT DO NOTHING，避免依赖特定约束
        if re.search(r'INSERT\s+OR\s+IGNORE', sql, re.IGNORECASE):
            sql = re.sub(
                r'INSERT\s+OR\s+IGNORE',
                'INSERT',
                sql,
                flags=re.IGNORECASE
            )
            sql = sql.rstrip(';') + ' ON CONFLICT DO NOTHING'

        # 处理INSERT OR REPLACE -> PostgreSQL ON CONFLICT语法
        if 'INSERT OR REPLACE' in sql:
            match = re.search(
                r"INSERT OR REPLACE INTO\s+(\w+)\s*\(([^)]+)\)",
                sql, re.IGNORECASE
            )
            if match:
                table_name = match.group(1)
                columns = match.group(2)
                # 按优先级确定主键列
                if 'identifier' in columns:
                    pk_col = 'identifier'
                elif 'config_key' in columns:
                    pk_col = 'config_key'
                elif 'cache_key' in columns:
                    pk_col = 'cache_key'
                elif 'id' in columns:
                    pk_col = 'id'
                else:
                    # 默认使用第一列
                    pk_col = columns.split(',')[0].strip()
                # 生成UPDATE子句
                update_cols = [col.strip() for col in columns.split(',')
                               if col.strip() != pk_col]
                update_set = ', '.join([f'{col}=EXCLUDED.{col}'
                                       for col in update_cols])
                # 替换整个语句
                sql = re.sub(
                    r'INSERT OR REPLACE INTO\s+\w+\s*\([^)]+\)\s*VALUES',
                    f'INSERT INTO {table_name} ({columns}) VALUES',
                    sql, flags=re.IGNORECASE
                )
                sql = (sql.rstrip(';') +
                       f' ON CONFLICT ({pk_col}) DO UPDATE SET '
                       f'{update_set}')

        # 转换SQLite的datetime函数为PostgreSQL语法
        # datetime(?, 'unixepoch') -> to_timestamp(?)
        # 使用re.DOTALL标志以匹配多行SQL（.可以匹配换行符）
        # 匹配模式：datetime(占位符, 空白字符 'unixepoch' 或 "unixepoch")
        sql = re.sub(
            r"datetime\s*\(\s*(\?|%\w+)\s*,\s*['\"]unixepoch['\"]\s*\)",
            r"to_timestamp(\1)",
            sql,
            flags=re.IGNORECASE | re.DOTALL
        )
        # datetime(?, unixepoch) -> to_timestamp(?) (处理不带引号的情况)
        sql = re.sub(
            r"datetime\s*\(\s*(\?|%\w+)\s*,\s*unixepoch\s*\)",
            r"to_timestamp(\1)",
            sql,
            flags=re.IGNORECASE | re.DOTALL
        )

        # 先处理INSERT VALUES中的布尔值（在占位符转换之前）
        # 因为占位符转换后，字面量1/0可能被误转换
        # 使用更宽松的匹配，因为SQL可能包含换行符
        sql_upper = sql.upper()
        if ('ACTIVE_SESSIONS' in sql_upper and 'VALUES' in sql_upper and
                'INSERT' in sql_upper):
            # 匹配 VALUES (...) 中最后一个单独的 1（可能是is_active）
            # 需要匹配多种情况：
            # 1. VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
            # 2. VALUES (..., 1)
            # 使用更精确的模式：匹配 VALUES 子句中最后的 , 1) 或 , 0)
            # 但要确保不是其他数字的一部分
            # 使用DOTALL标志以匹配可能包含换行符的SQL
            # \s* 匹配零个或多个空白字符，可以同时处理有空格和没空格的情况
            sql = re.sub(
                r',\s*1\s*\)(?=\s*(?:$|;|\n|RETURNING|ON CONFLICT))',
                ', TRUE)',
                sql,
                flags=re.IGNORECASE | re.MULTILINE | re.DOTALL
            )
            # 同样处理0
            sql = re.sub(
                r',\s*0\s*\)(?=\s*(?:$|;|\n|RETURNING|ON CONFLICT))',
                ', FALSE)',
                sql,
                flags=re.IGNORECASE | re.MULTILINE | re.DOTALL
            )

        # 转换占位符 ? 为 %s
        sql = sql.replace('?', '%s')

        # 转换布尔值比较：SQLite使用 = 1，PostgreSQL使用 = TRUE
        # 注意：is_test_data 是 INTEGER 类型，不能转换为 TRUE/FALSE
        # 处理 is_active = 1 -> is_active = TRUE
        sql = re.sub(
            r'\bis_active\s*=\s*1\b',
            'is_active = TRUE',
            sql,
            flags=re.IGNORECASE
        )
        # 处理 is_active = 0 -> is_active = FALSE
        sql = re.sub(
            r'\bis_active\s*=\s*0\b',
            'is_active = FALSE',
            sql,
            flags=re.IGNORECASE
        )
        # 处理其他布尔字段的类似比较（不包括 is_test_data）
        # is_test_data 是 INTEGER 类型，应该保持 = 1 或 = 0
        sql = re.sub(
            r'\b(success|is_test_user|is_active)\s*=\s*1\b',
            r'\1 = TRUE',
            sql,
            flags=re.IGNORECASE
        )
        sql = re.sub(
            r'\b(success|is_test_user|is_active)\s*=\s*0\b',
            r'\1 = FALSE',
            sql,
            flags=re.IGNORECASE
        )
    else:
        # SQLite模式：将可能存在的%s占位符转换为?
        # 这处理了某些SQL语句可能已经包含%s的情况
        sql = sql.replace('%s', '?')

        # SQLite模式：将PostgreSQL的布尔值语法转换为SQLite语法
        # 处理 is_active = TRUE -> is_active = 1
        sql = re.sub(
            r'\bis_active\s*=\s*TRUE\b',
            'is_active = 1',
            sql,
            flags=re.IGNORECASE
        )
        # 处理 is_active = FALSE -> is_active = 0
        sql = re.sub(
            r'\bis_active\s*=\s*FALSE\b',
            'is_active = 0',
            sql,
            flags=re.IGNORECASE
        )

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
    # 验证占位符数量
    placeholder_count = sql.count('?')
    if placeholder_count != param_count:
        raise ValueError(
            f"占位符数量({placeholder_count})与参数数量"
            f"({param_count})不匹配"
        )

    if DB_TYPE == 'postgresql':
        # psycopg2使用%s占位符，不需要转换
        # 只需确保SQL中没有?
        result = sql.replace('?', '%s')
        return result
    return sql


def get_last_insert_id(cursor) -> Optional[int]:
    """获取最后插入的ID"""
    if DB_TYPE == 'postgresql':
        # PostgreSQL需要先执行查询获取lastval()
        cursor.execute("SELECT lastval()")
        result = cursor.fetchone()
        return result[0] if result else None
    else:
        return cursor.lastrowid
