import os
import sqlite3
import streamlit as st
import hashlib
import bcrypt
import threading
import atexit
import queue
import json
import time
import signal
import sys
from datetime import datetime, date

# 确保模块别名一致（logistics.db_utils 与 db_utils 引用同一对象）
if __name__ == "db_utils":
    sys.modules.setdefault("logistics.db_utils", sys.modules[__name__])
elif __name__ == "logistics.db_utils":
    sys.modules.setdefault("db_utils", sys.modules[__name__])
from typing import Optional, Tuple, Dict, Any, Sequence, Mapping, cast

# 导入数据库适配函数（用于SQL语法适配）
try:
    from db_adapter import adapt_sql, get_placeholder
except ImportError:
    # 如果导入失败，定义占位函数（向后兼容）
    def adapt_sql(sql: str) -> str:
        return sql

    def get_placeholder() -> str:
        return "%s"


try:
    from .password_utils import validate_password_strength
except ImportError:  # pragma: no cover - fallback for non-package execution
    from password_utils import validate_password_strength


# 定义数据库异常类型（仅PostgreSQL）
def _get_db_exceptions():
    """获取数据库异常元组"""
    import psycopg2

    return psycopg2.Error, OSError, ValueError


try:
    import psycopg2  # pyright: ignore[reportUnusedImport]
except ImportError:
    psycopg2 = None  # type: ignore

DB_EXCEPTIONS = _get_db_exceptions()


def _is_postgresql_connection(conn):
    """
    检测连接对象是否为PostgreSQL连接
    """
    if conn is None:
        return False

    # 优先通过类型检测
    try:
        import psycopg2

        if isinstance(conn, psycopg2.extensions.connection):
            return True
    except (ImportError, AttributeError):
        pass

    # 检查连接对象的模块名
    conn_module = type(conn).__module__
    if "psycopg2" in conn_module or "postgresql" in conn_module.lower():
        return True

    # 检查连接对象的类名
    conn_class_name = type(conn).__name__.lower()
    if "postgres" in conn_class_name or "psycopg" in conn_class_name:
        return True

    # 对于其他情况，假设是PostgreSQL
    return True


def _subscription_expires_to_datetime(
    raw_value: Optional[Any],
) -> Optional[datetime]:
    """
    将 subscription_expires 原始值转换为 datetime 对象。

    支持整型/浮点型（Unix 时间戳）、仅包含数字的字符串、
    以及已经是 ISO 格式的字符串。转换失败时返回 None。
    """
    if raw_value in (None, "", 0):
        return None

    try:
        if isinstance(raw_value, (int, float)):
            return datetime.fromtimestamp(int(raw_value))

        cleaned = str(raw_value).strip()
        if cleaned == "":
            return None
        if cleaned.isdigit():
            return datetime.fromtimestamp(int(cleaned))
        return datetime.fromisoformat(cleaned)
    except (ValueError, TypeError, OSError):
        return None


def _serialize_subscription_expires(value: Optional[Any]) -> Optional[int]:
    """
    将外部传入的订阅到期值转换为 Unix 时间戳（秒）。

    支持 datetime、ISO 字符串、整型/浮点型或数字字符串。
    转换失败时返回 None。
    """
    if value in (None, "", 0):
        return None

    if isinstance(value, (int, float)):
        return int(value)

    if isinstance(value, datetime):
        return int(value.timestamp())

    cleaned = str(value).strip()
    if cleaned == "":
        return None
    try:
        return int(datetime.fromisoformat(cleaned).timestamp())
    except ValueError:
        try:
            return int(float(cleaned))
        except (ValueError, TypeError):
            return None


_TIMESTAMP_NUMERIC_PATTERN = r"^\d+(\.\d+)?$"
_TIMESTAMP_DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"
_TIMESTAMP_FULL_PATTERN = r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}$"
_TIMESTAMP_SHORT_PATTERN = r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}$"


def _build_safe_timestamp_expr(column: str) -> str:
    """生成兼容PostgreSQL的时间字段转换表达式"""
    return f"""
        COALESCE(
            CASE
                WHEN {column} IS NULL THEN NULL
                WHEN TRIM({column}::text) = '' THEN NULL
                WHEN TRIM({column}::text) ~ '{_TIMESTAMP_NUMERIC_PATTERN}'
                    THEN to_timestamp(TRIM({column}::text)::double precision)
                WHEN TRIM({column}::text) ~ '{_TIMESTAMP_DATE_PATTERN}'
                    THEN to_timestamp(TRIM({column}::text), 'YYYY-MM-DD')
                WHEN TRIM({column}::text) ~ '{_TIMESTAMP_FULL_PATTERN}'
                    THEN to_timestamp(
                        REPLACE(TRIM({column}::text), 'T', ' '),
                        'YYYY-MM-DD HH24:MI:SS'
                    )
                WHEN TRIM({column}::text) ~ '{_TIMESTAMP_SHORT_PATTERN}'
                    THEN to_timestamp(
                        REPLACE(TRIM({column}::text), 'T', ' '),
                        'YYYY-MM-DD HH24:MI'
                    )
                ELSE NULL
            END,
            to_timestamp(0)
        )
    """


def _safe_execute_fetchone(cursor, sql, params=None, conn=None) -> Any:
    """
    安全执行SQL查询并获取单行结果
    兼容PostgreSQL（cursor.execute返回None）和SQLite（返回cursor）

    Args:
        cursor: 数据库游标
        sql: SQL语句
        params: 参数（可选）
        conn: 数据库连接（可选，用于SQL适配）
    """
    # 高优先级安全改进：SQL注入检测
    # （仅在开发/测试环境启用，生产环境可选）
    try:
        import os

        if os.getenv("ENABLE_SQL_INJECTION_DETECTION", "false").lower() == "true":
            from sql_injection_protection import detect_sql_injection

            is_safe, warning = detect_sql_injection(sql, params)
            if not is_safe:
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(f"SQL注入检测警告: {warning}")
                logger.warning(f"SQL语句: {sql[:200]}...")
    except (ImportError, Exception):
        # 如果检测模块不可用或出错，继续执行（不阻断正常流程）
        pass

    # 如果提供了连接对象，先适配SQL
    if conn is not None:
        sql = _safe_adapt_sql(sql, conn)
    else:
        # 尝试从cursor获取connection（某些数据库驱动支持）
        try:
            conn = cursor.connection
            sql = _safe_adapt_sql(sql, conn)
        except AttributeError:
            # 如果无法获取连接，尝试通过cursor类型检测
            # 检查cursor类型来判断数据库类型
            cursor_module = type(cursor).__module__
            cursor_class_name = type(cursor).__name__.lower()
            # 检查是否为SQLite cursor（明确检测）
            if isinstance(cursor, sqlite3.Cursor):
                # SQLite cursor，保持?占位符
                pass  # sql保持不变
            elif "psycopg2" in cursor_module or "postgres" in cursor_class_name:
                # PostgreSQL cursor，需要转换占位符
                if "?" in sql:
                    sql = sql.replace("?", "%s")
            else:
                # 未知类型，尝试通过全局配置（但这不是最佳实践）
                try:
                    from db_config import DB_TYPE

                    if DB_TYPE == "postgresql" and "?" in sql:
                        sql = sql.replace("?", "%s")
                except (ImportError, AttributeError):
                    pass  # 保持原样

    if params:
        execute_result = cursor.execute(sql, params)
    else:
        execute_result = cursor.execute(sql)
    # PostgreSQL的execute返回None，SQLite返回cursor，但都可以调用fetchone
    return _safe_fetchone(cursor, execute_result)


def _safe_adapt_sql(sql: str, conn) -> str:
    """
    根据实际连接类型安全地适配SQL
    只有PostgreSQL连接才需要适配，SQLite连接使用原始SQL
    """
    import re

    # 首先明确检查是否为SQLite连接
    if isinstance(conn, sqlite3.Connection):
        # SQLite连接，确保使用?占位符，并将TRUE/FALSE转换为1/0
        # 需要将%s转换为?，但要避免替换字符串字面量中的%s
        # 使用更安全的方法：逐字符分析，跟踪是否在字符串中
        result = []
        in_single_quote = False
        in_double_quote = False
        i = 0

        while i < len(sql):
            char = sql[i]

            # 跟踪引号状态（考虑转义）
            if char == "'" and (i == 0 or sql[i - 1] != "\\"):
                in_single_quote = not in_single_quote
                result.append(char)
            elif char == '"' and (i == 0 or sql[i - 1] != "\\"):
                in_double_quote = not in_double_quote
                result.append(char)
            elif char == "%":
                # 处理%符号
                if i + 1 < len(sql) and sql[i + 1] == "s":
                    # 找到%s，检查是否在字符串中
                    if not in_single_quote and not in_double_quote:
                        # 不在字符串中，替换为?
                        result.append("?")
                        i += 1  # 跳过's'
                    else:
                        # 在字符串中，保留原样
                        result.append("%s")
                        i += 1
                elif not in_single_quote and not in_double_quote:
                    # 单独的%符号（不是%s）
                    # 检查下一个字符是否是字母或数字，如果是格式化说明符的一部分
                    if i + 1 < len(sql) and sql[i + 1].isalnum():
                        # 可能是格式化说明符（如%d, %f等），保留它
                        result.append(char)
                    elif i + 1 < len(sql) and sql[i + 1] == "%":
                        # 双重%符号（%%），在Python中表示字面量%，保留它
                        result.append("%")
                        result.append("%")
                        i += 1  # 跳过第二个%
                    else:
                        # 单独的%符号，在SQLite中需要转义为%%
                        # 转换为字面量%，避免SQL语法错误
                        # 但需要检查是否在LIKE操作符中，如果是则保留%
                        # 简化处理：下一个字符是空白或特殊字符，转义为%%
                        next_char = sql[i + 1] if i + 1 < len(sql) else ""
                        if next_char in (" ", "\t", "\n", "\r", ")", ",", ";", ""):
                            # 单独的%后面跟着空白或结束，转义为%%
                            result.append("%")
                            result.append("%")
                        else:
                            # 可能是其他情况，保留原样但转义为%%
                            result.append("%")
                            result.append("%")
                else:
                    # 在字符串中的%，保留
                    result.append(char)
            else:
                result.append(char)
            i += 1

        sql = "".join(result)

        # 转换PostgreSQL的TRUE/FALSE为SQLite的1/0
        # 使用正则表达式，只替换不在字符串中的TRUE/FALSE
        # 处理 is_active = TRUE -> is_active = 1
        sql = re.sub(
            r"\bis_active\s*=\s*TRUE\b", "is_active = 1", sql, flags=re.IGNORECASE
        )
        # 处理 is_active = FALSE -> is_active = 0
        sql = re.sub(
            r"\bis_active\s*=\s*FALSE\b", "is_active = 0", sql, flags=re.IGNORECASE
        )
        # 处理其他布尔字段的类似比较
        sql = re.sub(
            r"\b(success|is_test_user|is_active|is_test_data)\s*=\s*TRUE\b",
            r"\1 = 1",
            sql,
            flags=re.IGNORECASE,
        )
        sql = re.sub(
            r"\b(success|is_test_user|is_active|is_test_data)\s*=\s*FALSE\b",
            r"\1 = 0",
            sql,
            flags=re.IGNORECASE,
        )
        # 处理 VALUES (?, ?, TRUE) 或 SET is_active = TRUE 中的 TRUE/FALSE
        # 直接替换所有不在引号中的TRUE/FALSE
        # 使用简单的逐字符分析，确保不在字符串中
        result = []
        in_single_quote = False
        in_double_quote = False
        i = 0

        while i < len(sql):
            char = sql[i]

            # 跟踪引号状态
            if char == "'" and (i == 0 or sql[i - 1] != "\\"):
                in_single_quote = not in_single_quote
                result.append(char)
            elif char == '"' and (i == 0 or sql[i - 1] != "\\"):
                in_double_quote = not in_double_quote
                result.append(char)
            elif not in_single_quote and not in_double_quote:
                # 不在引号中，检查是否为TRUE或FALSE
                if i + 3 < len(sql) and sql[i : i + 4].upper() == "TRUE":
                    # 确保是完整的单词（使用单词边界检查）
                    if (i == 0 or not sql[i - 1].isalnum()) and (
                        i + 4 >= len(sql) or not sql[i + 4].isalnum()
                    ):
                        result.append("1")
                        i += 3  # 跳过'RUE'
                    else:
                        result.append(char)
                elif i + 4 < len(sql) and sql[i : i + 5].upper() == "FALSE":
                    # 确保是完整的单词
                    if (i == 0 or not sql[i - 1].isalnum()) and (
                        i + 5 >= len(sql) or not sql[i + 5].isalnum()
                    ):
                        result.append("0")
                        i += 4  # 跳过'ALSE'
                    else:
                        result.append(char)
                else:
                    result.append(char)
            else:
                result.append(char)
            i += 1

        sql = "".join(result)

        return sql

    # 检查是否为PostgreSQL连接
    if _is_postgresql_connection(conn):
        # 先处理INSERT VALUES中的布尔值（在占位符转换和adapt_sql之前）
        # 因为adapt_sql会转换占位符，我们需要在占位符转换之前处理字面量1/0
        # 使用更宽松的匹配，因为SQL可能包含换行符
        sql_upper = sql.upper()
        if (
            "ACTIVE_SESSIONS" in sql_upper
            and "VALUES" in sql_upper
            and "INSERT" in sql_upper
        ):
            # 匹配 VALUES (...) 中最后一个单独的 1（可能是is_active）
            # 需要匹配多种情况：
            # 1. VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
            # 2. VALUES (..., 1)
            # 使用更精确的模式：匹配 VALUES 子句中最后的 , 1) 或 , 0)
            # 但要确保不是其他数字的一部分
            # 使用DOTALL标志以匹配可能包含换行符的SQL
            # \s* 匹配零个或多个空白字符，可以同时处理有空格和没空格的情况
            sql = re.sub(
                r",\s*1\s*\)(?=\s*(?:$|;|\n|RETURNING|ON CONFLICT))",
                ", TRUE)",
                sql,
                flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
            )
            # 同样处理0
            sql = re.sub(
                r",\s*0\s*\)(?=\s*(?:$|;|\n|RETURNING|ON CONFLICT))",
                ", FALSE)",
                sql,
                flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
            )

        sql = adapt_sql(sql)
        # 确保占位符被转换（如果adapt_sql没有转换，手动转换）
        # 只替换不在字符串中的?占位符
        result = []
        in_single_quote = False
        in_double_quote = False
        i = 0

        while i < len(sql):
            char = sql[i]

            if char == "'" and (i == 0 or sql[i - 1] != "\\"):
                in_single_quote = not in_single_quote
                result.append(char)
            elif char == '"' and (i == 0 or sql[i - 1] != "\\"):
                in_double_quote = not in_double_quote
                result.append(char)
            elif char == "?":
                if not in_single_quote and not in_double_quote:
                    result.append("%s")
                else:
                    result.append("?")
            else:
                result.append(char)
            i += 1

        sql = "".join(result)
        # 额外的安全检查：确保datetime函数被转换（备用方案）
        # 只匹配?或%s占位符，不匹配单独的%符号
        sql = re.sub(
            r"datetime\s*\(\s*(\?|%s)\s*,\s*['\"]unixepoch['\"]\s*\)",
            r"to_timestamp(\1)",
            sql,
            flags=re.IGNORECASE | re.DOTALL,
        )
        sql = re.sub(
            r"datetime\s*\(\s*(\?|%s)\s*,\s*unixepoch\s*\)",
            r"to_timestamp(\1)",
            sql,
            flags=re.IGNORECASE | re.DOTALL,
        )
        return sql

    # 默认情况：如果无法确定，假设是SQLite，转换%s为?
    # 使用同样的安全替换方法
    result = []
    in_single_quote = False
    in_double_quote = False
    i = 0

    while i < len(sql):
        char = sql[i]

        if char == "'" and (i == 0 or sql[i - 1] != "\\"):
            in_single_quote = not in_single_quote
            result.append(char)
        elif char == '"' and (i == 0 or sql[i - 1] != "\\"):
            in_double_quote = not in_double_quote
            result.append(char)
        elif char == "%" and i + 1 < len(sql) and sql[i + 1] == "s":
            if not in_single_quote and not in_double_quote:
                result.append("?")
                i += 1
            else:
                result.append("%s")
                i += 1
        else:
            result.append(char)
        i += 1

    return "".join(result)


# 数据库连接监控
_connection_counter = 0
_connection_lock = threading.Lock()
_MAX_CONNECTIONS = 50  # 最大并发连接数阈值
_postgres_pool_closed_logged = False

# 连接监控配置
_CONNECTION_WARNINGS = set()  # 记录已发送的警告
_WARNING_THRESHOLD = 10  # 连接数警告阈值
_CRITICAL_THRESHOLD = 30  # 连接数严重阈值


def _increment_connection_counter():
    """增加连接计数器"""
    global _connection_counter
    with _connection_lock:
        _connection_counter += 1
        current_count = _connection_counter

        # 连接数监控和告警
        if current_count > _CRITICAL_THRESHOLD:
            if "critical" not in _CONNECTION_WARNINGS:
                print(
                    f"🚨 严重警告: 当前活跃连接数 {current_count} "
                    f"超过严重阈值 {_CRITICAL_THRESHOLD}"
                )
                _CONNECTION_WARNINGS.add("critical")
        elif current_count > _WARNING_THRESHOLD:
            if "warning" not in _CONNECTION_WARNINGS:
                print(
                    f"⚠️  警告: 当前活跃连接数 {current_count} "
                    f"超过警告阈值 {_WARNING_THRESHOLD}"
                )
                _CONNECTION_WARNINGS.add("warning")
        else:
            # 连接数恢复正常，清除警告记录
            _CONNECTION_WARNINGS.clear()

        return current_count


def _decrement_connection_counter():
    """减少连接计数器"""
    global _connection_counter
    with _connection_lock:
        _connection_counter = max(0, _connection_counter - 1)
        current_count = _connection_counter

        # 如果连接数恢复正常，清除警告记录
        if current_count <= _WARNING_THRESHOLD:
            _CONNECTION_WARNINGS.clear()

        return current_count


def get_connection_count():
    """获取当前活跃连接数"""
    with _connection_lock:
        return _connection_counter


def reset_connection_counter():
    """重置连接计数器（用于测试）"""
    global _connection_counter
    with _connection_lock:
        _connection_counter = 0
        _CONNECTION_WARNINGS.clear()


def get_connection_stats():
    """获取连接统计信息"""
    with _connection_lock:
        return {
            "active_connections": _connection_counter,
            "max_connections": _MAX_CONNECTIONS,
            "warning_threshold": _WARNING_THRESHOLD,
            "critical_threshold": _CRITICAL_THRESHOLD,
            "warnings_active": len(_CONNECTION_WARNINGS) > 0,
        }


def _get_table_columns(cursor, table_name: str) -> list:
    """
    获取表的所有列名（兼容SQLite和PostgreSQL）

    Args:
        cursor: 数据库游标
        table_name: 表名

    Returns:
        列名列表
    """
    # 从cursor获取connection对象以检测类型
    try:
        conn = cursor.connection
    except AttributeError:
        # 如果没有connection属性，尝试从cursor的模块判断
        # 这是后备方案，通常不会用到
        conn = None

    # 检测实际连接类型
    if conn and _is_postgresql_connection(conn):
        # PostgreSQL使用information_schema
        sql_raw = """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = ?
            ORDER BY ordinal_position
        """
        sql = _safe_adapt_sql(sql_raw, conn)
        cursor.execute(sql, (table_name,))
        return [row[0] for row in cursor.fetchall()]
    else:
        # SQLite使用PRAGMA（直接执行，不需要占位符）
        # 注意：table_name已经通过白名单验证或来自内部代码，安全
        cursor.execute(f"PRAGMA table_info({table_name})")
        return [col[1] for col in cursor.fetchall()]


def _check_connections_at_exit():
    """程序退出时检查并强制关闭所有连接"""
    try:
        count = get_connection_count()
    except (AttributeError, RuntimeError, TypeError):
        count = 0
    skip_cleanup = os.getenv("DBUTILS_SKIP_EXIT_CLEANUP") == "1"

    if count > 0:
        print(f"⚠️  警告: 程序退出时仍有 {count} 个数据库连接未关闭")
        print("🔧 正在强制关闭所有连接...")

    if not skip_cleanup:
        try:
            from db_adapter import close_connection_pool
        except ImportError:

            def close_connection_pool():
                pass

        try:
            close_connection_pool()
            global _postgres_pool_closed_logged
            if not _postgres_pool_closed_logged:
                print("✅ PostgreSQL连接池已关闭")
                _postgres_pool_closed_logged = True
        except (AttributeError, RuntimeError, OSError, ConnectionError):
            pass

    global _connection_counter
    try:
        with _connection_lock:
            remaining_count = _connection_counter
            if remaining_count > 0:
                print(f"⚠️  仍有 {remaining_count} 个连接未通过正常流程关闭")
            _connection_counter = 0
    except (AttributeError, RuntimeError):
        _connection_counter = 0


def _cleanup_on_interrupt():
    """优雅关闭处理器（用于信号处理）"""
    print("\n🛑 收到中断信号，正在优雅关闭...")
    _check_connections_at_exit()
    print("✅ 数据库连接已清理完成")


# 注册退出检查
atexit.register(_check_connections_at_exit)


def signal_handler(signum, frame):
    """处理SIGINT和SIGTERM信号"""
    # 明确标记未使用的参数
    _ = signum, frame
    _cleanup_on_interrupt()
    # 退出程序
    sys.exit(0)


# 注册信号处理（优雅关闭）
try:
    signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # kill命令
except (ValueError, OSError):
    # Windows上某些信号不支持，忽略
    pass


def hash_password(password: str) -> str:
    """
    使用bcrypt对密码进行加盐哈希

    Args:
        password (str): 明文密码

    Returns:
        str: 加盐哈希后的密码
    """
    # 生成随机盐值
    salt = bcrypt.gensalt(rounds=12)  # 12轮加密，安全性高
    # 对密码进行哈希
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    """
    验证密码是否正确

    Args:
        password (str): 明文密码
        hashed_password (str): 存储的哈希密码

    Returns:
        bool: 密码是否正确
    """
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))
    except (ValueError, TypeError):
        # 兼容旧的SHA256格式
        return verify_legacy_password(password, hashed_password)


def verify_legacy_password(password: str, hashed_password: str) -> bool:
    """
    验证旧的SHA256格式密码（向后兼容）

    Args:
        password (str): 明文密码
        hashed_password (str): SHA256哈希密码

    Returns:
        bool: 密码是否正确
    """
    legacy_hash = hashlib.sha256(password.encode()).hexdigest()
    return legacy_hash == hashed_password


def is_bcrypt_hash(hashed_password: str) -> bool:
    """
    检查密码是否为bcrypt格式

    Args:
        hashed_password (str): 哈希密码

    Returns:
        bool: 是否为bcrypt格式
    """
    return hashed_password.startswith("$2b$") or hashed_password.startswith("$2a$")


def get_db_connection():
    """
    返回一个可用于 with 语句的数据库连接管理器
    使用PostgreSQL
    """
    from db_adapter import get_db_connection as _adapter_func

    return _adapter_func()


def get_enhanced_db_connection():
    """
    获取增强的数据库连接（推荐使用）
    提供连接泄露检测和自动修复功能
    """
    try:
        from .enhanced_connection_manager import get_enhanced_db_connection

        return get_enhanced_db_connection()
    except ImportError:
        print("警告: 增强连接管理器不可用，使用标准连接")
        return get_db_connection()


def get_enhanced_connection_stats():
    """获取增强连接池统计信息"""
    try:
        from .enhanced_connection_manager import get_connection_stats as enhanced_stats

        return enhanced_stats()
    except ImportError:
        # 如果增强连接管理器不可用，回退到标准连接统计
        # 调用模块级别的 get_connection_stats 函数
        return get_connection_stats()


def current_user_id():
    """获取当前用户ID"""
    # 支持字典和属性两种访问方式，确保测试环境兼容性
    user = None
    try:
        # 先尝试字典方式访问
        if hasattr(st.session_state, "__contains__"):
            try:
                if "user" in st.session_state:
                    user = st.session_state["user"]
            except (TypeError, AttributeError):
                # FakeState等对象可能不支持字典访问
                pass
    except (TypeError, AttributeError):
        pass

    # 如果字典方式失败，尝试属性方式
    if user is None:
        try:
            if hasattr(st.session_state, "user"):
                user = st.session_state.user
        except (AttributeError, TypeError):
            pass

    if user is None:
        raise ValueError("用户未登录")

    if isinstance(user, dict):
        return user["id"]
    else:
        return getattr(user, "id", None)


def is_admin():
    """检查当前用户是否为管理员"""
    # 支持字典和属性两种访问方式，确保测试环境兼容性
    user = None
    try:
        # 先尝试字典方式访问
        if hasattr(st.session_state, "__contains__"):
            try:
                if "user" in st.session_state:
                    user = st.session_state["user"]
            except (TypeError, AttributeError):
                # FakeState等对象可能不支持字典访问
                pass
    except (TypeError, AttributeError):
        pass

    # 如果字典方式失败，尝试属性方式
    if user is None:
        try:
            if hasattr(st.session_state, "user"):
                user = st.session_state.user
        except (AttributeError, TypeError):
            pass

    if user is None:
        return False

    # 支持字典和对象两种访问方式
    if isinstance(user, dict):
        role = user.get("role")
    else:
        role = getattr(user, "role", None)
    return role == "admin"


def require_admin():
    """要求管理员权限，否则抛出异常"""
    if not is_admin():
        raise PermissionError("此操作需要管理员权限")


def get_system_config(
    config_key: str, default_value: Optional[str] = None
) -> Optional[str]:
    """获取系统配置值"""
    with get_db_connection() as (_, c):
        if c is None:
            return default_value
        # 确保使用正确的adapt_sql函数
        from db_adapter import adapt_sql as _adapt_sql

        sql = _adapt_sql("SELECT config_value FROM system_config WHERE config_key = ?")
        c.execute(sql, (config_key,))
        result = c.fetchone()
        return result[0] if result else default_value


def set_system_config(
    config_key: str, config_value: str, description: Optional[str] = None
) -> bool:
    """设置系统配置值"""
    with get_db_connection() as (conn, c):
        try:
            if _is_postgresql_connection(conn):
                sql_raw = """
                    INSERT INTO system_config
                    (config_key, config_value, description, updated_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT (config_key) DO UPDATE SET
                    config_value = EXCLUDED.config_value,
                    description = EXCLUDED.description,
                    updated_at = CURRENT_TIMESTAMP
                """
                sql = _safe_adapt_sql(sql_raw, conn)
                c.execute(sql, (config_key, config_value, description))
            else:
                sql = """
                    INSERT OR REPLACE INTO system_config
                    (config_key, config_value, description, updated_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                """
            c.execute(sql, (config_key, config_value, description or ""))
            conn.commit()
            return True
        except Exception as e:
            print(f"设置系统配置失败: {e}")
            return False


def is_registration_open() -> bool:
    """检查是否开放注册"""
    config_value = get_system_config("open_registration", "false")
    return config_value is not None and config_value.lower() == "true"


# 数据库升级相关函数


def _upgrade_logistics_volume_coefficient():
    """升级物流表体积系数字段"""
    with get_db_connection() as (conn, c):
        # 检测实际连接类型
        if _is_postgresql_connection(conn):
            # PostgreSQL跳过（表结构应该已经正确）
            return
        # 首先检查表是否存在
        check_sql = _safe_adapt_sql(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", conn
        )
        c.execute(check_sql, ("logistics",))
        if not c.fetchone():
            return  # 表不存在，无需升级
        cols = _get_table_columns(c, "logistics")
        if "volume_coefficient" not in cols:
            c.execute(
                "ALTER TABLE logistics ADD COLUMN volume_coefficient REAL DEFAULT 5000"
            )
        conn.commit()


def _upgrade_max_size_to_sides(table: str):
    """升级旧表结构：max_size -> max_sum_of_sides + max_longest_side"""
    with get_db_connection() as (conn, c):
        # 检测实际连接类型
        if _is_postgresql_connection(conn):
            # PostgreSQL跳过（表结构应该已经正确）
            return
        # 首先检查表是否存在
        check_sql = _safe_adapt_sql(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", conn
        )
        c.execute(check_sql, (table,))
        if not c.fetchone():
            return  # 表不存在，无需升级
        # 1. 检查是否已有新字段
        cols = _get_table_columns(c, table)
        if "max_sum_of_sides" in cols and "max_longest_side" in cols:
            return  # 已升级过
        # 2. 重命名旧表
        c.execute(f"ALTER TABLE {table} RENAME TO {table}_old")
        # 3. 创建包含所有字段的新表
        c.execute(
            """
            CREATE TABLE logistics (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                name TEXT,
                type TEXT,
                min_days INTEGER,
                max_days INTEGER,
                price_limit REAL,
                base_fee REAL,
                weight_factor REAL,
                min_weight INTEGER,
                max_weight INTEGER,
                max_sum_of_sides INTEGER,
                max_longest_side INTEGER,
                volume_mode TEXT
                    CHECK(volume_mode IN ('none',
                                          'max_actual_vs_volume',
                                          'longest_side'))
                    DEFAULT 'none',
                longest_side_threshold INTEGER DEFAULT 0,
                volume_coefficient REAL DEFAULT 5000,
                allow_battery INTEGER,
                allow_flammable INTEGER
            )
            """
        )
        # 4. 迁移旧数据
        c.execute(
            """
            INSERT INTO logistics (
                user_id, name, type, min_days, max_days, price_limit,
                base_fee, weight_factor,
                min_weight, max_weight,
                max_sum_of_sides, max_longest_side,
                volume_mode, longest_side_threshold,
                volume_coefficient, allow_battery, allow_flammable
            )
            SELECT
                user_id, name, type, min_days, max_days, price_limit,
                base_fee, weight_factor,
                min_weight, max_weight,
                COALESCE(max_size, 0), COALESCE(max_size, 0),
                volume_mode, longest_side_threshold,
                5000, allow_battery, allow_flammable
            FROM logistics_old
            """
        )
        # 5. 清理旧表（table已通过白名单验证）
        c.execute(f"DROP TABLE {table}_old")
        conn.commit()


def _upgrade_table_user_id(table: str):
    """给旧表加 user_id 字段（如存在）"""
    # 白名单验证：只允许这些表名，防止SQL注入
    allowed_tables = {"products", "logistics"}
    if table not in allowed_tables:
        raise ValueError(
            f"非法的表名: {table}. 只允许使用以下表名: {sorted(allowed_tables)}"
        )

    with get_db_connection() as (conn, c):
        # 首先检查表是否存在
        if _is_postgresql_connection(conn):
            # PostgreSQL: 检查表是否存在
            check_sql_raw = (
                "SELECT EXISTS ("
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = ?"
                ")"
            )
            check_sql = _safe_adapt_sql(check_sql_raw, conn)
            c.execute(check_sql, (table,))
            table_exists = c.fetchone()[0]
            if not table_exists:
                return  # 表不存在，无需升级
            # PostgreSQL使用information_schema
            sql_raw = (
                "SELECT column_name "
                "FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = ?"
            )
            sql = _safe_adapt_sql(sql_raw, conn)
            c.execute(sql, (table,))
            cols = [row[0] for row in c.fetchall()]
        else:
            # SQLite: 检查表是否存在
            check_sql = _safe_adapt_sql(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?", conn
            )
            c.execute(check_sql, (table,))
            if not c.fetchone():
                return  # 表不存在，无需升级
            # SQLite使用辅助函数
            cols = _get_table_columns(c, table)
        if "user_id" in cols:
            return
        c.execute(f"ALTER TABLE {table} RENAME TO {table}_old")
        if table == "logistics":
            c.execute(
                """
                CREATE TABLE logistics (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    name TEXT,
                    type TEXT,
                    min_days INTEGER,
                    max_days INTEGER,
                    price_limit REAL,
                    base_fee REAL,
                    weight_factor REAL,
                    min_weight INTEGER,
                    max_weight INTEGER,
                    max_sum_of_sides INTEGER,
                    max_longest_side INTEGER,
                    volume_mode TEXT DEFAULT 'none',
                    longest_side_threshold INTEGER DEFAULT 0,
                    volume_coefficient REAL DEFAULT 5000,
                    allow_battery INTEGER,
                    allow_flammable INTEGER
                )
                """
            )
            c.execute(
                """
                INSERT INTO logistics (
                    user_id, name, type, min_days, max_days, price_limit,
                    base_fee, weight_factor,
                    min_weight, max_weight,
                    max_sum_of_sides, max_longest_side,
                    volume_mode, longest_side_threshold,
                    volume_coefficient, allow_battery, allow_flammable
                )
                SELECT
                    (SELECT id FROM users WHERE role='admin' LIMIT 1),
                    name, type, min_days, max_days, price_limit,
                    base_fee, weight_factor,
                    min_weight, max_weight,
                    COALESCE(max_size, 0), COALESCE(max_size, 0),
                    volume_mode, longest_side_threshold,
                    5000, allow_battery, allow_flammable
                FROM logistics_old
                """
            )
        elif table == "products":
            c.execute(
                """
                CREATE TABLE products (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    name TEXT,
                    russian_name TEXT,
                    category TEXT,
                    model TEXT,
                    unit_price REAL,
                    weight_g INTEGER,
                    length_cm INTEGER,
                    width_cm INTEGER,
                    height_cm INTEGER,
                    is_cylinder INTEGER,
                    cylinder_diameter REAL,
                    cylinder_length REAL,
                    has_battery INTEGER,
                    battery_capacity_wh REAL,
                    battery_capacity_mah INTEGER,
                    battery_voltage REAL,
                    has_msds INTEGER,
                    has_flammable INTEGER,
                    shipping_fee REAL,
                    labeling_fee REAL
                )
                """
            )
            c.execute(
                """
                INSERT INTO products (
                    user_id, name, russian_name, category, model,
                    unit_price, weight_g, length_cm, width_cm, height_cm,
                    is_cylinder, cylinder_diameter, cylinder_length,
                    has_battery, battery_capacity_wh, battery_capacity_mah,
                    battery_voltage, has_msds, has_flammable,
                    shipping_fee, labeling_fee
                )
                SELECT
                    (SELECT id FROM users WHERE role='admin' LIMIT 1),
                    name, russian_name, category, model,
                    unit_price, weight_g, length_cm, width_cm, height_cm,
                    is_cylinder, cylinder_diameter, 0.0,
                    has_battery, battery_capacity_wh, battery_capacity_mah,
                    battery_voltage, has_msds, has_flammable,
                    shipping_fee, labeling_fee
                FROM products_old
                """
            )
        c.execute(f"DROP TABLE {table}_old")
        conn.commit()


def _upgrade_old_volume_battery():
    """升级旧表体积和电池因子字段"""
    _upgrade_logistics_volume_coefficient()
    with get_db_connection() as (conn, c):
        cols = _get_table_columns(c, "logistics")
        # 如果旧表里还有 volume_factor / battery_factor 就 DROP COLUMN
        # SQLite ≥ 3.35 支持 DROP COLUMN；PostgreSQL也支持
        # 检测实际连接类型
        if _is_postgresql_connection(conn):
            # PostgreSQL跳过（表结构应该已经正确）
            return
        for col in ["volume_factor", "battery_factor"]:
            if col in cols:
                c.execute(f"ALTER TABLE logistics DROP COLUMN {col}")
        conn.commit()


def _safe_alter_table_add_column(
    cursor, table_name: str, column_name: str, column_def: str, allowed_columns: set
) -> None:
    """
    安全地执行ALTER TABLE ADD COLUMN操作，防止SQL注入
    高优先级安全改进：增强列名验证（正则表达式 + SQL关键字检查）

    Args:
        cursor: 数据库游标
        table_name: 表名（必须为预定义的安全表名）
        column_name: 列名（必须通过白名单验证）
        column_def: 列定义（必须通过白名单验证）
        allowed_columns: 允许的列名白名单

    Raises:
        ValueError: 如果列名或表名不在白名单中
    """
    import re

    # 预定义的安全表名白名单（扩展以包含所有可能的表）
    safe_table_names = {
        "users",
        "products",
        "logistics",
        "payment_orders",
        "active_sessions",
        "login_attempts",
        "user_lockouts",
        "subscription_upgrade_history",
        "user_login_log",
        "user_behavior_log",
        "admin_action_log",
        "alert_records",
        "statistics_cache",
        "alert_config",
        "plans",
        "system_config",
        "payment_nonce_log",
    }

    # 验证表名
    if table_name not in safe_table_names:
        raise ValueError(
            f"非法的表名: {table_name}. 只允许使用以下表名: {sorted(safe_table_names)}"
        )

    # 高优先级安全改进：更严格的列名验证
    # 1. 正则表达式验证：只允许字母、数字、下划线，且必须以字母开头
    column_pattern = r"^[a-zA-Z][a-zA-Z0-9_]{0,62}$"
    if not re.match(column_pattern, column_name):
        raise ValueError(
            f"非法的列名格式: {column_name}. "
            f"列名必须以字母开头，只能包含字母、数字和下划线，"
            f"长度不超过63个字符"
        )

    # 2. SQL关键字检查（防止使用SQL关键字作为列名）
    sql_keywords = {
        "SELECT",
        "INSERT",
        "UPDATE",
        "DELETE",
        "DROP",
        "CREATE",
        "ALTER",
        "TABLE",
        "INDEX",
        "VIEW",
        "TRIGGER",
        "DATABASE",
        "SCHEMA",
        "FROM",
        "WHERE",
        "JOIN",
        "ON",
        "AS",
        "AND",
        "OR",
        "NOT",
        "IN",
        "LIKE",
        "BETWEEN",
        "IS",
        "NULL",
        "TRUE",
        "FALSE",
        "ORDER",
        "BY",
        "GROUP",
        "HAVING",
        "LIMIT",
        "OFFSET",
        "UNION",
        "ALL",
        "DISTINCT",
        "COUNT",
        "SUM",
        "AVG",
        "MAX",
        "MIN",
        "EXISTS",
        "CASE",
        "WHEN",
        "THEN",
        "ELSE",
        "END",
        "IF",
        "PRIMARY",
        "KEY",
        "FOREIGN",
        "REFERENCES",
        "CONSTRAINT",
        "UNIQUE",
        "CHECK",
        "DEFAULT",
        "AUTOINCREMENT",
        "INTEGER",
        "REAL",
        "TEXT",
        "BLOB",
        "VARCHAR",
        "CHAR",
        "DATE",
        "TIME",
        "DATETIME",
        "TIMESTAMP",
        "BOOLEAN",
        "INT",
        "FLOAT",
        "DOUBLE",
    }
    if column_name.upper() in sql_keywords:
        raise ValueError(f"列名不能使用SQL关键字: {column_name}. 请使用其他名称")

    # 3. 白名单验证（双重保险）
    if column_name not in allowed_columns:
        raise ValueError(
            f"非法的列名: {column_name}. 只允许使用以下列名: {sorted(allowed_columns)}"
        )

    # 验证列定义格式（只允许特定类型和DEFAULT值）

    allowed_types = {"INTEGER", "REAL", "TEXT", "BOOLEAN"}
    # 定义允许的列定义格式模式
    # 注意：SQLite支持单引号和双引号，都需要匹配
    allowed_patterns = [
        r"^INTEGER\s*$",  # INTEGER (无DEFAULT)
        r"^INTEGER\s+DEFAULT\s+-?\d+$",  # INTEGER DEFAULT 数字（支持负数）
        r"^REAL\s*$",  # REAL (无DEFAULT)
        r"^REAL\s+DEFAULT\s+-?[\d.]+$",  # REAL DEFAULT 数字或小数（支持负数）
        r"^TEXT\s*$",  # TEXT (无DEFAULT)
        r"^TEXT\s+DEFAULT\s+\'[^\']*\'\s*$",  # TEXT DEFAULT '字符串'
        r'^TEXT\s+DEFAULT\s+"[^"]*"\s*$',  # TEXT DEFAULT "字符串"
        r"^TEXT\s+DEFAULT\s+\'\'\s*$",  # TEXT DEFAULT '' (空字符串)
        r'^TEXT\s+DEFAULT\s+""\s*$',  # TEXT DEFAULT "" (空字符串)
    ]

    column_def_upper = column_def.upper().strip()

    # 首先检查列类型
    type_match = re.match(r"^(\w+)", column_def_upper)
    if type_match:
        col_type = type_match.group(1)
        if col_type not in allowed_types:
            raise ValueError(
                f"非法的列类型: {col_type}. 只允许使用以下类型: {sorted(allowed_types)}"
            )
    else:
        raise ValueError(f"无效的列定义格式: {column_def}")

    # 使用正则表达式验证列定义格式是否符合允许的模式
    pattern_matched = False
    for pattern in allowed_patterns:
        if re.match(pattern, column_def_upper):
            pattern_matched = True
            break

    if not pattern_matched:
        raise ValueError(
            f"非法的列定义格式: {column_def}. "
            f"列定义必须符合以下格式之一: "
            f"INTEGER, INTEGER DEFAULT <数字>, "
            f"REAL, REAL DEFAULT <数字>, "
            f"TEXT, TEXT DEFAULT '<字符串>' 或 TEXT DEFAULT \"<字符串>\""
        )

    # 执行安全的ALTER TABLE语句（使用参数化查询的列名部分）
    # 注意：SQLite的ALTER TABLE不支持参数化列名，所以必须使用白名单验证
    # 所有输入都经过严格验证和白名单检查
    sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}"
    # 最终验证：确保SQL语句不包含危险关键字
    dangerous_keywords = ["DROP", "DELETE", "TRUNCATE", "UPDATE", "INSERT"]
    sql_upper = sql.upper()
    for keyword in dangerous_keywords:
        if keyword in sql_upper and "ADD COLUMN" not in sql_upper:
            raise ValueError(f"检测到危险的SQL关键字: {keyword}，操作已阻止")
    cursor.execute(sql)


def _upgrade_logistics_new_fields():
    """升级：新增重量计费字段、电池容量限制字段"""
    # 白名单：只允许这些列名，防止SQL注入
    allowed_logistics_columns = {
        "battery_capacity_limit_wh",
        "require_msds",
        "fee_mode",
        "first_fee",
        "first_weight_g",
        "continue_fee",
        "continue_unit",
        "volume_coefficient",
        "price_limit_rub",
        "price_min_rub",
        "max_second_side",
        "min_second_side",
        "min_length",
        "max_cylinder_sum",
        "min_cylinder_sum",
        "max_cylinder_length",
        "min_cylinder_length",
        "allow_battery",
        "allow_flammable",
        "delivery_method",
        "priority_group",
        "price_limit_currency",
        "price_min_currency",
    }

    with get_db_connection() as (conn, c):
        # 检测实际连接类型
        if _is_postgresql_connection(conn):
            # PostgreSQL跳过（表结构应该已经正确）
            return
        # 首先检查表是否存在
        check_sql = _safe_adapt_sql(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", conn
        )
        c.execute(check_sql, ("logistics",))
        if not c.fetchone():
            return  # 表不存在，无需升级
        cols = _get_table_columns(c, "logistics")
        new_cols = {
            "battery_capacity_limit_wh": "REAL DEFAULT 0",
            "require_msds": "INTEGER DEFAULT 0",
            "fee_mode": "TEXT DEFAULT 'base_plus_continue'",
            "first_fee": "REAL DEFAULT 0",
            "first_weight_g": "INTEGER DEFAULT 0",
            "continue_fee": "REAL DEFAULT 0",
            "continue_unit": "TEXT DEFAULT '100'",
            "volume_coefficient": "INTEGER DEFAULT 5000",
            "price_limit_rub": "REAL DEFAULT 0",
            "price_min_rub": "REAL DEFAULT 0",
            "max_second_side": "INTEGER DEFAULT 0",
            "min_second_side": "INTEGER DEFAULT 0",
            "min_length": "INTEGER DEFAULT 0",
            "max_cylinder_sum": "INTEGER DEFAULT 0",
            "min_cylinder_sum": "INTEGER DEFAULT 0",
            "max_cylinder_length": "INTEGER DEFAULT 0",
            "min_cylinder_length": "INTEGER DEFAULT 0",
            "allow_battery": "INTEGER DEFAULT 0",
            "allow_flammable": "INTEGER DEFAULT 0",
            "delivery_method": "TEXT DEFAULT 'unknown'",
            "priority_group": "TEXT DEFAULT 'D'",
            "price_limit_currency": "TEXT DEFAULT 'RUB'",
            "price_min_currency": "TEXT DEFAULT 'RUB'",
        }
        for col, def_sql in new_cols.items():
            # 使用安全的ALTER TABLE函数
            if col not in cols:
                _safe_alter_table_add_column(
                    c, "logistics", col, def_sql, allowed_logistics_columns
                )
        conn.commit()


def _upgrade_products_cylinder_length():
    """升级：新增产品圆柱长度字段"""
    with get_db_connection() as (conn, c):
        # 检测实际连接类型
        if _is_postgresql_connection(conn):
            # PostgreSQL跳过（表结构应该已经正确）
            return
        # 首先检查表是否存在
        check_sql = _safe_adapt_sql(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", conn
        )
        c.execute(check_sql, ("products",))
        if not c.fetchone():
            return  # 表不存在，无需升级
        cols = _get_table_columns(c, "products")
        if "cylinder_length" not in cols:
            c.execute("ALTER TABLE products ADD COLUMN cylinder_length REAL DEFAULT 0")
        conn.commit()


def _upgrade_products_new_fields():
    """升级：新增产品定价相关字段"""
    # 白名单：只允许这些列名，防止SQL注入
    allowed_products_columns = {
        "promotion_discount",
        "promotion_cost_rate",
        "target_profit_margin",
        "commission_rate",
        "withdrawal_fee_rate",
        "payment_processing_fee",
    }

    with get_db_connection() as (conn, c):
        # 检测实际连接类型
        if _is_postgresql_connection(conn):
            # PostgreSQL跳过（表结构应该已经正确）
            return
        # 首先检查表是否存在
        check_sql = _safe_adapt_sql(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", conn
        )
        c.execute(check_sql, ("products",))
        if not c.fetchone():
            return  # 表不存在，无需升级
        cols = _get_table_columns(c, "products")
        new_cols = {
            "promotion_discount": "REAL DEFAULT 0.05",
            "promotion_cost_rate": "REAL DEFAULT 0.115",
            "target_profit_margin": "REAL DEFAULT 0.5",
            "commission_rate": "REAL DEFAULT 0.17",
            "withdrawal_fee_rate": "REAL DEFAULT 0.01",
            "payment_processing_fee": "REAL DEFAULT 0.01",
        }
        for col, def_sql in new_cols.items():
            # 使用安全的ALTER TABLE函数
            if col not in cols:
                _safe_alter_table_add_column(
                    c, "products", col, def_sql, allowed_products_columns
                )
        conn.commit()


def _upgrade_users_subscription_fields():
    """升级：新增用户订阅相关字段"""
    # 白名单：只允许这些列名，防止SQL注入
    allowed_users_columns = {
        "user_type",
        "expiry_date",
        "remaining_calculations",
        "first_login_date",
        "test_days_remaining",
        "subscription_type",
        "subscription_expires",
        "efficiency_promo_used",
        "created_at",
        "last_login",
    }

    with get_db_connection() as (conn, c):
        # 检测实际连接类型
        if _is_postgresql_connection(conn):
            # PostgreSQL跳过（表结构应该已经正确）
            return
        # 首先检查表是否存在
        check_sql = _safe_adapt_sql(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", conn
        )
        c.execute(check_sql, ("users",))
        if not c.fetchone():
            return  # 表不存在，无需升级
        cols = _get_table_columns(c, "users")
        new_cols = {
            "user_type": "TEXT DEFAULT 'permanent'",
            "expiry_date": "TEXT",
            "remaining_calculations": "INTEGER DEFAULT -1",
            "first_login_date": "TEXT",
            "test_days_remaining": "INTEGER DEFAULT 0",
            "subscription_type": "TEXT DEFAULT 'free'",
            "subscription_expires": "INTEGER",
            "efficiency_promo_used": "INTEGER DEFAULT 0",  # 记录是否使用过效率版首月1元优惠
            "created_at": "TEXT DEFAULT ''",  # 注册时间
            "last_login": "TEXT",  # 最后登录时间
        }
        for col, def_sql in new_cols.items():
            # 使用安全的ALTER TABLE函数
            if col not in cols:
                _safe_alter_table_add_column(
                    c, "users", col, def_sql, allowed_users_columns
                )
        conn.commit()


def _upgrade_users_test_flag():
    """升级：新增用户测试标记字段"""
    with get_db_connection() as (conn, c):
        # 检测实际连接类型
        if _is_postgresql_connection(conn):
            # PostgreSQL跳过（表结构应该已经正确）
            return
        # 首先检查表是否存在
        check_sql = _safe_adapt_sql(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", conn
        )
        c.execute(check_sql, ("users",))
        if not c.fetchone():
            return  # 表不存在，无需升级
        cols = _get_table_columns(c, "users")
        if "is_test_user" not in cols:
            c.execute("ALTER TABLE users ADD COLUMN is_test_user INTEGER DEFAULT 0")
        conn.commit()


def _upgrade_performance_indexes():
    """升级：添加复合索引优化查询性能"""
    with get_db_connection() as (conn, c):
        # 检查索引是否已存在
        # 检测实际连接类型
        if _is_postgresql_connection(conn):
            sql = """
                SELECT indexname FROM pg_indexes
                WHERE schemaname = 'public'
            """
            c.execute(sql)
            existing_indexes = c.fetchall()
            existing_index_names = [idx[0] for idx in existing_indexes]
        else:
            sql = "SELECT name FROM sqlite_master WHERE type='index'"
            c.execute(sql)
            existing_indexes = c.fetchall()
            existing_index_names = [idx[0] for idx in existing_indexes]

        # 检查表是否存在（仅SQLite需要）
        if not _is_postgresql_connection(conn):
            check_sql = _safe_adapt_sql(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?", conn
            )
            # 检查 payment_orders 表是否存在
            c.execute(check_sql, ("payment_orders",))
            payment_orders_exists = c.fetchone() is not None
            # 检查 user_login_log 表是否存在
            c.execute(check_sql, ("user_login_log",))
            user_login_log_exists = c.fetchone() is not None
            # 检查 user_behavior_log 表是否存在
            c.execute(check_sql, ("user_behavior_log",))
            user_behavior_log_exists = c.fetchone() is not None
            # 检查 products 表是否存在
            c.execute(check_sql, ("products",))
            products_exists = c.fetchone() is not None
        else:
            # PostgreSQL: 假设表都存在（表结构应该已经正确）
            payment_orders_exists = True
            user_login_log_exists = True
            user_behavior_log_exists = True
            products_exists = True

        # 1. payment_orders表 - 用户+状态复合索引（支付历史查询）
        if (
            payment_orders_exists
            and "idx_payment_orders_user_status" not in existing_index_names
        ):
            c.execute(
                _safe_adapt_sql(
                    """
                CREATE INDEX IF NOT EXISTS idx_payment_orders_user_status
                ON payment_orders(user_id, status)
            """,
                    conn,
                )
            )

        # 2. user_login_log表 - 用户+时间复合索引（活跃度统计）
        if (
            user_login_log_exists
            and "idx_user_login_log_user_time" not in existing_index_names
        ):
            c.execute(
                _safe_adapt_sql(
                    """
                CREATE INDEX IF NOT EXISTS idx_user_login_log_user_time
                ON user_login_log(user_id, login_time DESC)
            """,
                    conn,
                )
            )

        # 3. user_behavior_log表 - 用户+类型复合索引（行为分析）
        if (
            user_behavior_log_exists
            and "idx_user_behavior_log_user_type" not in existing_index_names
        ):
            c.execute(
                _safe_adapt_sql(
                    """
                CREATE INDEX IF NOT EXISTS idx_user_behavior_log_user_type
                ON user_behavior_log(user_id, behavior_type)
            """,
                    conn,
                )
            )

        # 4. payment_orders表 - 创建时间+状态索引（收入统计）
        if (
            payment_orders_exists
            and "idx_payment_orders_time_status" not in existing_index_names
        ):
            c.execute(
                _safe_adapt_sql(
                    """
                CREATE INDEX IF NOT EXISTS idx_payment_orders_time_status
                ON payment_orders(created_at DESC, status)
            """,
                    conn,
                )
            )

        # 5. products表 - 用户+名称索引（产品搜索）
        if products_exists and "idx_products_user_name" not in existing_index_names:
            c.execute(
                _safe_adapt_sql(
                    """
                CREATE INDEX IF NOT EXISTS idx_products_user_name
                ON products(user_id, name)
            """,
                    conn,
                )
            )

        conn.commit()


def _upgrade_logistics_price_min():
    """升级：新增物流价格下限字段"""
    with get_db_connection() as (conn, c):
        # 检测实际连接类型
        if _is_postgresql_connection(conn):
            # PostgreSQL跳过（表结构应该已经正确）
            return
        # 首先检查表是否存在
        check_sql = _safe_adapt_sql(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", conn
        )
        c.execute(check_sql, ("logistics",))
        if not c.fetchone():
            return  # 表不存在，无需升级
        cols = _get_table_columns(c, "logistics")
        if "price_min" not in cols:
            c.execute("ALTER TABLE logistics ADD COLUMN price_min REAL DEFAULT 0")
        conn.commit()


def _upgrade_products_return_rate():
    """升级：新增产品历史退货率字段"""
    with get_db_connection() as (conn, c):
        # 检测实际连接类型
        if _is_postgresql_connection(conn):
            return
        # 首先检查表是否存在
        check_sql = _safe_adapt_sql(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", conn
        )
        c.execute(check_sql, ("products",))
        if not c.fetchone():
            return  # 表不存在，无需升级
        cols = [col[1] for col in c.execute("PRAGMA table_info(products)").fetchall()]
        if "return_rate" not in cols:
            c.execute("ALTER TABLE products ADD COLUMN return_rate REAL DEFAULT 0")
        conn.commit()


def _upgrade_products_is_test_data():
    """升级：新增产品测试数据标记字段"""
    with get_db_connection() as (conn, c):
        # 首先检查表是否存在
        if not _is_postgresql_connection(conn):
            check_sql = _safe_adapt_sql(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?", conn
            )
            c.execute(check_sql, ("products",))
            if not c.fetchone():
                return  # 表不存在，无需升级
        cols = _get_table_columns(c, "products")
        if "is_test_data" not in cols:
            # 检测实际连接类型
            if _is_postgresql_connection(conn):
                c.execute(
                    ("ALTER TABLE products ADD COLUMN is_test_data INTEGER DEFAULT 0")
                )
            else:
                c.execute(
                    ("ALTER TABLE products ADD COLUMN is_test_data INTEGER DEFAULT 0")
                )
        conn.commit()


def _upgrade_products_vat_rate():
    """升级：新增产品增值税率字段"""
    with get_db_connection() as (conn, c):
        # 检测实际连接类型
        if _is_postgresql_connection(conn):
            return
        # 首先检查表是否存在
        check_sql = _safe_adapt_sql(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", conn
        )
        c.execute(check_sql, ("products",))
        if not c.fetchone():
            return  # 表不存在，无需升级
        cols = _get_table_columns(c, "products")
        if "vat_rate" not in cols:
            c.execute("ALTER TABLE products ADD COLUMN vat_rate REAL DEFAULT 0")
        conn.commit()


def _upgrade_payment_orders_duration():
    """升级：新增支付订单时长字段"""
    with get_db_connection() as (conn, c):
        # 检测实际连接类型
        if _is_postgresql_connection(conn):
            return
        # 首先检查表是否存在
        check_sql = _safe_adapt_sql(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", conn
        )
        c.execute(check_sql, ("payment_orders",))
        if not c.fetchone():
            return  # 表不存在，无需升级
        cols = _get_table_columns(c, "payment_orders")
        if "duration" not in cols:
            c.execute("ALTER TABLE payment_orders ADD COLUMN duration TEXT")
        conn.commit()


def _upgrade_subscription_upgrade_system():
    """升级：添加订阅升级系统相关字段和表"""
    with get_db_connection() as (conn, c):
        # 检测实际连接类型
        if _is_postgresql_connection(conn):
            # PostgreSQL跳过（表结构应该已经正确）
            return
        # 1. 添加 users 表的升级相关字段
        # 首先检查表是否存在
        check_sql = _safe_adapt_sql(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", conn
        )
        c.execute(check_sql, ("users",))
        if not c.fetchone():
            return  # 表不存在，无需升级
        cols = _get_table_columns(c, "users")

        new_fields = {
            "billing_cycle": "TEXT DEFAULT 'month'",
            "last_paid_amount": "REAL DEFAULT 0",
            "subscription_start": "INTEGER",
        }

        # 白名单：只允许这些列名，防止SQL注入
        allowed_users_upgrade_columns = {
            "billing_cycle",
            "last_paid_amount",
            "subscription_start",
        }

        for field_name, field_def in new_fields.items():
            if field_name not in cols:
                # 使用安全的ALTER TABLE函数
                if field_name in allowed_users_upgrade_columns:
                    _safe_alter_table_add_column(
                        c, "users", field_name, field_def, allowed_users_upgrade_columns
                    )
                else:
                    raise ValueError(
                        f"不允许的列名: {field_name}. "
                        f"只允许使用以下列名: "
                        f"{sorted(allowed_users_upgrade_columns)}"
                    )

        # 2. 添加 payment_orders 表的升级相关字段
        # 首先检查表是否存在
        c.execute(check_sql, ("payment_orders",))
        if not c.fetchone():
            conn.commit()
            return  # 表不存在，无需升级
        payment_cols = _get_table_columns(c, "payment_orders")

        payment_new_fields = {
            "is_upgrade": "INTEGER DEFAULT 0",
            "upgrade_from_plan": "TEXT",
            "upgrade_to_plan": "TEXT",
            "remaining_value": "REAL DEFAULT 0",
        }

        # 白名单：只允许这些列名，防止SQL注入
        allowed_payment_orders_upgrade_columns = {
            "is_upgrade",
            "upgrade_from_plan",
            "upgrade_to_plan",
            "remaining_value",
        }

        for field_name, field_def in payment_new_fields.items():
            if field_name not in payment_cols:
                # 使用安全的ALTER TABLE函数
                if field_name in allowed_payment_orders_upgrade_columns:
                    _safe_alter_table_add_column(
                        c,
                        "payment_orders",
                        field_name,
                        field_def,
                        allowed_payment_orders_upgrade_columns,
                    )
                else:
                    raise ValueError(
                        f"不允许的列名: {field_name}. "
                        f"只允许使用以下列名: "
                        f"{sorted(allowed_payment_orders_upgrade_columns)}"
                    )

        # 3. 创建升级历史表
        upgrade_history_sql = """
            CREATE TABLE IF NOT EXISTS subscription_upgrade_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                from_plan TEXT NOT NULL,
                to_plan TEXT NOT NULL,
                from_cycle TEXT,
                to_cycle TEXT,
                upgrade_time INTEGER NOT NULL,
                remaining_value REAL DEFAULT 0,
                difference_paid REAL DEFAULT 0,
                target_price REAL NOT NULL,
                payment_order_id TEXT,
                created_at INTEGER DEFAULT (strftime('%s', 'now')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """
        _safe_execute_create_table(c, upgrade_history_sql)

        conn.commit()


def _upgrade_users_security_questions():
    """升级：新增用户安全问题相关字段"""
    # 白名单：只允许这些列名，防止SQL注入
    allowed_users_columns = {
        "security_q1",
        "security_a1",
        "security_q2",
        "security_a2",
        "reset_locked_until",
        "reset_attempt_count",
        "reset_last_attempt",
    }

    with get_db_connection() as (conn, c):
        # 检测实际连接类型
        if _is_postgresql_connection(conn):
            # PostgreSQL跳过（表结构应该已经正确）
            return
        # 首先检查表是否存在
        check_sql = _safe_adapt_sql(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", conn
        )
        c.execute(check_sql, ("users",))
        if not c.fetchone():
            return  # 表不存在，无需升级
        cols = _get_table_columns(c, "users")
        new_cols = {
            "security_q1": "TEXT",
            "security_a1": "TEXT",
            "security_q2": "TEXT",
            "security_a2": "TEXT",
            "reset_locked_until": "REAL",
            "reset_attempt_count": "INTEGER DEFAULT 0",
            "reset_last_attempt": "REAL",
        }
        for col, def_sql in new_cols.items():
            # 使用安全的ALTER TABLE函数
            if col not in cols:
                _safe_alter_table_add_column(
                    c, "users", col, def_sql, allowed_users_columns
                )
        conn.commit()


def _upgrade_users_logistics_templates_limit():
    """升级：新增用户物流模板限制字段"""
    # 白名单：只允许这些列名，防止SQL注入
    allowed_users_columns = {"logistics_templates_limit"}

    with get_db_connection() as (conn, c):
        # 检测实际连接类型
        if _is_postgresql_connection(conn):
            # PostgreSQL跳过（表结构应该已经正确）
            return
        # 首先检查表是否存在
        check_sql = _safe_adapt_sql(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", conn
        )
        c.execute(check_sql, ("users",))
        if not c.fetchone():
            return  # 表不存在，无需升级
        cols = _get_table_columns(c, "users")
        new_cols = {"logistics_templates_limit": "INTEGER DEFAULT -1"}
        for col, def_sql in new_cols.items():
            # 使用安全的ALTER TABLE函数
            if col not in cols:
                _safe_alter_table_add_column(
                    c, "users", col, def_sql, allowed_users_columns
                )
        conn.commit()


def _safe_execute_create_table(cursor, sql: str):
    """安全执行CREATE TABLE语句，自动处理AUTOINCREMENT"""
    import re

    # 从cursor获取connection对象以检测类型
    try:
        conn = cursor.connection
    except AttributeError:
        conn = None

    # 检测实际连接类型
    is_pg = conn and _is_postgresql_connection(conn)

    # 只有PostgreSQL连接才需要适配SQL
    if is_pg:
        adapted_sql = adapt_sql(sql)
        # 确保AUTOINCREMENT被移除（双重保险）
        if "AUTOINCREMENT" in adapted_sql.upper():
            adapted_sql = re.sub(
                r"INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT",
                "SERIAL PRIMARY KEY",
                adapted_sql,
                flags=re.IGNORECASE | re.MULTILINE,
            )
            adapted_sql = re.sub(
                r"\s+AUTOINCREMENT\b",
                "",
                adapted_sql,
                flags=re.IGNORECASE | re.MULTILINE,
            )
        # 最终检查（仅对PostgreSQL）
        if "AUTOINCREMENT" in adapted_sql.upper():
            raise ValueError(f"SQL适配失败，仍包含AUTOINCREMENT: {adapted_sql[:300]}")
        cursor.execute(adapted_sql)
    else:
        # SQLite连接直接执行原始SQL（可能包含strftime等SQLite特有语法）
        cursor.execute(sql)


def _safe_fetchone(cursor, execute_result=None) -> Any:
    """安全执行fetchone，兼容execute返回值"""
    fetcher = None
    if execute_result is not None:
        fetcher = getattr(execute_result, "fetchone", None)
    elif hasattr(getattr(cursor, "execute", None), "return_value"):
        fallback_result = getattr(cursor.execute, "return_value")
        fetcher = getattr(fallback_result, "fetchone", None)
    fetch_callable = fetcher if callable(fetcher) else None
    if fetch_callable is not None:
        try:
            return fetch_callable()
        except DB_EXCEPTIONS:
            pass
        except (AttributeError, TypeError):
            pass
    return cursor.fetchone()


def _ensure_serial_primary_key(conn, cursor, table_name: str):
    """确保PostgreSQL表的id列具备自增序列"""
    # print(f"DEBUG: Checking table {table_name}")
    is_pg = _is_postgresql_connection(conn)
    if not is_pg:
        # print(f"DEBUG: Not PostgreSQL connection for {table_name}")
        return

    safe_table = table_name.lower()
    if not safe_table.replace("_", "").isalnum():
        return

    try:
        cursor.execute(
            """
            SELECT column_default
            FROM information_schema.columns
            WHERE table_name = %s AND column_name = 'id'
            """,
            (safe_table,),
        )
        try:
            result = cursor.fetchone()
        except DB_EXCEPTIONS:
            # fetchone失败时返回
            return
        if not result:
            return
        column_default = result[0]
        if column_default:
            return

        sequence_name = f"{safe_table}_id_seq"
        cursor.execute(
            """
            SELECT 1 FROM information_schema.sequences
            WHERE sequence_name = %s
            """,
            (sequence_name,),
        )
        if not cursor.fetchone():
            cursor.execute(f"CREATE SEQUENCE {sequence_name}")

        cursor.execute(
            f"""
            ALTER TABLE {safe_table}
            ALTER COLUMN id SET DEFAULT nextval('{sequence_name}')
            """
        )
        cursor.execute(f"ALTER SEQUENCE {sequence_name} OWNED BY {safe_table}.id")
        cursor.execute(f"SELECT COALESCE(MAX(id), 0) FROM {safe_table}")
        max_id = cursor.fetchone()
        max_id_value = max_id[0] if max_id and max_id[0] else 0
        next_value = max(1, max_id_value + 1)
        cursor.execute(f"SELECT setval('{sequence_name}', %s, false)", (next_value,))
        conn.commit()
    except DB_EXCEPTIONS as exc:
        try:
            conn.rollback()
        except DB_EXCEPTIONS:
            pass
        # 如果序列修复失败，不阻塞主流程（记录后忽略）
        import os

        if not os.getenv("PYTEST_CURRENT_TEST"):
            import traceback

            print(f"[WARN] 序列修复失败: {exc}")
            traceback.print_exc()


def _ensure_unique_constraint(
    conn, cursor, table_name: str, columns: Tuple[str, ...], constraint_name: str
):
    """确保PostgreSQL表上存在指定列的唯一约束"""
    if not _is_postgresql_connection(conn):
        return

    safe_table = table_name.lower()
    if not safe_table.replace("_", "").isalnum():
        return

    try:
        cursor.execute(
            """
            SELECT 1
            FROM information_schema.table_constraints
            WHERE table_name = %s
              AND constraint_name = %s
            """,
            (safe_table, constraint_name),
        )
        try:
            if cursor.fetchone():
                return
        except DB_EXCEPTIONS:
            # fetchone失败时继续执行（可能约束不存在）
            pass
            return

        normalized_target = tuple(sorted(columns))
        cursor.execute(
            """
            SELECT tc.constraint_name,
                   ARRAY_AGG(ccu.column_name ORDER BY ccu.column_name)
            FROM information_schema.table_constraints tc
            JOIN information_schema.constraint_column_usage ccu
              ON tc.constraint_name = ccu.constraint_name
            WHERE tc.table_name = %s
              AND tc.constraint_type IN ('UNIQUE', 'PRIMARY KEY')
            GROUP BY tc.constraint_name
            """,
            (safe_table,),
        )
        rows = cursor.fetchall() or []
        for _, cols in rows:
            if tuple(sorted(cols)) == normalized_target:
                return

        columns_sql = ", ".join(columns)
        cursor.execute(
            f"""
            ALTER TABLE {safe_table}
            ADD CONSTRAINT {constraint_name}
            UNIQUE ({columns_sql})
            """
        )
        conn.commit()
    except DB_EXCEPTIONS as exc:
        # 执行或commit失败时尝试回滚
        try:
            conn.rollback()
        except DB_EXCEPTIONS:
            pass
        try:
            conn.rollback()
        except DB_EXCEPTIONS:
            pass
        import os

        if not os.getenv("PYTEST_CURRENT_TEST"):
            import traceback

            print(f"[WARN] 创建唯一约束失败: {exc}")
            traceback.print_exc()


def _ensure_foreign_key(
    conn,
    cursor,
    table_name: str,
    constraint_name: str,
    column: str,
    ref_table: str,
    ref_column: str = "id",
):
    """确保PostgreSQL表上存在指定的外键约束"""
    if not _is_postgresql_connection(conn):
        return

    safe_table = table_name.lower()
    if not safe_table.replace("_", "").isalnum():
        return

    cursor.execute(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_name = %s
        """,
        (safe_table,),
    )
    if cursor.fetchone() is None:
        return

    cursor.execute(
        """
        SELECT constraint_name
        FROM information_schema.table_constraints
        WHERE table_name = %s
          AND constraint_type = 'FOREIGN KEY'
          AND constraint_name = %s
        """,
        (safe_table, constraint_name),
    )
    if cursor.fetchone():
        return

    column_sql = column.lower()
    ref_table_sql = ref_table.lower()
    ref_column_sql = ref_column.lower()
    try:
        cursor.execute(
            f"""
            SELECT 1
            FROM {safe_table} child
            LEFT JOIN {ref_table_sql} parent
              ON child.{column_sql} = parent.{ref_column_sql}
            WHERE child.{column_sql} IS NOT NULL
              AND parent.{ref_column_sql} IS NULL
            LIMIT 1
            """
        )
        if cursor.fetchone():
            cursor.execute(
                f"""
                DELETE FROM {safe_table}
                WHERE {column_sql} IS NOT NULL
                  AND {column_sql} NOT IN (
                      SELECT {ref_column_sql}
                      FROM {ref_table_sql}
                  )
                """
            )
            conn.commit()
        cursor.execute(
            f"""
            ALTER TABLE {safe_table}
            ADD CONSTRAINT {constraint_name}
            FOREIGN KEY ({column_sql})
            REFERENCES {ref_table_sql} ({ref_column_sql})
            """
        )
        conn.commit()
    except DB_EXCEPTIONS as exc:
        try:
            conn.rollback()
        except DB_EXCEPTIONS:
            pass
        import os

        if not os.getenv("PYTEST_CURRENT_TEST"):
            import traceback

            print(f"[WARN] 创建外键约束失败: {exc}")
            traceback.print_exc()


def _cleanup_duplicate_ids(conn, cursor, table_name: str):
    """移除指定表中重复的id记录（PostgreSQL专用）"""
    if not _is_postgresql_connection(conn):
        return
    safe_table = table_name.lower()
    if not safe_table.replace("_", "").isalnum():
        return
    try:
        cursor.execute(
            f"""
            DELETE FROM {safe_table} a
            USING {safe_table} b
            WHERE a.id = b.id AND a.ctid > b.ctid
            """
        )
        try:
            conn.commit()
        except DB_EXCEPTIONS:
            # commit失败时尝试回滚
            try:
                conn.rollback()
            except DB_EXCEPTIONS:
                pass
    except DB_EXCEPTIONS:
        try:
            conn.rollback()
        except DB_EXCEPTIONS:
            pass


def _cleanup_duplicate_rows(conn, cursor, table_name: str, columns: Tuple[str, ...]):
    """按指定列组合去重，保留最早记录"""
    if not _is_postgresql_connection(conn):
        return
    safe_table = table_name.lower()
    if not safe_table.replace("_", "").isalnum():
        return
    if not columns:
        return
    join_conditions = " AND ".join([f"a.{col} = b.{col}" for col in columns])
    try:
        cursor.execute(
            f"""
            DELETE FROM {safe_table} a
            USING {safe_table} b
            WHERE {join_conditions}
              AND a.ctid > b.ctid
            """
        )
        conn.commit()
    except DB_EXCEPTIONS:
        try:
            conn.rollback()
        except DB_EXCEPTIONS:
            pass


def _ensure_postgresql_schema(conn, cursor):
    """确保PostgreSQL关键表结构完整"""
    if not _is_postgresql_connection(conn):
        return

    critical_tables = [
        "users",
        "products",
        "logistics",
        "payment_orders",
        "login_attempts",
        "admin_action_log",
        "password_recovery_log",
        "alert_records",
        "user_behavior_log",
        "statistics_cache",
        "plans",
        "user_login_log",
        "subscription_upgrade_history",
        "trusted_devices",
        "audit_logs",
    ]
    for table in critical_tables:
        _ensure_serial_primary_key(conn, cursor, table)

    _ensure_unique_constraint(
        conn, cursor, "users", ("username",), "users_username_key"
    )
    _ensure_unique_constraint(conn, cursor, "users", ("email",), "users_email_key")
    _ensure_unique_constraint(conn, cursor, "users", ("id",), "users_id_key")
    _cleanup_duplicate_rows(conn, cursor, "system_config", ("config_key",))
    _ensure_unique_constraint(
        conn, cursor, "system_config", ("config_key",), "system_config_config_key_key"
    )
    _cleanup_duplicate_rows(conn, cursor, "statistics_cache", ("cache_key",))
    _ensure_unique_constraint(
        conn,
        cursor,
        "statistics_cache",
        ("cache_key",),
        "statistics_cache_cache_key_key",
    )
    _ensure_unique_constraint(
        conn,
        cursor,
        "trusted_devices",
        ("user_id", "device_fingerprint"),
        "trusted_devices_user_device_key",
    )
    _ensure_unique_constraint(
        conn, cursor, "user_lockouts", ("identifier",), "user_lockouts_identifier_key"
    )
    _cleanup_duplicate_ids(conn, cursor, "user_login_log")
    _ensure_unique_constraint(
        conn, cursor, "user_login_log", ("id",), "user_login_log_id_key"
    )
    _ensure_foreign_key(
        conn, cursor, "products", "products_user_id_fkey", "user_id", "users"
    )
    _ensure_foreign_key(
        conn, cursor, "logistics", "logistics_user_id_fkey", "user_id", "users"
    )
    try:
        conn.commit()
    except DB_EXCEPTIONS:
        # commit失败时尝试回滚
        try:
            conn.rollback()
        except DB_EXCEPTIONS:
            pass


def _upgrade_statistics_tables():
    """升级：添加统计与运营看板相关表"""
    with get_db_connection() as (conn, c):
        # 1. 创建用户登录日志表
        user_login_log_sql_raw = """
            CREATE TABLE IF NOT EXISTS user_login_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                login_time INTEGER NOT NULL,
                ip_address TEXT,
                user_agent TEXT,
                device_type TEXT,
                created_at INTEGER DEFAULT (strftime('%s', 'now')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """
        # 只有PostgreSQL连接才需要适配SQL
        user_login_log_sql = _safe_adapt_sql(user_login_log_sql_raw, conn)
        _safe_execute_create_table(c, user_login_log_sql)

        # 为登录日志创建索引以提升查询性能
        index_sql1 = """
            CREATE INDEX IF NOT EXISTS idx_user_login_log_user_id
            ON user_login_log(user_id)
        """
        index_sql2 = """
            CREATE INDEX IF NOT EXISTS idx_user_login_log_login_time
            ON user_login_log(login_time)
        """
        c.execute(_safe_adapt_sql(index_sql1, conn))
        c.execute(_safe_adapt_sql(index_sql2, conn))

        # 2. 创建管理员操作日志表（增强版）
        admin_action_log_sql_raw = """
            CREATE TABLE IF NOT EXISTS admin_action_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER NOT NULL,
                action_type TEXT NOT NULL,
                action_detail TEXT,
                target_user_id INTEGER,
                target_type TEXT,
                ip_address TEXT,
                created_at INTEGER DEFAULT (strftime('%s', 'now')),
                FOREIGN KEY (admin_id) REFERENCES users(id),
                FOREIGN KEY (target_user_id) REFERENCES users(id)
            )
        """
        admin_action_log_sql = _safe_adapt_sql(admin_action_log_sql_raw, conn)
        _safe_execute_create_table(c, admin_action_log_sql)

        c.execute(
            _safe_adapt_sql(
                """
            CREATE INDEX IF NOT EXISTS idx_admin_action_log_admin_id
            ON admin_action_log(admin_id)
        """,
                conn,
            )
        )
        c.execute(
            _safe_adapt_sql(
                """
            CREATE INDEX IF NOT EXISTS idx_admin_action_log_created_at
            ON admin_action_log(created_at)
        """,
                conn,
            )
        )

        # 3. 创建密码找回日志表
        password_recovery_log_sql_raw = """
            CREATE TABLE IF NOT EXISTS password_recovery_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                ip_address TEXT,
                event_type TEXT NOT NULL,
                success INTEGER DEFAULT 0,
                attempt_count INTEGER DEFAULT 0,
                admin_name TEXT,
                created_at INTEGER DEFAULT (strftime('%s', 'now'))
            )
        """
        password_recovery_log_sql = _safe_adapt_sql(password_recovery_log_sql_raw, conn)
        _safe_execute_create_table(c, password_recovery_log_sql)

        c.execute(
            _safe_adapt_sql(
                """
            CREATE INDEX IF NOT EXISTS idx_password_recovery_log_username
            ON password_recovery_log(username)
        """,
                conn,
            )
        )
        c.execute(
            _safe_adapt_sql(
                """
            CREATE INDEX IF NOT EXISTS idx_password_recovery_log_created_at
            ON password_recovery_log(created_at)
        """,
                conn,
            )
        )

        # 4. 创建异常告警记录表
        alert_records_sql_raw = """
            CREATE TABLE IF NOT EXISTS alert_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_type TEXT NOT NULL,
                alert_level TEXT NOT NULL,
                description TEXT NOT NULL,
                threshold_value REAL,
                actual_value REAL,
                status TEXT DEFAULT 'unhandled',
                handled_by INTEGER,
                handled_at INTEGER,
                handle_note TEXT,
                created_at INTEGER DEFAULT (strftime('%s', 'now')),
                FOREIGN KEY (handled_by) REFERENCES users(id)
            )
        """
        alert_records_sql = _safe_adapt_sql(alert_records_sql_raw, conn)
        _safe_execute_create_table(c, alert_records_sql)

        c.execute(
            _safe_adapt_sql(
                """
            CREATE INDEX IF NOT EXISTS idx_alert_records_created_at
            ON alert_records(created_at)
        """,
                conn,
            )
        )
        c.execute(
            _safe_adapt_sql(
                """
            CREATE INDEX IF NOT EXISTS idx_alert_records_status
            ON alert_records(status)
        """,
                conn,
            )
        )

        # 5. 创建统计数据缓存表
        statistics_cache_sql_raw = """
            CREATE TABLE IF NOT EXISTS statistics_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cache_key TEXT UNIQUE NOT NULL,
                cache_data TEXT NOT NULL,
                expires_at INTEGER NOT NULL,
                created_at INTEGER DEFAULT (strftime('%s', 'now')),
                updated_at INTEGER DEFAULT (strftime('%s', 'now'))
            )
        """
        statistics_cache_sql = _safe_adapt_sql(statistics_cache_sql_raw, conn)
        _safe_execute_create_table(c, statistics_cache_sql)

        c.execute(
            _safe_adapt_sql(
                """
            CREATE INDEX IF NOT EXISTS idx_statistics_cache_key
            ON statistics_cache(cache_key)
        """,
                conn,
            )
        )
        c.execute(
            _safe_adapt_sql(
                """
            CREATE INDEX IF NOT EXISTS idx_statistics_cache_expires_at
            ON statistics_cache(expires_at)
        """,
                conn,
            )
        )

        # 6. 创建用户行为记录表（新增）
        user_behavior_log_sql_raw = """
            CREATE TABLE IF NOT EXISTS user_behavior_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                behavior_type TEXT NOT NULL,
                behavior_detail TEXT,
                calculation_mode TEXT,
                created_at INTEGER DEFAULT (strftime('%s', 'now')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """
        user_behavior_log_sql = _safe_adapt_sql(user_behavior_log_sql_raw, conn)
        _safe_execute_create_table(c, user_behavior_log_sql)

        c.execute(
            _safe_adapt_sql(
                """
            CREATE INDEX IF NOT EXISTS idx_user_behavior_user_id
            ON user_behavior_log(user_id)
        """,
                conn,
            )
        )
        c.execute(
            _safe_adapt_sql(
                """
            CREATE INDEX IF NOT EXISTS idx_user_behavior_type
            ON user_behavior_log(behavior_type)
        """,
                conn,
            )
        )
        c.execute(
            _safe_adapt_sql(
                """
            CREATE INDEX IF NOT EXISTS idx_user_behavior_created_at
            ON user_behavior_log(created_at)
        """,
                conn,
            )
        )

        # 7. 创建预警配置表（新增）
        alert_config_sql_raw = """
            CREATE TABLE IF NOT EXISTS alert_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                metric_name TEXT NOT NULL,
                threshold_value REAL,
                comparison_type TEXT,
                is_enabled INTEGER DEFAULT 1,
                notification_method TEXT DEFAULT 'system',
                created_at INTEGER DEFAULT (strftime('%s', 'now')),
                updated_at INTEGER DEFAULT (strftime('%s', 'now'))
            )
        """
        alert_config_sql = _safe_adapt_sql(alert_config_sql_raw, conn)
        _safe_execute_create_table(c, alert_config_sql)

        c.execute(
            _safe_adapt_sql(
                """
            CREATE INDEX IF NOT EXISTS idx_alert_config_metric_name
            ON alert_config(metric_name)
        """,
                conn,
            )
        )
        c.execute(
            _safe_adapt_sql(
                """
            CREATE INDEX IF NOT EXISTS idx_alert_config_is_enabled
            ON alert_config(is_enabled)
        """,
                conn,
            )
        )

        # 8. 为payment_orders表添加order_type字段（如果不存在）
        # 首先检查表是否存在
        if not _is_postgresql_connection(conn):
            check_sql = _safe_adapt_sql(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?", conn
            )
            c.execute(check_sql, ("payment_orders",))
            if not c.fetchone():
                conn.commit()
                return  # 表不存在，无需升级
        cols = _get_table_columns(c, "payment_orders")
        if "order_type" not in cols:
            # ALTER TABLE语句在PostgreSQL和SQLite中语法相同，但需要适配占位符
            sql_raw = """
                ALTER TABLE payment_orders
                ADD COLUMN order_type TEXT DEFAULT NULL
            """
            sql = _safe_adapt_sql(sql_raw, conn)
            c.execute(sql)
            # 创建索引
            c.execute(
                _safe_adapt_sql(
                    """
                CREATE INDEX IF NOT EXISTS idx_payment_orders_order_type
                ON payment_orders(order_type)
            """,
                    conn,
                )
            )

        # 8. 创建套餐配置表（新增）
        plans_sql_raw = """
            CREATE TABLE IF NOT EXISTS plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plan_code TEXT UNIQUE NOT NULL,
                plan_name TEXT NOT NULL,
                display_price_month REAL NOT NULL,
                display_price_year REAL NOT NULL,
                actual_price_month REAL NOT NULL,
                actual_price_year REAL NOT NULL,
                test_price_month REAL NOT NULL DEFAULT 0,
                test_price_year REAL NOT NULL DEFAULT 0,
                calc_limit INTEGER NOT NULL DEFAULT -1,
                logistics_limit INTEGER NOT NULL DEFAULT 1,
                description TEXT,
                features TEXT,
                is_active INTEGER DEFAULT 1,
                sort_order INTEGER DEFAULT 0,
                created_at INTEGER DEFAULT (strftime('%s', 'now')),
                updated_at INTEGER DEFAULT (strftime('%s', 'now'))
            )
        """
        plans_sql = _safe_adapt_sql(plans_sql_raw, conn)
        _safe_execute_create_table(c, plans_sql)

        # 为plans表创建索引
        c.execute(
            _safe_adapt_sql(
                """
            CREATE INDEX IF NOT EXISTS idx_plans_code
            ON plans(plan_code)
        """,
                conn,
            )
        )
        c.execute(
            _safe_adapt_sql(
                """
            CREATE INDEX IF NOT EXISTS idx_plans_active
            ON plans(is_active)
        """,
                conn,
            )
        )
        c.execute(
            _safe_adapt_sql(
                """
            CREATE INDEX IF NOT EXISTS idx_plans_sort_order
            ON plans(sort_order)
        """,
                conn,
            )
        )

        # 9. 初始化默认套餐数据（如果表为空）
        sql = _safe_adapt_sql("SELECT COUNT(*) FROM plans", conn)
        c.execute(sql)
        result = c.fetchone()
        count = result[0] if result else 0
        if count == 0:
            # 免费版
            sql = _safe_adapt_sql(
                """
                INSERT INTO plans (
                    plan_code, plan_name,
                    display_price_month, display_price_year,
                    actual_price_month, actual_price_year,
                    test_price_month, test_price_year,
                    calc_limit, logistics_limit,
                    description, features, sort_order
                ) VALUES (
                    ?, ?,
                    ?, ?,
                    ?, ?,
                    ?, ?,
                    ?, ?,
                    ?, ?, ?
                )
            """,
                conn,
            )
            c.execute(
                sql,
                (
                    "free",
                    "免费版",
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    10,
                    1,
                    "适合初次体验的用户",
                    "每日10次计算|1个物流模板|基础功能",
                    1,
                ),
            )

            # 效率版
            c.execute(
                sql,
                (
                    "efficiency",
                    "效率版",
                    9.9,
                    99,
                    9.9,
                    99,
                    1.1,
                    1.2,
                    500,
                    3,
                    "适合中小规模卖家",
                    "每月500次计算|3个物流模板|优先客服",
                    2,
                ),
            )

            # 专业版
            c.execute(
                sql,
                (
                    "professional",
                    "专业版",
                    149,
                    1499,
                    149,
                    1499,
                    1.3,
                    1.4,
                    -1,
                    10,
                    "适合大规模专业卖家",
                    "无限次计算|10个物流模板|专属客服|数据导出",
                    3,
                ),
            )

            # 企业版
            c.execute(
                sql,
                (
                    "enterprise",
                    "企业版",
                    299,
                    2988,
                    299,
                    2988,
                    1.5,
                    1.6,
                    -1,
                    -1,
                    "适合企业团队使用",
                    "无限次计算|无限物流模板|API接口|定制开发|7x24服务",
                    4,
                ),
            )

        # 10. 创建审计日志表（audit_logs）
        audit_logs_sql_raw = """
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                details TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (admin_id) REFERENCES users(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """
        audit_logs_sql = _safe_adapt_sql(audit_logs_sql_raw, conn)
        _safe_execute_create_table(c, audit_logs_sql)

        c.execute(
            _safe_adapt_sql(
                """
            CREATE INDEX IF NOT EXISTS idx_audit_logs_admin_id
            ON audit_logs(admin_id)
        """,
                conn,
            )
        )
        c.execute(
            _safe_adapt_sql(
                """
            CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id
            ON audit_logs(user_id)
        """,
                conn,
            )
        )
        c.execute(
            _safe_adapt_sql(
                """
            CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp
            ON audit_logs(timestamp)
        """,
                conn,
            )
        )

        conn.commit()


def create_user(
    username, password, role="user", email=None, user_type="free", is_test_user=False
):
    """创建用户，返回user_id或None

    Args:
        username: 用户名
        password: 密码
        role: 角色 (user/admin)
        email: 邮箱 (可选)
        user_type: 用户类型 (free/efficiency/professional/enterprise)
        is_test_user: 是否为测试用户，测试用户会在测试结束后自动清理
    """
    # 确保数据库已初始化
    init_db()

    # 验证用户名
    if not username or len(username.strip()) == 0:
        return None

    # 验证密码强度
    password_validation = validate_password_strength(password)
    if not password_validation["is_valid"]:
        return None

    with get_db_connection() as (conn, c):
        # 检查用户名是否已存在（不区分大小写）
        sql_raw = "SELECT username FROM users WHERE LOWER(username) = LOWER(?)"
        sql = _safe_adapt_sql(sql_raw, conn)
        c.execute(sql, (username,))
        existing_user = c.fetchone()

        if existing_user:
            return None  # 用户名已存在

        # 检查邮箱是否已存在（如果提供了邮箱）
        if email:
            sql_raw = "SELECT email FROM users WHERE LOWER(email) = LOWER(?)"
            sql = _safe_adapt_sql(sql_raw, conn)
            existing_email = _safe_execute_fetchone(c, sql, (email,), conn)

            if existing_email:
                return None  # 邮箱已存在

        # 使用bcrypt加盐哈希密码
        hashed_password = hash_password(password)

        # 根据用户类型设置计算次数
        if user_type == "free":
            remaining_calculations = 10
        elif user_type in [
            "test",
            "gratitude",
            "efficiency",
            "professional",
            "enterprise",
        ]:
            remaining_calculations = -1  # 无限次
        else:
            remaining_calculations = 10  # 默认为免费版

        try:
            # 设置注册时间为当前时间
            from datetime import datetime

            created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # 转换is_test_user为整数
            is_test = 1 if is_test_user else 0

            if email:
                # 检测实际连接类型
                if _is_postgresql_connection(conn):
                    # PostgreSQL使用RETURNING子句获取新插入的ID
                    sql_raw = (
                        "INSERT INTO users (username, password, role, email, "
                        "user_type, subscription_type, "
                        "remaining_calculations, "
                        "created_at, is_test_user) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, to_timestamp(?), ?) "
                        "RETURNING id"
                    )
                    sql = _safe_adapt_sql(sql_raw, conn)
                    # created_at需要转换为时间戳
                    created_at_ts = int(
                        datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S").timestamp()
                    )
                    c.execute(
                        sql,
                        (
                            username,
                            hashed_password,
                            role,
                            email,
                            user_type,
                            user_type,
                            remaining_calculations,
                            created_at_ts,
                            is_test,
                        ),
                    )
                    user_id = c.fetchone()[0]
                else:
                    sql_raw = (
                        "INSERT INTO users (username, password, role, email, "
                        "user_type, subscription_type, "
                        "remaining_calculations, "
                        "created_at, is_test_user) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
                    )
                    sql = _safe_adapt_sql(sql_raw, conn)
                    c.execute(
                        sql,
                        (
                            username,
                            hashed_password,
                            role,
                            email,
                            user_type,
                            user_type,
                            remaining_calculations,
                            created_at,
                            is_test,
                        ),
                    )
                    # SQLite使用lastrowid
                    user_id = c.lastrowid
            else:
                # 检测实际连接类型
                if _is_postgresql_connection(conn):
                    # PostgreSQL使用RETURNING子句获取新插入的ID
                    sql_raw = (
                        "INSERT INTO users (username, password, role, "
                        "user_type, subscription_type, "
                        "remaining_calculations, "
                        "created_at, is_test_user) "
                        "VALUES (?, ?, ?, ?, ?, ?, to_timestamp(?), ?) "
                        "RETURNING id"
                    )
                    sql = _safe_adapt_sql(sql_raw, conn)
                    # created_at需要转换为时间戳
                    created_at_ts = int(
                        datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S").timestamp()
                    )
                    c.execute(
                        sql,
                        (
                            username,
                            hashed_password,
                            role,
                            user_type,
                            user_type,
                            remaining_calculations,
                            created_at_ts,
                            is_test,
                        ),
                    )
                    user_id = c.fetchone()[0]
                else:
                    sql_raw = (
                        "INSERT INTO users (username, password, role, "
                        "user_type, subscription_type, "
                        "remaining_calculations, "
                        "created_at, is_test_user) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
                    )
                    sql = _safe_adapt_sql(sql_raw, conn)
                    c.execute(
                        sql,
                        (
                            username,
                            hashed_password,
                            role,
                            user_type,
                            user_type,
                            remaining_calculations,
                            created_at,
                            is_test,
                        ),
                    )
                    # SQLite使用lastrowid
                    user_id = c.lastrowid
            conn.commit()
            # 返回新创建用户的ID
            return user_id
        except sqlite3.IntegrityError:
            return None


# 全局标志，用于缓存数据库初始化状态（避免重复检查）
_db_initialized_cache = {"initialized": False, "lock": threading.Lock()}


def verify_user(identifier, password):
    """验证用户"""
    # 优化：使用缓存避免重复检查表是否存在
    # 在完整测试套件中，数据库通常已经初始化，可以跳过检查
    # 快速检查缓存
    with _db_initialized_cache["lock"]:
        if _db_initialized_cache["initialized"]:
            # 数据库已初始化，跳过检查
            pass
        else:
            # 需要检查表是否存在
            try:
                with get_db_connection() as (conn, c):
                    # 快速检查表是否存在（使用更简单的查询）
                    if _is_postgresql_connection(conn):
                        check_sql = """
                            SELECT EXISTS (
                                SELECT 1 FROM information_schema.tables
                                WHERE table_name = 'users'
                                LIMIT 1
                            )
                        """
                    else:
                        check_sql = (
                            "SELECT 1 FROM sqlite_master "
                            "WHERE type='table' AND name='users' LIMIT 1"
                        )
                    c.execute(check_sql)
                    table_exists = c.fetchone()
                    if table_exists and (
                        (isinstance(table_exists, bool) and table_exists)
                        or (isinstance(table_exists, tuple) and table_exists[0])
                    ):
                        # 表存在，标记为已初始化
                        _db_initialized_cache["initialized"] = True
                    else:
                        # 表不存在，需要初始化
                        init_db()
                        _db_initialized_cache["initialized"] = True
            except (sqlite3.Error, OSError, AttributeError, TypeError, ValueError):
                # 如果检查失败（数据库错误、属性错误、类型错误或值错误），
                # 尝试初始化
                try:
                    init_db()
                    _db_initialized_cache["initialized"] = True
                except (
                    sqlite3.Error,
                    OSError,
                    AttributeError,
                    TypeError,
                    ValueError,
                    RuntimeError,
                    KeyError,
                ):
                    # 初始化失败，继续执行（可能在测试环境中）
                    pass
            except Exception as e:
                # 捕获PostgreSQL错误（如果psycopg2可用）
                try:
                    import psycopg2

                    if isinstance(
                        e,
                        (
                            psycopg2.Error,
                            psycopg2.OperationalError,
                            psycopg2.ProgrammingError,
                        ),
                    ):
                        try:
                            init_db()
                            _db_initialized_cache["initialized"] = True
                        except (
                            sqlite3.Error,
                            OSError,
                            AttributeError,
                            TypeError,
                            ValueError,
                            RuntimeError,
                            KeyError,
                            psycopg2.Error,
                            psycopg2.OperationalError,
                            psycopg2.ProgrammingError,
                        ):
                            # 初始化失败，继续执行
                            pass
                    else:
                        # 其他未预期的异常，继续执行（可能在测试环境中）
                        pass
                except ImportError:
                    # psycopg2不可用，继续执行
                    pass

    with get_db_connection() as (conn, c):
        # 首先根据用户名或邮箱查找用户（用户名不区分大小写）
        # 优化：使用更高效的查询方式，避免LOWER函数（如果可能）
        # 注意：在完整测试套件中，users表可能有很多数据，需要确保有索引
        sql_raw = (
            "SELECT * FROM users WHERE LOWER(username) = LOWER(?) "
            "OR LOWER(email) = LOWER(?) LIMIT 1"
        )
        sql = _safe_adapt_sql(sql_raw, conn)
        user = _safe_execute_fetchone(c, sql, (identifier, identifier), conn)

        if user:
            stored_password = user[2]  # 存储的密码哈希

            # 使用新的密码验证函数（支持bcrypt和旧SHA256格式）
            if verify_password(password, stored_password):
                # 如果是旧格式密码，自动升级到bcrypt
                if not is_bcrypt_hash(stored_password):
                    upgrade_user_password_to_bcrypt(user[0], password)

                return {
                    "id": user[0],
                    "username": user[1],
                    "password": user[2],
                    "role": user[3],
                    "email": user[4],
                }

        return None


def upgrade_user_password_to_bcrypt(user_id, password):
    """
    将用户密码从SHA256格式升级到bcrypt格式

    Args:
        user_id (int): 用户ID
        password (str): 明文密码
    """
    with get_db_connection() as (conn, c):
        new_hashed_password = hash_password(password)

        sql_raw = "UPDATE users SET password = ? WHERE id = ?"
        sql = _safe_adapt_sql(sql_raw, conn)
        c.execute(sql, (new_hashed_password, user_id))
        conn.commit()


def init_db():
    """初始化数据库"""
    with get_db_connection() as (conn, c):
        _ensure_postgresql_schema(conn, c)
        # 1. 三张基础表：users / products / logistics
        users_sql_raw = """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT UNIQUE,
                password TEXT,
                role TEXT,
                email TEXT UNIQUE,
                preferred_mode TEXT DEFAULT 'fast'
            )
        """
        users_sql = _safe_adapt_sql(users_sql_raw, conn)
        c.execute(users_sql)

        products_sql_raw = """
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                name TEXT,
                russian_name TEXT,
                category TEXT,
                model TEXT,
                unit_price REAL,
                weight_g INTEGER,
                length_cm INTEGER,
                width_cm INTEGER,
                height_cm INTEGER,
                is_cylinder INTEGER,
                cylinder_diameter REAL,
                cylinder_length REAL,
                has_battery INTEGER,
                battery_capacity_wh REAL,
                battery_capacity_mah INTEGER,
                battery_voltage REAL,
                has_msds INTEGER,
                has_flammable INTEGER,
                shipping_fee REAL,
                labeling_fee REAL,
                promotion_discount     REAL DEFAULT 0.05,
                promotion_cost_rate    REAL DEFAULT 0.115,
                target_profit_margin   REAL DEFAULT 0.5,
                commission_rate        REAL DEFAULT 0.17,
                withdrawal_fee_rate    REAL DEFAULT 0.01,
                payment_processing_fee REAL DEFAULT 0.01,
                return_rate            REAL DEFAULT 0,
                vat_rate               REAL DEFAULT 0,
                is_test_data           INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """
        products_sql = _safe_adapt_sql(products_sql_raw, conn)
        c.execute(products_sql)

        logistics_sql_raw = """
            CREATE TABLE IF NOT EXISTS logistics (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                name TEXT,
                type TEXT,
                min_days INTEGER,
                max_days INTEGER,
                price_limit REAL,
                price_limit_rub REAL,
                price_min REAL DEFAULT 0,
                price_min_rub REAL DEFAULT 0,
                base_fee REAL DEFAULT 0,
                min_weight INTEGER,
                max_weight INTEGER,
                max_sum_of_sides INTEGER,
                max_longest_side INTEGER,
                max_second_side INTEGER DEFAULT 0,
                min_second_side INTEGER DEFAULT 0,
                min_length INTEGER DEFAULT 0,
                max_cylinder_sum INTEGER DEFAULT 0,
                min_cylinder_sum INTEGER DEFAULT 0,
                max_cylinder_length INTEGER DEFAULT 0,
                min_cylinder_length INTEGER DEFAULT 0,
                volume_mode TEXT
                    CHECK(
                        volume_mode IN (
                            'none',
                            'max_actual_vs_volume',
                            'longest_side'
                        )
                    )
                    DEFAULT 'none',
                longest_side_threshold INTEGER DEFAULT 0,
                allow_battery INTEGER,
                allow_flammable INTEGER,
                battery_capacity_limit_wh REAL DEFAULT 0,
                require_msds INTEGER DEFAULT 0,
                fee_mode TEXT DEFAULT 'base_plus_continue',
                first_fee REAL DEFAULT 0,
                first_weight_g INTEGER DEFAULT 0,
                continue_fee REAL DEFAULT 0,
                continue_unit TEXT DEFAULT '100',
                volume_coefficient REAL DEFAULT 5000,
                delivery_method TEXT DEFAULT 'unknown',
                priority_group TEXT DEFAULT 'D',
                price_limit_currency TEXT DEFAULT 'RUB',
                price_min_currency TEXT DEFAULT 'RUB',
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """
        logistics_sql = _safe_adapt_sql(logistics_sql_raw, conn)
        c.execute(logistics_sql)

        # 创建系统配置表
        system_config_sql = """
            CREATE TABLE IF NOT EXISTS system_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                config_key TEXT UNIQUE NOT NULL,
                config_value TEXT NOT NULL,
                description TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        # 强制适配SQL，确保AUTOINCREMENT被移除
        import re
        from db_adapter import adapt_sql

        _safe_execute_create_table(c, system_config_sql)

        # PostgreSQL需要显式创建唯一约束（如果不存在）
        # 同时检查并修复id列类型（如果是INTEGER而不是SERIAL）
        if _is_postgresql_connection(conn):
            try:
                # 检查表是否存在以及id列的类型
                check_table_sql = """
                    SELECT data_type, column_default
                    FROM information_schema.columns
                    WHERE table_name = 'system_config'
                    AND column_name = 'id'
                """
                c.execute(check_table_sql)
                id_col_info = c.fetchone()

                # 如果表存在但id列不是SERIAL类型，需要修复
                if id_col_info and id_col_info[0] == "integer" and not id_col_info[1]:
                    # id列是INTEGER但没有默认值（不是SERIAL）
                    # 需要创建序列并设置默认值
                    try:
                        # 创建序列
                        create_seq_sql = """
                            CREATE SEQUENCE IF NOT EXISTS system_config_id_seq
                        """
                        c.execute(create_seq_sql)

                        # 设置id列的默认值为序列的下一个值
                        alter_col_sql = """
                            ALTER TABLE system_config
                            ALTER COLUMN id SET DEFAULT
                            nextval('system_config_id_seq')
                        """
                        c.execute(alter_col_sql)

                        # 设置序列的所有者为id列
                        set_owned_sql = """
                            ALTER SEQUENCE system_config_id_seq
                            OWNED BY system_config.id
                        """
                        c.execute(set_owned_sql)
                        conn.commit()
                    except DB_EXCEPTIONS:
                        conn.rollback()
                        # 序列可能已存在，继续

                # 检查唯一约束是否已存在
                check_constraint_sql = """
                    SELECT constraint_name
                    FROM information_schema.table_constraints
                    WHERE table_name = 'system_config'
                    AND constraint_type = 'UNIQUE'
                    AND constraint_name LIKE '%config_key%'
                """
                c.execute(check_constraint_sql)
                if not c.fetchone():
                    # 创建唯一约束
                    create_constraint_sql = """
                        ALTER TABLE system_config
                        ADD CONSTRAINT system_config_config_key_unique
                        UNIQUE (config_key)
                    """
                    c.execute(create_constraint_sql)
                    conn.commit()
            except DB_EXCEPTIONS as e:
                # 约束可能已存在或其他数据库错误，忽略
                conn.rollback()
                # 如果是PostgreSQL的约束已存在错误，这是预期的
                try:
                    import psycopg2

                    if isinstance(
                        e,
                        (
                            psycopg2.errors.DuplicateObject,
                            psycopg2.errors.ProgrammingError,
                        ),
                    ):
                        # 约束已存在，这是预期的，忽略
                        pass
                except (ImportError, AttributeError):
                    # psycopg2未导入或错误类型不匹配，忽略
                    pass
            except (AttributeError, KeyError, TypeError, RuntimeError):
                # 其他非数据库错误（如连接对象属性错误等），忽略
                conn.rollback()

        # 创建支付订单表
        payment_orders_sql = """
            CREATE TABLE IF NOT EXISTS payment_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT UNIQUE NOT NULL,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                description TEXT NOT NULL,
                duration TEXT,
                status TEXT DEFAULT 'PENDING',
                wechat_transaction_id TEXT,
                created_at INTEGER NOT NULL,
                updated_at INTEGER,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """
        adapted_sql = adapt_sql(payment_orders_sql)
        # 确保AUTOINCREMENT被移除（检测实际连接类型）
        if _is_postgresql_connection(conn) and "AUTOINCREMENT" in adapted_sql.upper():
            adapted_sql = re.sub(
                r"INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT",
                "SERIAL PRIMARY KEY",
                adapted_sql,
                flags=re.IGNORECASE,
            )
            adapted_sql = re.sub(
                r"\s+AUTOINCREMENT", "", adapted_sql, flags=re.IGNORECASE
            )
        c.execute(adapted_sql)

        # 初始化系统配置（适配INSERT OR IGNORE）
        # 检测实际连接类型，而不是依赖全局配置
        # 这样可以兼容测试环境中的monkeypatch
        if _is_postgresql_connection(conn):
            insert_config_sql_raw = """
                INSERT INTO system_config
                (config_key, config_value, description)
                VALUES (%s, %s, %s)
                ON CONFLICT DO NOTHING
            """
            insert_config_sql = _safe_adapt_sql(insert_config_sql_raw, conn)
        else:
            insert_config_sql_raw = """
                INSERT OR IGNORE INTO system_config
                (config_key, config_value, description)
                VALUES (?, ?, ?)
            """
            insert_config_sql = _safe_adapt_sql(insert_config_sql_raw, conn)
        c.execute(insert_config_sql, ("open_registration", "false", "是否开放用户注册"))
        conn.commit()
        # 2. 升级旧表（只跑一次）
        _upgrade_table_user_id("products")
        _upgrade_table_user_id("logistics")
        _upgrade_max_size_to_sides("logistics")
        _upgrade_old_volume_battery()
        _upgrade_logistics_new_fields()
        _upgrade_products_cylinder_length()
        _upgrade_products_new_fields()
        _upgrade_logistics_price_min()
        _upgrade_products_return_rate()
        _upgrade_products_is_test_data()
        _upgrade_products_vat_rate()
        _upgrade_users_subscription_fields()
        _upgrade_users_test_flag()
        _upgrade_payment_orders_duration()
        _upgrade_subscription_upgrade_system()
        _upgrade_statistics_tables()
        _upgrade_performance_indexes()
        _upgrade_users_security_questions()
        _upgrade_users_logistics_templates_limit()
        # 3. 初始管理员（避免递归调用）
        # 检测实际连接类型
        is_pg = _is_postgresql_connection(conn)
        sql_raw = "SELECT * FROM users WHERE username = ?"
        sql = _safe_adapt_sql(sql_raw, conn)
        # 确保占位符被转换（如果adapt_sql没有转换，手动转换）
        if is_pg and "?" in sql:
            sql = sql.replace("?", "%s")
        c.execute(sql, ("admin",))
        admin_user = c.fetchone()
        if not admin_user:
            # 使用bcrypt为默认管理员密码加盐哈希
            hashed_password = hash_password("admin123")

            # 检查 user_type 列是否存在
            cols = _get_table_columns(c, "users")
            has_user_type = "user_type" in cols

            if has_user_type:
                # 如果 user_type 列存在，包含在 INSERT 中
                sql_raw = (
                    "INSERT INTO users (username, password, role, email, "
                    "user_type) VALUES (?, ?, ?, ?, ?)"
                )
                sql = _safe_adapt_sql(sql_raw, conn)
                # 确保占位符被转换（如果adapt_sql没有转换，手动转换）
                if is_pg and "?" in sql:
                    sql = sql.replace("?", "%s")
                c.execute(
                    sql,
                    (
                        "admin",
                        hashed_password,
                        "admin",
                        "admin@example.com",
                        "permanent",
                    ),
                )
            else:
                # 如果 user_type 列不存在，不包含在 INSERT 中（使用默认值）
                sql_raw = (
                    "INSERT INTO users (username, password, role, email) "
                    "VALUES (?, ?, ?, ?)"
                )
                sql = _safe_adapt_sql(sql_raw, conn)
                # 确保占位符被转换（如果adapt_sql没有转换，手动转换）
                if is_pg and "?" in sql:
                    sql = sql.replace("?", "%s")
                c.execute(
                    sql,
                    (
                        "admin",
                        hashed_password,
                        "admin",
                        "admin@example.com",
                    ),
                )
            conn.commit()

        # 4. 数据保护策略调整：允许管理员手动删除其产品
        # 取消历史触发器，改为通过业务逻辑防止"非手动路径"误删
        try:
            # 检测实际连接类型
            if _is_postgresql_connection(conn):
                # PostgreSQL需要指定schema和表名，但触发器可能不存在，直接跳过
                sql = """
                    DROP TRIGGER IF EXISTS trg_prevent_delete_admin_products
                    ON products
                """
                c.execute(sql)
            else:
                c.execute("DROP TRIGGER IF EXISTS trg_prevent_delete_admin_products")
            conn.commit()
        except DB_EXCEPTIONS:
            # 如果触发器不存在或其他错误，忽略
            pass

        # 再次确保PostgreSQL关键表结构（在所有表创建及升级后）
        _ensure_postgresql_schema(conn, c)


def add_product(product_data):
    """添加新产品

    Args:
        product_data: 产品数据字典，可包含is_test_data字段
                     - is_test_data=0或未设置：手动创建的产品
                     - is_test_data=1：测试数据
    """
    with get_db_connection() as (conn, c):
        # 确保is_test_data列存在（向后兼容）
        cols = _get_table_columns(c, "products")
        if "is_test_data" not in cols:
            try:
                if _is_postgresql_connection(conn):
                    c.execute(
                        "ALTER TABLE products ADD COLUMN is_test_data INTEGER DEFAULT 0"
                    )
                else:
                    c.execute(
                        "ALTER TABLE products ADD COLUMN is_test_data INTEGER DEFAULT 0"
                    )
                conn.commit()
            except DB_EXCEPTIONS:
                # 如果列已存在或其他错误，忽略
                pass

        # 提取产品数据
        fields = [
            "user_id",
            "name",
            "russian_name",
            "category",
            "model",
            "unit_price",
            "weight_g",
            "length_cm",
            "width_cm",
            "height_cm",
            "is_cylinder",
            "cylinder_diameter",
            "cylinder_length",
            "has_battery",
            "battery_capacity_wh",
            "battery_capacity_mah",
            "battery_voltage",
            "has_msds",
            "has_flammable",
            "shipping_fee",
            "labeling_fee",
            "promotion_cost_rate",
            "target_profit_margin",
            "commission_rate",
            "withdrawal_fee_rate",
            "payment_processing_fee",
            "return_rate",
            "is_test_data",
        ]

        # 构建SQL语句（如果is_test_data未提供，使用默认值0）
        base_fields = [f for f in fields if f != "is_test_data"]
        field_names = ",".join(base_fields) + ",is_test_data"
        placeholder = get_placeholder()
        placeholders = ",".join([placeholder for _ in base_fields]) + f",{placeholder}"

        # 获取值
        values = [product_data.get(field, 0) for field in base_fields]
        # is_test_data默认0（手动创建）
        values.append(product_data.get("is_test_data", 0))

        # 高优先级安全改进：使用sql_security模块进行字段名验证（防止SQL注入）
        try:
            from .sql_security import validate_field_names, SQLSecurityError
        except ImportError:
            from sql_security import validate_field_names, SQLSecurityError

        # 安全的字段名白名单验证（防止SQL注入）
        # 注意：user_id是必需的字段，包含在白名单中
        allowed_product_fields = {
            "user_id",
            "name",
            "russian_name",
            "category",
            "model",
            "unit_price",
            "weight_g",
            "length_cm",
            "width_cm",
            "height_cm",
            "is_cylinder",
            "cylinder_diameter",
            "cylinder_length",
            "has_battery",
            "battery_capacity_wh",
            "battery_capacity_mah",
            "battery_voltage",
            "has_msds",
            "has_flammable",
            "labeling_fee",
            "shipping_fee",
            "promotion_cost_rate",
            "target_profit_margin",
            "commission_rate",
            "withdrawal_fee_rate",
            "payment_processing_fee",
            "return_rate",
            "vat_rate",
            "is_test_data",
        }
        # 使用sql_security模块验证所有字段名
        field_list = [f.strip() for f in field_names.split(",")]
        try:
            validate_field_names(field_list, allowed_product_fields)
        except SQLSecurityError as e:
            raise ValueError(f"SQL安全错误: {e}") from e

        # 检测实际连接类型，适配PostgreSQL和SQLite
        if _is_postgresql_connection(conn):
            # PostgreSQL使用RETURNING子句获取新插入的ID
            sql_raw = (
                f"INSERT INTO products ({field_names}) "
                f"VALUES ({placeholders}) RETURNING id"
            )
            sql = _safe_adapt_sql(sql_raw, conn)
            c.execute(sql, values)
            result = c.fetchone()
            conn.commit()
            return result[0] if result else None
        else:
            # SQLite使用lastrowid
            sql_raw = f"INSERT INTO products ({field_names}) VALUES ({placeholders})"
            sql = _safe_adapt_sql(sql_raw, conn)
            c.execute(sql, values)
            conn.commit()
            return c.lastrowid


# @st.cache_resource(ttl=600)  # 缓存10分钟 - 临时禁用
def get_all_products_for_user(user_id):
    """获取用户的所有产品"""
    with get_db_connection() as (conn, c):
        sql = _safe_adapt_sql("SELECT * FROM products WHERE user_id = ?", conn)
        c.execute(sql, (user_id,))
        products = c.fetchall()
        # 获取列名并转换为字典
        # 检测实际连接类型
        if _is_postgresql_connection(conn):
            columns = [desc[0] for desc in c.description]
        else:
            columns = [col[0] for col in c.description]
        return [dict(zip(columns, product)) for product in products]


def ensure_admin_product_deletion_allowed() -> None:
    """确保不存在阻止删除管理员产品的触发器。

    某些历史环境可能残留触发器，导致手动删除被阻断。
    本函数幂等，若不存在该触发器则忽略。
    """
    with get_db_connection() as (conn, c):
        try:
            # 检测实际连接类型
            if _is_postgresql_connection(conn):
                # PostgreSQL需要指定schema和表名
                sql = """
                    DROP TRIGGER IF EXISTS trg_prevent_delete_admin_products
                    ON products
                """
                c.execute(sql)
            else:
                c.execute("DROP TRIGGER IF EXISTS trg_prevent_delete_admin_products")
            conn.commit()
        except DB_EXCEPTIONS:
            # 如果触发器不存在或其他错误，忽略
            pass


def get_product_by_id(product_id, user_id):
    """根据ID获取产品 - 强制要求用户ID验证"""
    if user_id is None:
        raise ValueError("user_id参数是必需的，以确保数据安全隔离")

    with get_db_connection() as (conn, c):
        # 始终使用?占位符，_safe_execute_fetchone会自动适配
        sql = "SELECT * FROM products WHERE id = ? AND user_id = ?"
        product = _safe_execute_fetchone(c, sql, (product_id, user_id), conn)
        if product:
            # Convert tuple to dict using column names
            columns = [description[0] for description in c.description]
            return dict(zip(columns, product))
        return None


def delete_product(product_id, user_id):
    """删除产品

    基于is_test_data标记判断：
    - is_test_data=0（手动创建）：允许删除
    - is_test_data=1（测试数据）：允许删除（主要用于批量清理）
    """
    with get_db_connection() as (conn, c):
        # 检查产品是否存在且属于该用户
        sql = "SELECT is_test_data FROM products WHERE id = ? AND user_id = ?"
        product = _safe_execute_fetchone(c, sql, (product_id, user_id), conn)

        if not product:
            return False

        # 允许删除（无论是手动还是测试数据都可以删除）
        sql = _safe_adapt_sql("DELETE FROM products WHERE id = ? AND user_id = ?", conn)
        c.execute(sql, (product_id, user_id))
        conn.commit()
        return c.rowcount > 0


def batch_delete_products(product_ids, user_id):
    """批量删除产品

    基于is_test_data标记判断：
    - 只删除属于该用户的产品
    - 建议主要用于清理测试数据（is_test_data=1）
    """
    if not product_ids:
        return 0
    with get_db_connection() as (conn, c):
        # 导入SQL安全工具
        try:
            from .sql_security import build_in_clause, SQLSecurityError
        except ImportError:
            from sql_security import build_in_clause, SQLSecurityError

        # 使用安全的IN子句构建工具
        try:
            in_clause, validated_ids = build_in_clause(product_ids)
        except SQLSecurityError as e:
            raise ValueError(f"SQL安全错误: {e}") from e

        # 使用参数化查询，确保安全
        params = validated_ids + [user_id]
        sql_raw = f"DELETE FROM products WHERE id {in_clause} AND user_id = ?"
        sql = _safe_adapt_sql(sql_raw, conn)
        c.execute(sql, params)
        conn.commit()
        return c.rowcount


def cleanup_test_products(user_id=None):
    """清理测试产品（is_test_data=1）

    Args:
        user_id: 可选，如果指定则只清理该用户的测试产品,
                否则清理所有用户的测试产品

    Returns:
        删除的产品数量
    """
    try:
        with get_db_connection() as (conn, c):
            # 检查is_test_data字段是否存在
            cols = _get_table_columns(c, "products")
            if "is_test_data" not in cols:
                # 如果字段不存在，返回0（不删除任何数据）
                return 0

            # 统一使用整数比较（兼容SQLite和PostgreSQL）
            # 注意：PostgreSQL中is_test_data是INTEGER类型，不能与TRUE比较
            if user_id:
                sql_raw = "DELETE FROM products WHERE is_test_data = 1 AND user_id = ?"
            else:
                sql_raw = "DELETE FROM products WHERE is_test_data = 1"

            sql = _safe_adapt_sql(sql_raw, conn)
            if user_id:
                c.execute(sql, (user_id,))
            else:
                c.execute(sql)
            conn.commit()
            return c.rowcount
    except Exception as e:
        # 如果清理失败，返回0并记录错误（但不抛出异常）
        print(f"清理测试产品时出错: {e}")
        return 0


def update_product(product_id, user_id, updates):
    """更新产品信息"""
    if not updates:
        return False

    # 导入SQL安全工具
    try:
        from .sql_security import build_update_set_clause, SQLSecurityError
    except ImportError:
        from sql_security import build_update_set_clause, SQLSecurityError

    with get_db_connection() as (conn, c):
        # 安全的字段名白名单验证（防止SQL注入）
        allowed_product_fields = {
            "name",
            "russian_name",
            "category",
            "model",
            "unit_price",
            "weight_g",
            "length_cm",
            "width_cm",
            "height_cm",
            "is_cylinder",
            "cylinder_diameter",
            "cylinder_length",
            "has_battery",
            "battery_capacity_wh",
            "battery_capacity_mah",
            "battery_voltage",
            "has_msds",
            "has_flammable",
            "labeling_fee",
            "shipping_fee",
            "promotion_cost_rate",
            "target_profit_margin",
            "commission_rate",
            "withdrawal_fee_rate",
            "payment_processing_fee",
            "return_rate",
            "vat_rate",
            "is_test_data",
        }

        # 使用安全的SQL构建工具
        try:
            set_clause, values = build_update_set_clause(
                updates, allowed_product_fields
            )
        except SQLSecurityError as e:
            raise ValueError(f"SQL安全错误: {e}") from e

        values.extend([product_id, user_id])

        # 使用参数化查询，确保安全
        sql_raw = f"UPDATE products SET {set_clause} WHERE id = ? AND user_id = ?"
        sql = _safe_adapt_sql(sql_raw, conn)
        c.execute(sql, values)
        conn.commit()
        return c.rowcount > 0


def batch_update_pricing_params(product_ids, user_id, pricing_updates):
    """批量更新产品定价参数"""
    if not product_ids or not pricing_updates:
        return 0

    # 导入SQL安全工具
    try:
        from .sql_security import (
            build_update_set_clause,
            build_in_clause,
            SQLSecurityError,
        )
    except ImportError:
        from sql_security import (
            build_update_set_clause,
            build_in_clause,
            SQLSecurityError,
        )

    with get_db_connection() as (conn, c):
        # 安全的字段名白名单验证（防止SQL注入）
        # 注意：允许更新unit_price等基础字段，不仅仅是定价参数
        allowed_pricing_fields = {
            "promotion_cost_rate",
            "target_profit_margin",
            "commission_rate",
            "withdrawal_fee_rate",
            "payment_processing_fee",
            "return_rate",
            "vat_rate",
            "unit_price",
            "labeling_fee",
            "shipping_fee",
        }

        # 使用安全的SQL构建工具
        try:
            set_clause, values = build_update_set_clause(
                pricing_updates, allowed_pricing_fields
            )
            in_clause, validated_ids = build_in_clause(product_ids)
        except SQLSecurityError as e:
            raise ValueError(f"SQL安全错误: {e}") from e

        values.extend(validated_ids)
        values.append(user_id)

        # 使用参数化查询，确保安全
        sql = f"UPDATE products SET {set_clause} WHERE id {in_clause} AND user_id = ?"
        sql = _safe_adapt_sql(sql, conn)
        c.execute(sql, values)
        conn.commit()
        return c.rowcount


def calculate_and_update_priority_groups(user_id):
    """计算并更新物流优先级分组 - 支持用户隔离"""
    with get_db_connection() as (conn, c):
        # 获取指定用户的物流数据
        sql_raw = "SELECT id, type, min_days, max_days FROM logistics WHERE user_id = ?"
        sql = _safe_adapt_sql(sql_raw, conn)
        c.execute(sql, (user_id,))
        logistics_raw = c.fetchall()
        # 将元组转换为字典
        logistics = [
            {"id": row[0], "type": row[1], "min_days": row[2], "max_days": row[3]}
            for row in logistics_raw
        ]

        # 按类型分组
        land_logistics = [log for log in logistics if log["type"] == "land"]
        air_logistics = [log for log in logistics if log["type"] == "air"]

        def calculate_group_averages(logistics_list):
            """计算物流组的平均值"""
            if not logistics_list:
                return 0, 0, 0

            # 过滤出时效不为0的物流（参与平均值计算）
            valid_logistics = [
                log
                for log in logistics_list
                if log["min_days"] > 0 and log["max_days"] > 0
            ]

            if not valid_logistics:
                return 0, 0, 0

            # 计算平均最快时效(A)
            min_days_sum = sum(log["min_days"] for log in valid_logistics)
            avg_fastest = min_days_sum / len(valid_logistics)

            # 计算平均最慢时效(B)
            max_days_sum = sum(log["max_days"] for log in valid_logistics)
            avg_slowest = max_days_sum / len(valid_logistics)

            # 计算每个物流的平均时效(C)的平均值(D)
            avg_times = []
            for log in valid_logistics:
                avg_time = (log["min_days"] + log["max_days"]) / 2
                avg_times.append(avg_time)
            avg_overall = sum(avg_times) / len(avg_times)

            return avg_fastest, avg_slowest, avg_overall

        def assign_priority_group(log, avg_fastest, avg_slowest, avg_overall):
            """为单个物流分配优先级组"""
            min_days = log["min_days"]
            max_days = log["max_days"]

            # 如果时效为0，分配为E组（优先级最低）
            if min_days == 0 and max_days == 0:
                return "E"

            avg_time = (min_days + max_days) / 2

            # 计算有多少个值小于平均值
            count_below_avg = 0
            if min_days < avg_fastest:
                count_below_avg += 1
            if max_days < avg_slowest:
                count_below_avg += 1
            if avg_time < avg_overall:
                count_below_avg += 1

            # 根据数量分配组别
            if count_below_avg == 3:
                return "A"
            elif count_below_avg == 2:
                return "B"
            elif count_below_avg == 1:
                return "C"
            else:
                return "D"

        # 计算陆运组平均值
        land_avg_fastest, land_avg_slowest, land_avg_overall = calculate_group_averages(
            land_logistics
        )

        # 计算空运组平均值
        air_avg_fastest, air_avg_slowest, air_avg_overall = calculate_group_averages(
            air_logistics
        )

        # 更新陆运物流的优先级组
        update_sql_raw = "UPDATE logistics SET priority_group = ? WHERE id = ?"
        update_sql = _safe_adapt_sql(update_sql_raw, conn)
        for log in land_logistics:
            group = assign_priority_group(
                log, land_avg_fastest, land_avg_slowest, land_avg_overall
            )
            c.execute(update_sql, (group, log["id"]))

        # 更新空运物流的优先级组
        for log in air_logistics:
            group = assign_priority_group(
                log, air_avg_fastest, air_avg_slowest, air_avg_overall
            )
            c.execute(update_sql, (group, log["id"]))

        conn.commit()


# @st.cache_resource(ttl=300)  # 缓存5分钟 - 临时禁用
def get_user_subscription_info(user_id):
    """获取用户订阅信息"""
    with get_db_connection() as (conn, c):
        if c is None:
            return None
        # 使用_safe_adapt_sql适配SQL（根据实际连接类型检测）
        sql_raw = (
            "SELECT id, username, user_type, expiry_date, "
            "remaining_calculations, first_login_date, "
            "test_days_remaining, role, subscription_type, "
            "subscription_expires "
            "FROM users WHERE id = ?"
        )
        # 确保SQL适配正确（强制适配）
        sql = _safe_adapt_sql(sql_raw, conn)
        execute_result = c.execute(sql, (user_id,))
        user = _safe_fetchone(c, execute_result)

        if not user:
            return None

        fields = [
            "id",
            "username",
            "user_type",
            "expiry_date",
            "remaining_calculations",
            "first_login_date",
            "test_days_remaining",
            "role",
            "subscription_type",
            "subscription_expires",
        ]

        if isinstance(user, dict):
            return user
        if hasattr(user, "keys"):
            mapped = dict(cast(Mapping[str, Any], user))
            for field in fields:
                mapped.setdefault(field, None)
            return mapped

        values = list(cast(Sequence[Any], user))
        if len(values) < len(fields):
            values.extend([None] * (len(fields) - len(values)))
        return dict(zip(fields, values))


def update_user_subscription(user_id, updates):
    """更新用户订阅信息"""
    with get_db_connection() as (conn, c):
        placeholder = get_placeholder()
        set_clauses = []
        values = []
        for field, value in updates.items():
            set_clauses.append(f"{field} = {placeholder}")
            values.append(value)

        values.append(user_id)

        # 构建SQL并适配（使用占位符，然后根据实际连接类型适配）
        sql_raw = f"UPDATE users SET {', '.join(set_clauses)} WHERE id = {placeholder}"
        sql = _safe_adapt_sql(sql_raw, conn)
        c.execute(sql, values)
        conn.commit()
        return c.rowcount > 0


# @st.cache_resource(ttl=300)  # 缓存5分钟 - 临时禁用
def check_user_subscription_status(user_id):
    """检查用户订阅状态"""
    user_info = get_user_subscription_info(user_id)
    if not user_info:
        return {"valid": False, "message": "用户不存在"}

    # 检查用户角色，如果是admin用户，直接返回管理员状态
    user_role = user_info.get("role", "user")
    if user_role == "admin":
        return {
            "valid": True,
            "message": "管理员用户",
            "user_type": "admin",
            "role": "admin",
        }

    # 优先使用subscription_type字段，如果没有则使用user_type
    user_type = user_info.get("subscription_type") or user_info.get(
        "user_type", "permanent"
    )

    # 永久用户
    if user_type == "permanent":
        return {"valid": True, "message": "永久用户", "user_type": user_type}

    # 测试用户
    if user_type == "test":
        first_login = user_info.get("first_login_date")
        if not first_login:
            return {
                "valid": True,
                "message": "测试用户未开始计时",
                "user_type": user_type,
            }

        try:
            first_login_date = datetime.fromisoformat(first_login)
            days_elapsed = (datetime.now() - first_login_date).days
            remaining_days = 7 - days_elapsed

            if remaining_days <= 0:
                return {
                    "valid": False,
                    "message": "测试期已过期",
                    "user_type": user_type,
                }
            else:
                return {
                    "valid": True,
                    "message": (f"测试用户，剩余{remaining_days}天"),
                    "remaining_days": remaining_days,
                    "user_type": user_type,
                }
        except (ValueError, TypeError):
            return {
                "valid": True,
                "message": "测试用户",
                "user_type": user_type,
            }

    # 按月付费用户
    if user_type == "monthly":
        expiry_date = user_info.get("expiry_date")
        remaining_calculations = user_info.get("remaining_calculations", 0)

        if not expiry_date:
            return {"valid": False, "message": "订阅信息不完整"}

        try:
            # 处理不同的日期格式
            if isinstance(expiry_date, datetime):
                expiry = expiry_date
            elif isinstance(expiry_date, date):
                expiry = datetime.combine(expiry_date, datetime.min.time())
            elif isinstance(expiry_date, str):
                # 尝试解析ISO格式
                if "T" in expiry_date:
                    expiry = datetime.fromisoformat(expiry_date.replace("Z", "+00:00"))
                else:
                    # 纯日期格式，尝试解析
                    try:
                        expiry = datetime.strptime(expiry_date, "%Y-%m-%d")
                    except ValueError:
                        expiry = datetime.fromisoformat(expiry_date)
            else:
                raise ValueError(f"不支持的日期类型: {type(expiry_date)}")

            today = date.today()
            days_remaining = (expiry.date() - today).days
            # 剩余天数为0视为已到期（按日期差）
            if days_remaining <= 0:
                return {
                    "valid": False,
                    "message": "订阅已过期",
                    "remaining_days": 0,
                    "remaining_calculations": remaining_calculations,
                    "user_type": user_type,
                }

            # 格式化计算次数显示
            if remaining_calculations == -1:
                calculations_display = "无限次"
            else:
                calculations_display = f"{remaining_calculations}次"

            return {
                "valid": True,
                "message": (
                    f"按月付费用户，剩余{days_remaining}天，"
                    f"剩余{calculations_display}计算"
                ),
                "remaining_days": days_remaining,
                "remaining_calculations": remaining_calculations,
                "user_type": user_type,
            }
        except (ValueError, TypeError):
            return {
                "valid": False,
                "message": "订阅信息错误",
                "user_type": user_type,
            }

    # 企业用户
    if user_type == "enterprise":
        expiry_date = user_info.get("expiry_date")

        if not expiry_date:
            return {
                "valid": False,
                "message": "订阅信息不完整",
                "user_type": user_type,
            }

        try:
            # 处理不同的日期格式
            if isinstance(expiry_date, datetime):
                expiry = expiry_date
            elif isinstance(expiry_date, date):
                expiry = datetime.combine(expiry_date, datetime.min.time())
            elif isinstance(expiry_date, str):
                # 尝试解析ISO格式
                if "T" in expiry_date:
                    expiry = datetime.fromisoformat(expiry_date.replace("Z", "+00:00"))
                else:
                    # 纯日期格式，尝试解析
                    try:
                        expiry = datetime.strptime(expiry_date, "%Y-%m-%d")
                    except ValueError:
                        expiry = datetime.fromisoformat(expiry_date)
            else:
                raise ValueError(f"不支持的日期类型: {type(expiry_date)}")

            today = date.today()
            days_remaining = (expiry.date() - today).days
            if days_remaining <= 0:
                return {
                    "valid": False,
                    "message": "订阅已过期",
                    "remaining_days": 0,
                    "user_type": user_type,
                }
            return {
                "valid": True,
                "message": f"企业版用户，剩余{days_remaining}天",
                "remaining_days": days_remaining,
                "user_type": user_type,
            }
        except (ValueError, TypeError):
            return {
                "valid": False,
                "message": "订阅信息错误",
                "user_type": user_type,
            }

    # 处理新的用户类型系统
    if user_type in [
        "free",
        "efficiency",
        "professional",
        "enterprise",
        "gratitude",
    ]:
        remaining_calculations = user_info.get("remaining_calculations", 0)

        # 免费版用户：不检查到期时间，仅依据每日计算次数
        if user_type == "free":
            # 兼容历史数据：免费版不应为-1，若为-1则按10次处理并尝试纠正
            if remaining_calculations == -1:
                try:
                    with get_db_connection() as (fix_conn, fix_cur):
                        sql_raw = (
                            "UPDATE users SET remaining_calculations = 10 WHERE id = ?"
                        )
                        sql = _safe_adapt_sql(sql_raw, fix_conn)
                        fix_cur.execute(sql, (user_id,))
                        fix_conn.commit()
                except DB_EXCEPTIONS:
                    pass
                remaining_calculations = 10

            calculations_display = f"{remaining_calculations}次"
            return {
                "valid": True,
                "message": (f"免费版用户，剩余{calculations_display}计算"),
                "remaining_calculations": remaining_calculations,
                "user_type": user_type,
            }

        # 感谢版用户：不检查到期时间，视为永久有效
        if user_type == "gratitude":
            return {
                "valid": True,
                "message": "感谢版用户，永久有效",
                "remaining_days": -1,  # -1表示永久有效
                "remaining_calculations": -1,  # -1表示无限次
                "user_type": user_type,
            }

        # 非免费版和感谢版用户：检查订阅过期时间
        # 优先使用subscription_expires字段，如果没有则使用expiry_date
        subscription_expires = user_info.get("subscription_expires")
        expiry_date = user_info.get("expiry_date")

        if subscription_expires:
            # 使用subscription_expires（Unix时间戳）
            import time

            current_time = int(time.time())
            # 确保subscription_expires是整数类型
            subscription_expires = int(subscription_expires)
            # 使用向上取整，确保用户看到完整的剩余天数
            import math

            days_remaining = math.ceil(
                (subscription_expires - current_time) / (24 * 3600)
            )
        elif expiry_date:
            # 使用expiry_date（ISO格式）
            try:
                expiry = datetime.fromisoformat(expiry_date)
                today = date.today()
                days_remaining = (expiry.date() - today).days
            except (ValueError, TypeError):
                return {
                    "valid": False,
                    "message": "订阅信息错误",
                    "user_type": user_type,
                }
        else:
            return {
                "valid": False,
                "message": "订阅信息不完整",
                "user_type": user_type,
            }

        try:
            if days_remaining <= 0:
                return {
                    "valid": False,
                    "message": "订阅到期，请续订",
                    "remaining_days": 0,
                    "remaining_calculations": remaining_calculations,
                    "user_type": user_type,
                }
            # 使用友好的用户类型名称
            user_type_display_names = {
                "free": "免费版用户",
                "efficiency": "效率版用户",
                "professional": "专业版用户",
                "enterprise": "企业版用户",
                "gratitude": "感谢版用户",
            }
            display_name = user_type_display_names.get(
                user_type,
                f"{user_type}用户",
            )
            # 只有免费版用户才显示计算次数，付费用户都是无限次
            if user_type == "free":
                # 格式化计算次数显示
                if remaining_calculations == -1:
                    calculations_display = "无限次"
                else:
                    calculations_display = f"{remaining_calculations}次"
                message = (
                    f"{display_name}，剩余{days_remaining}天，"
                    f"剩余{calculations_display}计算"
                )
            else:
                # 付费用户不显示计算次数（都是无限次）
                message = f"{display_name}，剩余{days_remaining}天"
            return {
                "valid": True,
                "message": message,
                "remaining_days": days_remaining,
                "remaining_calculations": remaining_calculations,
                "user_type": user_type,
            }
        except (ValueError, TypeError):
            return {
                "valid": False,
                "message": "订阅信息错误",
                "user_type": user_type,
            }
    return {"valid": False, "message": "未知用户类型", "user_type": user_type}


def decrement_user_calculations(user_id):
    """减少用户计算次数（以 subscription_type 优先判定用户类型）。"""
    with get_db_connection() as (conn, c):
        # 获取当前用户信息（包含 subscription_type 用于优先判断）
        sql_raw = (
            "SELECT user_type, subscription_type, "
            "remaining_calculations FROM users WHERE id = ?"
        )
        sql = _safe_adapt_sql(sql_raw, conn)
        user = _safe_execute_fetchone(c, sql, (user_id,), conn)

        if not user:
            return False

        db_user_type = user[0]
        db_subscription_type = user[1] if len(user) > 1 else None
        remaining = user[2] if len(user) > 2 else -1

        # 以 subscription_type 优先，其次回退到 user_type
        user_type = (db_subscription_type or db_user_type or "").strip()

        # admin用户、永久用户、企业用户、感谢版用户、效率版用户、专业版用户不限制次数
        if user_type in [
            "admin",
            "permanent",
            "enterprise",
            "gratitude",
            "efficiency",
            "professional",
        ]:
            return True

        # 测试用户不限制次数
        if user_type == "test":
            return True

        # 免费版用户：按每日次数扣减
        if user_type == "free":
            if remaining <= 0:
                return False
            sql_raw = (
                "UPDATE users SET remaining_calculations = "
                "remaining_calculations - 1 WHERE id = ? "
                "AND remaining_calculations > 0"
            )
            sql = _safe_adapt_sql(sql_raw, conn)
            c.execute(sql, (user_id,))
            conn.commit()
            return c.rowcount > 0

        # 按月付费用户需要检查次数
        if user_type == "monthly":
            if remaining <= 0:
                return False

            sql_raw = (
                "UPDATE users SET remaining_calculations = "
                "remaining_calculations - 1 WHERE id = ? "
                "AND remaining_calculations > 0"
            )
            sql = _safe_adapt_sql(sql_raw, conn)
            c.execute(sql, (user_id,))
            conn.commit()
            return c.rowcount > 0

        return False


def reset_free_users_daily_calculations():
    """每日重置免费用户的计算次数为10次"""
    with get_db_connection() as (conn, c):
        try:
            # 重置所有免费用户的计算次数为10
            c.execute(
                """
                UPDATE users
                SET remaining_calculations = 10
                WHERE user_type = 'free'
                """
            )
            affected_rows = c.rowcount
            conn.commit()

            # 记录日志
            from logger_config import logger

            logger.info(
                f"每日计算次数重置完成：重置了 {affected_rows} 个免费用户的计算次数"
            )

            return affected_rows
        except Exception as e:
            from logger_config import logger

            logger.error(f"重置免费用户计算次数失败: {e}")
            return 0


def update_user_password(user_id, current_password, new_password):
    """更新用户密码"""
    import bcrypt

    with get_db_connection() as (conn, c):
        # 获取当前用户信息
        sql = "SELECT password FROM users WHERE id = ?"
        user = _safe_execute_fetchone(c, sql, (user_id,), conn)

        if not user:
            return False

        # 验证当前密码
        current_password_bytes = current_password.encode("utf-8")
        stored_password = user["password"] if isinstance(user, dict) else user[0]

        if isinstance(stored_password, bytes):
            stored_password = stored_password.decode("utf-8")
        elif not isinstance(stored_password, str):
            stored_password = str(stored_password or "")

        # 支持旧的SHA256和新的bcrypt密码
        if stored_password.startswith("$2b$"):
            # bcrypt密码
            if not bcrypt.checkpw(
                current_password_bytes, stored_password.encode("utf-8")
            ):
                return False
        else:
            # 旧的SHA256密码
            import hashlib

            if hashlib.sha256(current_password_bytes).hexdigest() != stored_password:
                return False

        # 使用bcrypt加密新密码
        new_password_bytes = new_password.encode("utf-8")
        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(new_password_bytes, salt).decode("utf-8")
        # 更新密码
        sql = _safe_adapt_sql("UPDATE users SET password = ? WHERE id = ?", conn)
        c.execute(sql, (hashed_password, user_id))
        conn.commit()
        return True


def delete_user(user_id):
    """删除用户及其相关数据"""

    with get_db_connection() as (conn, c):
        try:
            # 检查用户是否存在
            sql = "SELECT id, username, role FROM users WHERE id = ?"
            user = _safe_execute_fetchone(c, sql, (user_id,), conn)

            if not user:
                print(f"删除失败: 用户 ID={user_id} 不存在")
                return False  # 用户不存在

            print(f"准备删除用户: ID={user[0]}, 用户名={user[1]}, 角色={user[2]}")

            # 不允许删除admin用户
            if user[2] == "admin":
                print(f"删除失败: 用户 {user[1]} 是管理员，不允许删除")
                return False

            # 获取占位符
            placeholder = get_placeholder()

            # 删除用户相关的数据（按外键依赖顺序）
            # 1. 删除用户的产品
            sql_raw = f"DELETE FROM products WHERE user_id = {placeholder}"
            sql = _safe_adapt_sql(sql_raw, conn)
            c.execute(sql, (user_id,))
            rowcount = (
                c.rowcount if hasattr(c, "rowcount") and c.rowcount is not None else 0
            )
            print(f"删除产品: {rowcount} 条")

            # 2. 删除用户的会话记录
            sql_raw = f"DELETE FROM active_sessions WHERE user_id = {placeholder}"
            sql = _safe_adapt_sql(sql_raw, conn)
            c.execute(sql, (user_id,))
            rowcount = (
                c.rowcount if hasattr(c, "rowcount") and c.rowcount is not None else 0
            )
            print(f"删除会话记录: {rowcount} 条")

            # 3. 删除用户的登录尝试记录
            sql_raw = f"DELETE FROM login_attempts WHERE identifier = {placeholder}"
            sql = _safe_adapt_sql(sql_raw, conn)
            c.execute(sql, (user[1],))
            rowcount = (
                c.rowcount if hasattr(c, "rowcount") and c.rowcount is not None else 0
            )
            print(f"删除登录尝试记录: {rowcount} 条")

            # 4. 删除用户的锁定记录
            sql_raw = f"DELETE FROM user_lockouts WHERE identifier = {placeholder}"
            sql = _safe_adapt_sql(sql_raw, conn)
            c.execute(sql, (user[1],))
            rowcount = (
                c.rowcount if hasattr(c, "rowcount") and c.rowcount is not None else 0
            )
            print(f"删除锁定记录: {rowcount} 条")

            # 5. 删除用户的登录/行为日志（统计表中的外键）
            try:
                sql_raw = f"DELETE FROM user_login_log WHERE user_id = {placeholder}"
                sql = _safe_adapt_sql(sql_raw, conn)
                c.execute(sql, (user_id,))
                rowcount = (
                    c.rowcount
                    if hasattr(c, "rowcount") and c.rowcount is not None
                    else 0
                )
                print(f"删除登录日志: {rowcount} 条")
            except (sqlite3.OperationalError, Exception):
                print("登录日志表不存在，跳过")

            try:
                sql_raw = f"DELETE FROM user_behavior_log WHERE user_id = {placeholder}"
                sql = _safe_adapt_sql(sql_raw, conn)
                c.execute(sql, (user_id,))
                rowcount = (
                    c.rowcount
                    if hasattr(c, "rowcount") and c.rowcount is not None
                    else 0
                )
                print(f"删除行为日志: {rowcount} 条")
            except (sqlite3.OperationalError, Exception):
                print("行为日志表不存在，跳过")

            # 6. 删除用户的物流规则
            sql_raw = f"DELETE FROM logistics WHERE user_id = {placeholder}"
            sql = _safe_adapt_sql(sql_raw, conn)
            c.execute(sql, (user_id,))
            rowcount = (
                c.rowcount if hasattr(c, "rowcount") and c.rowcount is not None else 0
            )
            print(f"删除物流规则: {rowcount} 条")

            # 7. 删除用户的升级历史（如果表存在）
            try:
                sql_raw = (
                    f"DELETE FROM subscription_upgrade_history "
                    f"WHERE user_id = {placeholder}"
                )
                sql = _safe_adapt_sql(sql_raw, conn)
                c.execute(sql, (user_id,))
                rowcount = (
                    c.rowcount
                    if hasattr(c, "rowcount") and c.rowcount is not None
                    else 0
                )
                print(f"删除升级历史: {rowcount} 条")
            except (sqlite3.OperationalError, Exception):
                print("升级历史表不存在，跳过")

            # 8. 删除用户的支付订单
            sql_raw = f"DELETE FROM payment_orders WHERE user_id = {placeholder}"
            sql = _safe_adapt_sql(sql_raw, conn)
            c.execute(sql, (user_id,))
            rowcount = (
                c.rowcount if hasattr(c, "rowcount") and c.rowcount is not None else 0
            )
            print(f"删除支付订单: {rowcount} 条")

            # 9. 清理与用户相关的管理员操作日志/告警记录
            try:
                sql_raw = (
                    f"DELETE FROM admin_action_log "
                    f"WHERE admin_id = {placeholder} "
                    f"OR target_user_id = {placeholder}"
                )
                sql = _safe_adapt_sql(sql_raw, conn)
                c.execute(sql, (user_id, user_id))
                rowcount = (
                    c.rowcount
                    if hasattr(c, "rowcount") and c.rowcount is not None
                    else 0
                )
                print(f"删除管理员操作日志: {rowcount} 条")
            except (sqlite3.OperationalError, Exception):
                print("管理员操作日志表不存在，跳过")

            try:
                sql_raw = (
                    f"UPDATE alert_records SET handled_by = NULL "
                    f"WHERE handled_by = {placeholder}"
                )
                sql = _safe_adapt_sql(sql_raw, conn)
                c.execute(sql, (user_id,))
                rowcount = (
                    c.rowcount
                    if hasattr(c, "rowcount") and c.rowcount is not None
                    else 0
                )
                print(f"置空告警处理人: {rowcount} 条")
            except (sqlite3.OperationalError, Exception):
                print("告警记录表不存在，跳过")

            # 10. 删除用户本身
            sql_raw = f"DELETE FROM users WHERE id = {placeholder}"
            sql = _safe_adapt_sql(sql_raw, conn)
            c.execute(sql, (user_id,))
            rowcount = (
                c.rowcount if hasattr(c, "rowcount") and c.rowcount is not None else 0
            )
            print(f"删除用户: {rowcount} 条")

            conn.commit()
            print(f"✅ 成功删除用户 {user[1]} (ID={user_id})")
            return True

        except sqlite3.Error as e:
            print(f"❌ 数据库错误: {e}")
            import traceback

            traceback.print_exc()
            conn.rollback()
            return False
        except (Exception,) as e:
            print(f"❌ 删除用户失败: {e}")
            import traceback

            traceback.print_exc()
            conn.rollback()
            return False


def get_user_preferred_mode(user_id):
    """获取用户的模式偏好"""
    with get_db_connection() as (conn, c):
        if c is None:
            return None
        sql_raw = "SELECT preferred_mode FROM users WHERE id = ?"
        # 确保SQL适配正确（强制适配）
        sql = _safe_adapt_sql(sql_raw, conn)
        execute_result = c.execute(sql, (user_id,))
        result = _safe_fetchone(c, execute_result)

        if not result:
            return None  # 用户不存在

        if isinstance(result, (list, tuple)):
            return result[0]
        if isinstance(result, dict):
            return result.get("preferred_mode")
        if hasattr(result, "keys"):
            row_dict = dict(cast(Mapping[str, Any], result))
            return row_dict.get("preferred_mode")
        return cast(Optional[str], result)


def update_user_preferred_mode(user_id, mode):
    """更新用户的模式偏好"""
    with get_db_connection() as (conn, c):
        sql = _safe_adapt_sql("UPDATE users SET preferred_mode = ? WHERE id = ?", conn)
        c.execute(sql, (mode, user_id))
        conn.commit()


def migrate_user_preferences():
    """迁移现有用户的模式偏好"""
    with get_db_connection() as (conn, c):
        try:
            # 检查preferred_mode列是否存在
            columns = _get_table_columns(c, "users")

            if "preferred_mode" not in columns:
                # 添加preferred_mode列
                c.execute(
                    ("ALTER TABLE users ADD COLUMN preferred_mode TEXT DEFAULT 'fast'")
                )
                conn.commit()
                print("已为users表添加preferred_mode列")

            # 检查是否还有用户没有设置偏好模式
            c.execute("SELECT COUNT(*) FROM users WHERE preferred_mode IS NULL")
            null_count = c.fetchone()[0]

            if null_count > 0:
                # 为所有现有用户设置默认偏好为极速模式
                c.execute(
                    "UPDATE users SET preferred_mode = 'fast' "
                    "WHERE preferred_mode IS NULL"
                )
                conn.commit()
                print(f"已为 {null_count} 个用户设置默认模式偏好")
            # 如果没有需要设置的用户，则不显示任何信息

        except (Exception,) as e:
            print(f"迁移用户偏好失败: {e}")
            conn.rollback()


# 管理员后台相关函数


def authenticate_admin(username, password):
    """验证管理员登录"""
    with get_db_connection() as (conn, c):
        sql = _safe_adapt_sql(
            "SELECT id, username, password, role, email "
            "FROM users "
            "WHERE username = ? AND role = 'admin'",
            conn,
        )
        c.execute(sql, (username,))
        result = c.fetchone()

        if result:
            admin_id, username, password_hash, role, email = result
            import bcrypt

            if bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8")):
                # 更新最后登录时间
                if _is_postgresql_connection(conn):
                    update_sql = _safe_adapt_sql(
                        "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?",
                        conn,
                    )
                else:
                    update_sql = _safe_adapt_sql(
                        "UPDATE users SET last_login = datetime('now') WHERE id = ?",
                        conn,
                    )
                c.execute(update_sql, (admin_id,))
                conn.commit()
                return {
                    "id": admin_id,
                    "username": username,
                    "role": role,
                    "email": email,
                }
        return None


@st.cache_data(ttl=60)  # 缓存1分钟，用户列表变化不频繁
def get_all_users(
    page=1,
    per_page=20,
    search=None,
    user_type_filter=None,
    status_filter=None,
):
    """获取所有用户列表（分页）"""
    with get_db_connection() as (conn, c):
        # 构建查询条件
        where_conditions = []
        params = []

        if search:
            where_conditions.append("(username LIKE ? OR email LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])

        if user_type_filter and user_type_filter != "all":
            where_conditions.append("user_type = ?")
            params.append(user_type_filter)

        if status_filter:
            current_ts = int(time.time())
            if status_filter == "expired":
                where_conditions.append(
                    "(subscription_expires IS NOT NULL AND subscription_expires < ?)"
                )
                params.append(current_ts)
            elif status_filter == "expiring_soon":
                where_conditions.append(
                    "(subscription_expires IS NOT NULL "
                    "AND subscription_expires BETWEEN ? AND ?)"
                )
                params.extend([current_ts, current_ts + 7 * 24 * 3600])
            elif status_filter == "active":
                where_conditions.append(
                    "(subscription_expires IS NULL OR subscription_expires >= ?)"
                )
                params.append(current_ts)

        # 导入SQL安全工具
        try:
            from .sql_security import build_where_clause
        except ImportError:
            from sql_security import build_where_clause

        # 使用安全的WHERE子句构建工具
        where_clause, safe_params = build_where_clause(where_conditions, params)

        # 获取总数
        count_query = f"SELECT COUNT(*) FROM users WHERE {where_clause}"
        count_query = _safe_adapt_sql(count_query, conn)
        c.execute(count_query, safe_params)
        total_count = c.fetchone()[0]

        # 获取分页数据
        offset = (page - 1) * per_page
        # 检查logistics_templates_limit列是否存在
        cols = _get_table_columns(c, "users")
        has_logistics_limit = "logistics_templates_limit" in cols

        if has_logistics_limit:
            query = f"""
            SELECT id, username, email, role, user_type,
                   subscription_start, subscription_expires,
                   remaining_calculations, logistics_templates_limit,
                   is_auto_renew, created_at, last_login, is_frozen
            FROM users
            WHERE {where_clause}
            ORDER BY created_at DESC, id DESC
            LIMIT ? OFFSET ?
            """
        else:
            query = f"""
            SELECT id, username, email, role, user_type,
                   subscription_start, subscription_expires,
                   remaining_calculations, -1,
                   is_auto_renew, created_at, last_login, is_frozen
            FROM users
            WHERE {where_clause}
            ORDER BY created_at DESC, id DESC
            LIMIT ? OFFSET ?
            """
        query = _safe_adapt_sql(query, conn)
        c.execute(query, safe_params + [per_page, offset])
        users = c.fetchall()

        # 获取每个用户的物流模板数量
        user_logistics_counts = {}
        for user in users:
            user_id = user[0]
            sql = _safe_adapt_sql(
                "SELECT COUNT(*) FROM logistics WHERE user_id = ?", conn
            )
            c.execute(sql, (user_id,))
            logistics_count = c.fetchone()[0]
            user_logistics_counts[user_id] = logistics_count

        # 格式化用户数据
        formatted_users = []
        for user in users:
            (
                user_id,
                username,
                email,
                role,
                user_type,
                subscription_start,
                subscription_expires_raw,
                remaining_calculations,
                logistics_templates_limit,
                is_auto_renew,
                created_at,
                last_login,
                is_frozen,
            ) = user

            # 计算剩余天数
            remaining_days = None
            subscription_end_iso = None
            expiry_dt = _subscription_expires_to_datetime(subscription_expires_raw)
            if expiry_dt is not None:
                subscription_end_iso = expiry_dt.isoformat()
                today = date.today()
                remaining_days = (expiry_dt.date() - today).days

            formatted_users.append(
                {
                    "id": user_id,
                    "username": username,
                    "email": email,
                    "role": role,
                    "user_type": user_type,
                    "subscription_start": subscription_start,
                    "subscription_end": subscription_end_iso,
                    "remaining_days": remaining_days,
                    "remaining_calculations": remaining_calculations,
                    "logistics_templates_limit": logistics_templates_limit,
                    "current_logistics_count": user_logistics_counts.get(user_id, 0),
                    "is_auto_renew": is_auto_renew,
                    "created_at": created_at,
                    "last_login": last_login,
                    "is_frozen": is_frozen,
                }
            )

        return {
            "users": formatted_users,
            "total_count": total_count,
            "total_pages": (total_count + per_page - 1) // per_page,
            "current_page": page,
        }


def get_user_detail(user_id):
    """获取用户详细信息"""
    with get_db_connection() as (conn, c):
        sql = _safe_adapt_sql(
            "SELECT id, username, email, role, user_type, "
            "subscription_start, subscription_expires, "
            "remaining_calculations, logistics_templates_limit, "
            "is_auto_renew, created_at, last_login, "
            "is_frozen FROM users WHERE id = ?",
            conn,
        )
        c.execute(sql, (user_id,))
        user = c.fetchone()

        if not user:
            return None

        (
            user_id,
            username,
            email,
            role,
            user_type,
            subscription_start,
            subscription_expires_raw,
            remaining_calculations,
            logistics_templates_limit,
            is_auto_renew,
            created_at,
            last_login,
            is_frozen,
        ) = user

        # 获取物流模板数量
        sql = _safe_adapt_sql("SELECT COUNT(*) FROM logistics WHERE user_id = ?", conn)
        c.execute(sql, (user_id,))
        logistics_count = c.fetchone()[0]

        # 获取产品数量
        sql = _safe_adapt_sql("SELECT COUNT(*) FROM products WHERE user_id = ?", conn)
        c.execute(sql, (user_id,))
        products_count = c.fetchone()[0]

        # 计算剩余天数
        remaining_days = None
        subscription_end_iso = None
        expiry_dt = _subscription_expires_to_datetime(subscription_expires_raw)
        if expiry_dt is not None:
            subscription_end_iso = expiry_dt.isoformat()
            today = date.today()
            remaining_days = (expiry_dt.date() - today).days

        return {
            "id": user_id,
            "username": username,
            "email": email,
            "role": role,
            "user_type": user_type,
            "subscription_start": subscription_start,
            "subscription_end": subscription_end_iso,
            "remaining_days": remaining_days,
            "remaining_calculations": remaining_calculations,
            "logistics_templates_limit": logistics_templates_limit,
            "current_logistics_count": logistics_count,
            "products_count": products_count,
            "is_auto_renew": is_auto_renew,
            "created_at": created_at,
            "last_login": last_login,
            "is_frozen": is_frozen,
        }


def update_user_subscription_admin(user_id, updates, admin_id):
    """管理员更新用户订阅信息"""
    with get_db_connection() as (conn, c):
        # 构建更新字段
        set_clauses = []
        values = []

        for field, value in updates.items():
            if field == "subscription_end":
                serialized = _serialize_subscription_expires(value)
                set_clauses.append("subscription_expires = ?")
                values.append(serialized)
                continue

            if field in [
                "user_type",
                "subscription_start",
                "remaining_calculations",
                "logistics_templates_limit",
                "is_auto_renew",
                "is_frozen",
            ]:
                set_clauses.append(f"{field} = ?")
                values.append(value)

        if not set_clauses:
            return False

        values.append(user_id)

        # 执行更新
        placeholder = get_placeholder()
        query = f"UPDATE users SET {', '.join(set_clauses)} WHERE id = {placeholder}"
        query = adapt_sql(query)
        c.execute(query, values)

        if c.rowcount > 0:
            # 记录审计日志（保留兼容性）
            details_pairs = [f"{k}={v}" for k, v in updates.items()]
            action_details = "管理员更新用户订阅: " + ", ".join(details_pairs)
            sql = _safe_adapt_sql(
                """
                INSERT INTO audit_logs (admin_id, user_id, action, details)
                VALUES (?, ?, ?, ?)
                """,
                conn,
            )
            c.execute(
                sql,
                (admin_id, user_id, "update_subscription", action_details),
            )

            conn.commit()

            # 记录新的操作日志
            try:
                log_admin_action(
                    admin_id=admin_id,
                    action_type="更新订阅",
                    action_detail=action_details,
                    target_user_id=user_id,
                    target_type="subscription",
                )
            except Exception as e:
                print(f"记录管理员操作日志失败: {e}")

            return True

        return False


def freeze_user(user_id, admin_id):
    """冻结用户"""
    with get_db_connection() as (conn, c):
        # 检测数据库类型，PostgreSQL使用TRUE，SQLite使用1
        try:
            import psycopg2

            is_pg = isinstance(conn, psycopg2.extensions.connection)
        except (ImportError, AttributeError):
            is_pg = False

        if is_pg:
            sql = _safe_adapt_sql(
                "UPDATE users SET is_frozen = TRUE WHERE id = ?", conn
            )
        else:
            sql = _safe_adapt_sql("UPDATE users SET is_frozen = 1 WHERE id = ?", conn)
        c.execute(sql, (user_id,))

        if c.rowcount > 0:
            # 记录审计日志（保留兼容性）
            sql = _safe_adapt_sql(
                """
            INSERT INTO audit_logs (admin_id, user_id, action, details)
            VALUES (?, ?, ?, ?)
            """,
                conn,
            )
            c.execute(sql, (admin_id, user_id, "freeze_user", "管理员冻结用户"))

            conn.commit()

            # 记录新的操作日志
            try:
                log_admin_action(
                    admin_id=admin_id,
                    action_type="冻结用户",
                    action_detail=f"管理员冻结了用户ID: {user_id}",
                    target_user_id=user_id,
                    target_type="user",
                )
            except Exception as e:
                print(f"记录管理员操作日志失败: {e}")

            return True

        return False


def unfreeze_user(user_id, admin_id):
    """解冻用户"""
    with get_db_connection() as (conn, c):
        # 检测数据库类型，PostgreSQL使用FALSE，SQLite使用0
        try:
            import psycopg2

            is_pg = isinstance(conn, psycopg2.extensions.connection)
        except (ImportError, AttributeError):
            is_pg = False

        if is_pg:
            sql = _safe_adapt_sql(
                "UPDATE users SET is_frozen = FALSE WHERE id = ?", conn
            )
        else:
            sql = _safe_adapt_sql("UPDATE users SET is_frozen = 0 WHERE id = ?", conn)
        c.execute(sql, (user_id,))

        if c.rowcount > 0:
            # 记录审计日志（注意：原代码有bug，参数数量不对）
            sql = _safe_adapt_sql(
                """
            INSERT INTO audit_logs (admin_id, user_id, action, details)
            VALUES (?, ?, ?, ?)
            """,
                conn,
            )
            c.execute(sql, (admin_id, user_id, "unfreeze_user", "管理员解冻用户"))

            conn.commit()

            # 记录新的操作日志
            try:
                log_admin_action(
                    admin_id=admin_id,
                    action_type="解冻用户",
                    action_detail=(f"管理员解冻了用户ID: {user_id}"),
                    target_user_id=user_id,
                    target_type="user",
                )
            except Exception as e:
                print(f"记录管理员操作日志失败: {e}")

            return True

        return False


def delete_user_admin(user_id, admin_id):
    """管理员删除用户"""
    with get_db_connection() as (conn, c):
        # 保护管理员账号：禁止删除 admin 及其数据
        user_role_sql = _safe_adapt_sql(
            "SELECT role, username FROM users WHERE id = ?", conn
        )
        user_role_row = _safe_execute_fetchone(c, user_role_sql, (user_id,))
        if user_role_row and user_role_row[0] == "admin":
            print("删除失败: 不允许删除管理员账号及其数据")
            return False

        # 获取用户信息用于日志
        user_sql = _safe_adapt_sql("SELECT username FROM users WHERE id = ?", conn)
        user = _safe_execute_fetchone(c, user_sql, (user_id,))
        username = user[0] if user else f"ID:{user_id}"

        # 先删除用户相关的数据
        sql = _safe_adapt_sql("DELETE FROM logistics WHERE user_id = ?", conn)
        c.execute(sql, (user_id,))
        sql = _safe_adapt_sql("DELETE FROM products WHERE user_id = ?", conn)
        c.execute(sql, (user_id,))

        # 删除用户
        sql = _safe_adapt_sql("DELETE FROM users WHERE id = ?", conn)
        c.execute(sql, (user_id,))

        if c.rowcount > 0:
            # 记录审计日志（保留兼容性）
            # 注意：用户已删除，audit_logs.user_id 有 NOT NULL 约束且存在外键
            # 因此无法在 audit_logs 中记录已删除用户，跳过旧表记录
            # sql = _safe_adapt_sql("""
            # INSERT INTO audit_logs (admin_id, user_id, action, details)
            # VALUES (?, ?, ?, ?)
            # """, conn)
            # c.execute(
            #     sql,
            #     (admin_id, None, 'delete_user', f'管理员删除用户 (ID: {user_id})')
            # )

            conn.commit()

            # 记录新的操作日志
            try:
                log_admin_action(
                    admin_id=admin_id,
                    action_type="删除用户",
                    action_detail=(f"管理员删除了用户: {username} (ID: {user_id})"),
                    target_user_id=None,  # 用户已删除，设为None
                    target_type="user",
                )
            except Exception as e:
                print(f"记录管理员操作日志失败: {e}")

            return True

        return False


def batch_update_users(user_ids, updates, admin_id):
    """批量更新用户"""
    with get_db_connection() as (conn, c):
        success_count = 0

        for user_id in user_ids:
            # 构建更新字段
            set_clauses = []
            values = []

            for field, value in updates.items():
                if field == "subscription_end":
                    serialized = _serialize_subscription_expires(value)
                    set_clauses.append("subscription_expires = ?")
                    values.append(serialized)
                    continue

                if field in [
                    "user_type",
                    "subscription_start",
                    "remaining_calculations",
                    "logistics_templates_limit",
                    "is_auto_renew",
                    "is_frozen",
                ]:
                    set_clauses.append(f"{field} = ?")
                    values.append(value)

            if set_clauses:
                values.append(user_id)
                placeholder = get_placeholder()
                query = (
                    f"UPDATE users SET {', '.join(set_clauses)} "
                    f"WHERE id = {placeholder}"
                )
                query = adapt_sql(query)
                c.execute(query, values)

                if c.rowcount > 0:
                    success_count += 1
                    # 记录审计日志
                    details_pairs = [f"{k}={v}" for k, v in updates.items()]
                    action_details = "批量更新: " + ", ".join(details_pairs)
                    sql_raw = """
                    INSERT INTO audit_logs (admin_id, user_id, action, details)
                    VALUES (?, ?, ?, ?)
                    """
                    sql = _safe_adapt_sql(sql_raw, conn)
                    c.execute(sql, (admin_id, user_id, "batch_update", action_details))

        conn.commit()
        return success_count


def get_audit_logs(
    page=1,
    per_page=50,
    admin_id=None,
    user_id=None,
    action=None,
):
    """获取审计日志"""
    with get_db_connection() as (_, c):
        # 构建查询条件
        where_conditions = []
        params = []

        if admin_id:
            where_conditions.append("audit_logs.admin_id = ?")
            params.append(admin_id)

        if user_id:
            where_conditions.append("audit_logs.user_id = ?")
            params.append(user_id)

        if action:
            where_conditions.append("audit_logs.action = ?")
            params.append(action)

        # 导入SQL安全工具
        try:
            from .sql_security import build_where_clause
        except ImportError:
            from sql_security import build_where_clause

        # 使用安全的WHERE子句构建工具
        where_clause, safe_params = build_where_clause(where_conditions, params)

        # 获取总数
        count_query = f"SELECT COUNT(*) FROM audit_logs WHERE {where_clause}"
        c.execute(count_query, safe_params)
        total_count = c.fetchone()[0]

        # 获取分页数据
        offset = (page - 1) * per_page
        query = (
            "SELECT audit_logs.id, audit_logs.admin_id, audit_logs.user_id, "
            "audit_logs.action, audit_logs.details, audit_logs.timestamp, "
            "a.username as admin_username, "
            "u.username as user_username "
            "FROM audit_logs "
            "LEFT JOIN users a ON audit_logs.admin_id = a.id "
            "AND a.role = 'admin' "
            "LEFT JOIN users u ON audit_logs.user_id = u.id "
            f"WHERE {where_clause} "
            "ORDER BY audit_logs.timestamp DESC "
            "LIMIT ? OFFSET ?"
        )
        c.execute(query, safe_params + [per_page, offset])
        logs = c.fetchall()

        formatted_logs = []
        for log in logs:
            (
                log_id,
                admin_id,
                user_id,
                action,
                details,
                timestamp,
                admin_username,
                user_username,
            ) = log
            formatted_logs.append(
                {
                    "id": log_id,
                    "admin_id": admin_id,
                    "user_id": user_id,
                    "action": action,
                    "details": details,
                    "timestamp": timestamp,
                    "admin_username": admin_username,
                    "user_username": user_username,
                }
            )

        return {
            "logs": formatted_logs,
            "total_count": total_count,
            "total_pages": (total_count + per_page - 1) // per_page,
            "current_page": page,
        }


def reset_user_password(user_id, admin_id):
    """重置用户密码"""
    import secrets
    import string

    # 生成随机密码
    alphabet = string.ascii_letters + string.digits
    new_password = "".join(secrets.choice(alphabet) for _ in range(12))

    # 加密密码
    import bcrypt

    password_hash = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt())

    with get_db_connection() as (conn, c):
        c.execute(
            "UPDATE users SET password = ? WHERE id = ?",
            (password_hash.decode("utf-8"), user_id),
        )

        if c.rowcount > 0:
            # 记录审计日志（保留兼容性）
            details_text = f"管理员重置密码: {new_password}"
            c.execute(
                """
                INSERT INTO audit_logs (admin_id, user_id, action, details)
                VALUES (?, ?, ?, ?)
                """,
                (
                    admin_id,
                    user_id,
                    "reset_password",
                    details_text,
                ),
            )

            conn.commit()

            # 记录新的操作日志（不记录密码）
            try:
                log_admin_action(
                    admin_id=admin_id,
                    action_type="重置密码",
                    action_detail=f"管理员重置了用户ID: {user_id} 的密码",
                    target_user_id=user_id,
                    target_type="user",
                )
            except Exception as e:
                print(f"记录管理员操作日志失败: {e}")

            return new_password

        return None


# ============= 统计与运营看板相关函数 =============


def log_user_login(
    user_id: int, ip_address: Optional[str] = None, user_agent: Optional[str] = None
) -> bool:
    """记录用户登录日志"""
    with get_db_connection() as (conn, c):
        # 确保外键约束已启用（仅SQLite）
        if not _is_postgresql_connection(conn):
            try:
                # 只有SQLite连接才需要PRAGMA
                conn.execute("PRAGMA foreign_keys=ON")
            except (sqlite3.Error, AttributeError):
                pass
        try:
            # 简单的设备类型判断
            device_type = "unknown"
            if user_agent:
                user_agent_lower = user_agent.lower()
                if "mobile" in user_agent_lower or "android" in user_agent_lower:
                    device_type = "mobile"
                elif "tablet" in user_agent_lower or "ipad" in user_agent_lower:
                    device_type = "tablet"
                else:
                    device_type = "desktop"

            login_time = int(time.time())
            sql_raw = """
                INSERT INTO user_login_log
                (user_id, login_time, ip_address, user_agent, device_type)
                VALUES (?, ?, ?, ?, ?)
            """
            sql = _safe_adapt_sql(sql_raw, conn)
            c.execute(sql, (user_id, login_time, ip_address, user_agent, device_type))

            # 更新用户的最后登录时间
            sql_raw = """
                UPDATE users
                SET last_login = CURRENT_TIMESTAMP
                WHERE id = ?
            """
            sql = _safe_adapt_sql(sql_raw, conn)
            c.execute(sql, (user_id,))

            conn.commit()
            return True
        except Exception as e:
            # 如果主键冲突处理失败，尝试捕获并忽略
            error_str = str(e).lower()
            if "duplicate" in error_str or "unique" in error_str:
                # 主键冲突，忽略错误但继续更新最后登录时间
                try:
                    sql_raw = """
                        UPDATE users
                        SET last_login = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """
                    sql = _safe_adapt_sql(sql_raw, conn)
                    c.execute(sql, (user_id,))
                    conn.commit()
                except DB_EXCEPTIONS:
                    pass
                return True
            print(f"记录用户登录日志失败: {e}")
            return False


def log_user_behavior(
    user_id: int,
    behavior_type: str,
    behavior_detail: Optional[str] = None,
    calculation_mode: Optional[str] = None,
) -> bool:
    """
    记录用户行为日志

    Args:
        user_id: 用户ID
        behavior_type: 行为类型 (calculation/mode_switch/export等)
        behavior_detail: 行为详细信息（JSON格式）
        calculation_mode: 计算模式（fast/complete）

    Returns:
        bool: 记录是否成功
    """
    with get_db_connection() as (conn, c):
        try:
            sql_raw = """
                INSERT INTO user_behavior_log
                (user_id, behavior_type, behavior_detail, calculation_mode)
                VALUES (?, ?, ?, ?)
            """
            sql = _safe_adapt_sql(sql_raw, conn)
            c.execute(sql, (user_id, behavior_type, behavior_detail, calculation_mode))
            conn.commit()
            return True
        except Exception as e:
            print(f"记录用户行为日志失败: {e}")
            return False


def log_admin_action(
    admin_id: int,
    action_type: str,
    action_detail: str,
    target_user_id: Optional[int] = None,
    target_type: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> bool:
    """记录管理员操作日志"""
    with get_db_connection() as (conn, c):
        try:
            sql_raw = """
                INSERT INTO admin_action_log
                (admin_id, action_type, action_detail, target_user_id,
                 target_type, ip_address)
                VALUES (?, ?, ?, ?, ?, ?)
            """
            sql = _safe_adapt_sql(sql_raw, conn)
            c.execute(
                sql,
                (
                    admin_id,
                    action_type,
                    action_detail,
                    target_user_id,
                    target_type,
                    ip_address,
                ),
            )
            conn.commit()
            return True
        except Exception as e:
            print(f"记录管理员操作日志失败: {e}")
            return False


def create_alert(
    alert_type: str,
    alert_level: str,
    description: str,
    threshold_value: Optional[float] = None,
    actual_value: Optional[float] = None,
) -> bool:
    """创建异常告警记录"""
    with get_db_connection() as (conn, c):
        try:
            c.execute(
                """
                INSERT INTO alert_records
                (alert_type, alert_level, description,
                 threshold_value, actual_value)
                VALUES (?, ?, ?, ?, ?)
            """,
                (alert_type, alert_level, description, threshold_value, actual_value),
            )
            conn.commit()
            return True
        except Exception as e:
            print(f"创建告警记录失败: {e}")
            return False


def get_statistics_cache(cache_key: str) -> Optional[Dict[str, Any]]:
    """获取统计缓存数据"""
    with get_db_connection() as (conn, c):
        try:
            current_time = int(time.time())
            sql_raw = """
                SELECT cache_data FROM statistics_cache
                WHERE cache_key = ? AND expires_at > ?
            """
            sql = _safe_adapt_sql(sql_raw, conn)
            result = _safe_execute_fetchone(c, sql, (cache_key, current_time), conn)

            if result:
                return json.loads(result[0])
            return None
        except Exception as e:
            print(f"获取缓存失败: {e}")
            return None


def _convert_decimal_to_float(obj):
    """递归转换Decimal为float，用于JSON序列化"""
    from decimal import Decimal

    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: _convert_decimal_to_float(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_decimal_to_float(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(_convert_decimal_to_float(item) for item in obj)
    return obj


def set_statistics_cache(
    cache_key: str, cache_data: Dict[str, Any], ttl: int = 300
) -> bool:
    """设置统计缓存数据

    Args:
        cache_key: 缓存键
        cache_data: 缓存数据
        ttl: 过期时间（秒），默认5分钟
    """
    with get_db_connection() as (conn, c):
        try:
            current_time = int(time.time())
            expires_at = current_time + ttl
            # 转换Decimal为float以支持JSON序列化
            cache_data_serializable = _convert_decimal_to_float(cache_data)
            cache_json = json.dumps(cache_data_serializable, ensure_ascii=False)

            if _is_postgresql_connection(conn):
                sql = """
                    INSERT INTO statistics_cache
                    (cache_key, cache_data, expires_at, updated_at)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (cache_key) DO UPDATE SET
                    cache_data = EXCLUDED.cache_data,
                    expires_at = EXCLUDED.expires_at,
                    updated_at = EXCLUDED.updated_at
                """
            else:
                sql = """
                    INSERT OR REPLACE INTO statistics_cache
                    (cache_key, cache_data, expires_at, updated_at)
                    VALUES (?, ?, ?, ?)
                """
            c.execute(sql, (cache_key, cache_json, expires_at, current_time))
            conn.commit()
            return True
        except Exception as e:
            print(f"设置缓存失败: {e}")
            return False


def clear_expired_cache() -> int:
    """清理过期的缓存数据"""
    with get_db_connection() as (conn, c):
        try:
            current_time = int(time.time())
            c.execute(
                """
                DELETE FROM statistics_cache WHERE expires_at < ?
            """,
                (current_time,),
            )
            conn.commit()
            return c.rowcount
        except Exception as e:
            print(f"清理缓存失败: {e}")
            return 0


def clear_all_statistics_cache() -> int:
    """清除所有统计缓存数据"""
    with get_db_connection() as (conn, c):
        try:
            sql_raw = "DELETE FROM statistics_cache"
            sql = _safe_adapt_sql(sql_raw, conn)
            c.execute(sql)
            conn.commit()
            return c.rowcount
        except Exception as e:
            print(f"清除所有缓存失败: {e}")
            return 0


# @st.cache_resource(ttl=300)  # 缓存5分钟 - 临时禁用
def get_dashboard_stats() -> Dict[str, Any]:
    """获取总览看板数据"""
    # 先尝试从缓存获取
    cache_key = "dashboard_stats"
    cached = get_statistics_cache(cache_key)
    if cached:
        return cached

    with get_db_connection() as (conn, c):
        try:
            current_time = int(time.time())
            today_start = current_time - (current_time % 86400)
            yesterday_start = today_start - 86400
            month_start = current_time - (current_time % (30 * 86400))

            # 今日活跃用户数（今日登录的用户）
            sql_raw = """
                SELECT COUNT(DISTINCT user_id)
                FROM user_login_log
                WHERE login_time >= ?
            """
            sql = _safe_adapt_sql(sql_raw, conn)
            c.execute(sql, (today_start,))
            active_users_today = c.fetchone()[0]

            # 今日新增用户数
            if _is_postgresql_connection(conn):
                safe_user_expr = _build_safe_timestamp_expr("created_at")
                sql = f"""
                    WITH normalized_users AS (
                        SELECT
                            {safe_user_expr} AS created_ts,
                            role
                        FROM users
                    )
                    SELECT COUNT(*) FROM normalized_users
                    WHERE role != 'admin'
                    AND created_ts >= to_timestamp(%s)
                """
                c.execute(sql, (today_start,))
            else:
                today_start_str = datetime.fromtimestamp(today_start).strftime(
                    "%Y-%m-%d 00:00:00"
                )
                sql = """
                    SELECT COUNT(*) FROM users
                    WHERE created_at >= ?
                """
                c.execute(sql, (today_start_str,))
            new_users_today = c.fetchone()[0]

            # 累计注册用户数
            sql_raw = """
                SELECT COUNT(*) FROM users WHERE role != 'admin'
            """
            sql = _safe_adapt_sql(sql_raw, conn)
            c.execute(sql)
            total_users = c.fetchone()[0]

            # 总收入（所有成功支付的订单）
            sql_raw = """
                SELECT COALESCE(SUM(amount), 0) / 100.0
                FROM payment_orders
                WHERE status = 'SUCCESS'
            """
            sql = _safe_adapt_sql(sql_raw, conn)
            c.execute(sql)
            total_revenue = c.fetchone()[0]

            # 今日收入
            orders_cte = ""
            if _is_postgresql_connection(conn):
                safe_order_expr = _build_safe_timestamp_expr("created_at")
                orders_cte = f"""
                    WITH normalized_orders AS (
                        SELECT
                            amount,
                            status,
                            {safe_order_expr} AS created_ts
                        FROM payment_orders
                    )
                """
                sql = (
                    orders_cte
                    + """
                    SELECT COALESCE(SUM(amount), 0) / 100.0
                    FROM normalized_orders
                    WHERE status = 'SUCCESS'
                    AND created_ts >= to_timestamp(%s)
                """
                )
                c.execute(sql, (today_start,))
            else:
                sql_raw = """
                    SELECT COALESCE(SUM(amount), 0) / 100.0
                    FROM payment_orders
                    WHERE status = 'SUCCESS' AND created_at >= ?
                """
                sql = _safe_adapt_sql(sql_raw, conn)
                c.execute(sql, (today_start,))
            revenue_today = c.fetchone()[0]

            # 昨日收入
            if _is_postgresql_connection(conn):
                sql = (
                    orders_cte
                    + """
                    SELECT COALESCE(SUM(amount), 0) / 100.0
                    FROM normalized_orders
                    WHERE status = 'SUCCESS'
                    AND created_ts >= to_timestamp(%s)
                    AND created_ts < to_timestamp(%s)
                """
                )
                c.execute(sql, (yesterday_start, today_start))
            else:
                sql_raw = """
                    SELECT COALESCE(SUM(amount), 0) / 100.0
                    FROM payment_orders
                    WHERE status = 'SUCCESS'
                    AND created_at >= ? AND created_at < ?
                """
                sql = _safe_adapt_sql(sql_raw, conn)
                c.execute(sql, (yesterday_start, today_start))
            revenue_yesterday = c.fetchone()[0]

            # 本月收入
            if _is_postgresql_connection(conn):
                sql = (
                    orders_cte
                    + """
                    SELECT COALESCE(SUM(amount), 0) / 100.0
                    FROM normalized_orders
                    WHERE status = 'SUCCESS'
                    AND created_ts >= to_timestamp(%s)
                """
                )
                c.execute(sql, (month_start,))
            else:
                sql_raw = """
                    SELECT COALESCE(SUM(amount), 0) / 100.0
                    FROM payment_orders
                    WHERE status = 'SUCCESS' AND created_at >= ?
                """
                sql = _safe_adapt_sql(sql_raw, conn)
                c.execute(sql, (month_start,))
            revenue_month = c.fetchone()[0]

            # 实时在线用户数（过去5分钟有登录记录的用户）
            sql_raw = """
                SELECT COUNT(DISTINCT user_id)
                FROM user_login_log
                WHERE login_time >= ?
            """
            sql = _safe_adapt_sql(sql_raw, conn)
            c.execute(sql, (current_time - 300,))
            online_users = c.fetchone()[0]

            result = {
                "active_users_today": active_users_today,
                "new_users_today": new_users_today,
                "total_users": total_users,
                "total_revenue": round(total_revenue, 2),
                "revenue_today": round(revenue_today, 2),
                "revenue_yesterday": round(revenue_yesterday, 2),
                "revenue_month": round(revenue_month, 2),
                "online_users": online_users,
                "timestamp": current_time,
            }

            # 缓存5分钟
            set_statistics_cache(cache_key, result, 300)
            return result
        except Exception as e:
            print(f"获取总览数据失败: {e}")
            return {}


# ============================================================================
# 套餐管理CRUD函数
# ============================================================================


@st.cache_data(ttl=300)  # 缓存5分钟，套餐数据变化不频繁
def get_plans(active_only=False, include_free=True):
    """
    获取所有套餐列表

    Args:
        active_only: 是否只获取上架的套餐
        include_free: 是否包含免费版

    Returns:
        list: 套餐列表，每个套餐为dict
    """
    with get_db_connection() as (_, c):
        try:
            query = "SELECT * FROM plans WHERE 1=1"
            params = []

            if active_only:
                query += " AND is_active = 1"

            if not include_free:
                query += " AND plan_code != 'free'"

            query += " ORDER BY sort_order"

            c.execute(query, params)
            columns = [col[0] for col in c.description]
            rows = c.fetchall()

            plans = []
            for row in rows:
                plan = dict(zip(columns, row))
                plans.append(plan)

            return plans
        except Exception as e:
            print(f"获取套餐列表失败: {e}")
            return []


# @st.cache_data(ttl=300)  # 缓存5分钟 - 暂时禁用以修复测试
def get_plan_by_code(plan_code: str):
    """
    根据套餐代码获取套餐详情

    Args:
        plan_code: 套餐代码

    Returns:
        dict: 套餐详情，不存在返回None
    """
    with get_db_connection() as (conn, c):
        try:
            sql_raw = "SELECT * FROM plans WHERE plan_code = ?"
            sql = _safe_adapt_sql(sql_raw, conn)
            c.execute(sql, (plan_code,))
            row = c.fetchone()

            if row:
                columns = [col[0] for col in c.description]
                return dict(zip(columns, row))
            return None
        except Exception as e:
            print(f"获取套餐详情失败: {e}")
            return None


def get_plan_by_id(plan_id: int):
    """
    根据ID获取套餐详情

    Args:
        plan_id: 套餐ID

    Returns:
        dict: 套餐详情，不存在返回None
    """
    with get_db_connection() as (conn, c):
        try:
            sql_raw = "SELECT * FROM plans WHERE id = ?"
            sql = _safe_adapt_sql(sql_raw, conn)
            c.execute(sql, (plan_id,))
            row = c.fetchone()

            if row:
                columns = [col[0] for col in c.description]
                return dict(zip(columns, row))
            return None
        except Exception as e:
            print(f"获取套餐详情失败: {e}")
            return None


def create_plan(
    plan_code: str,
    plan_name: str,
    display_price_month: float,
    display_price_year: float,
    actual_price_month: float,
    actual_price_year: float,
    test_price_month: float = 0.0,
    test_price_year: float = 0.0,
    calc_limit: int = -1,
    logistics_limit: int = 1,
    description: str = "",
    features: str = "",
    is_active: int = 1,
    sort_order: int = 0,
):
    """
    创建新套餐

    Returns:
        bool: 成功返回True，失败返回False
    """
    with get_db_connection() as (conn, c):
        try:
            # 检查代码是否已存在
            existing = c.execute(
                "SELECT id FROM plans WHERE plan_code = ?", (plan_code,)
            ).fetchone()

            if existing:
                print(f"套餐代码 {plan_code} 已存在")
                return False

            c.execute(
                """
                INSERT INTO plans (
                    plan_code, plan_name,
                    display_price_month, display_price_year,
                    actual_price_month, actual_price_year,
                    test_price_month, test_price_year,
                    calc_limit, logistics_limit,
                    description, features,
                    is_active, sort_order
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    plan_code,
                    plan_name,
                    display_price_month,
                    display_price_year,
                    actual_price_month,
                    actual_price_year,
                    test_price_month,
                    test_price_year,
                    calc_limit,
                    logistics_limit,
                    description,
                    features,
                    is_active,
                    sort_order,
                ),
            )

            conn.commit()
            return True
        except Exception as e:
            print(f"创建套餐失败: {e}")
            return False


def update_plan(plan_id: int, **kwargs):
    """
    更新套餐信息

    Args:
        plan_id: 套餐ID
        **kwargs: 要更新的字段

    Returns:
        bool: 成功返回True，失败返回False
    """
    with get_db_connection() as (conn, c):
        try:
            # 允许更新的字段
            allowed_fields = [
                "plan_name",
                "display_price_month",
                "display_price_year",
                "actual_price_month",
                "actual_price_year",
                "test_price_month",
                "test_price_year",
                "calc_limit",
                "logistics_limit",
                "description",
                "features",
                "is_active",
                "sort_order",
            ]

            # 过滤并构建SET子句
            updates = []
            values = []
            for field, value in kwargs.items():
                if field in allowed_fields:
                    updates.append(f"{field} = ?")
                    values.append(value)

            if not updates:
                return False

            # 添加updated_at（需要适配数据库类型）
            # 检测实际连接类型
            if _is_postgresql_connection(conn):
                updates.append("updated_at = extract(epoch from now())")
            else:
                updates.append("updated_at = strftime('%s', 'now')")

            placeholder = get_placeholder()
            query = f"UPDATE plans SET {', '.join(updates)} WHERE id = {placeholder}"
            query = adapt_sql(query)
            values.append(plan_id)
            c.execute(query, values)
            conn.commit()

            return c.rowcount > 0
        except Exception as e:
            print(f"更新套餐失败: {e}")
            return False


def delete_plan(plan_id: int):
    """
    删除套餐

    Args:
        plan_id: 套餐ID

    Returns:
        bool: 成功返回True，失败返回False
    """
    with get_db_connection() as (conn, c):
        try:
            # 检查是否为免费版（不允许删除）
            plan = c.execute(
                "SELECT plan_code FROM plans WHERE id = ?", (plan_id,)
            ).fetchone()

            if plan and plan[0] == "free":
                print("不允许删除免费版套餐")
                return False

            sql_raw = "DELETE FROM plans WHERE id = ?"
            sql = _safe_adapt_sql(sql_raw, conn)
            c.execute(sql, (plan_id,))
            conn.commit()

            return c.rowcount > 0
        except Exception as e:
            print(f"删除套餐失败: {e}")
            return False


def toggle_plan_active(plan_id: int):
    """
    切换套餐上下架状态

    Args:
        plan_id: 套餐ID

    Returns:
        bool: 成功返回True，失败返回False
    """
    with get_db_connection() as (conn, c):
        try:
            c.execute(
                """
                UPDATE plans
                SET is_active = 1 - is_active,
                    updated_at = strftime('%s', 'now')
                WHERE id = ?
            """,
                (plan_id,),
            )
            conn.commit()

            return c.rowcount > 0
        except Exception as e:
            print(f"切换套餐状态失败: {e}")
            return False


def get_plan_price(plan_code: str, duration: str, use_test_price: bool = False):
    """
    获取套餐价格（根据用户角色）

    Args:
        plan_code: 套餐代码
        duration: 时长 ('month' 或 'year')
        use_test_price: 是否使用测试价格（管理员使用测试价）

    Returns:
        float: 价格（元），如果套餐不存在返回0
    """
    plan = get_plan_by_code(plan_code)
    if not plan:
        return 0

    if use_test_price:
        # 管理员使用测试价
        if duration == "year":
            return plan["test_price_year"]
        return plan["test_price_month"]
    else:
        # 普通用户使用实际价
        if duration == "year":
            return plan["actual_price_year"]
        return plan["actual_price_month"]
