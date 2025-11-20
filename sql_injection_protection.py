# -*- coding: utf-8 -*-
"""
SQL注入防护模块（高优先级安全改进）
提供运行时SQL注入检测和防护机制
"""

import re
import logging
from typing import Optional, Tuple, Any, Callable
from functools import wraps

# 配置日志
logger = logging.getLogger(__name__)

# 危险的SQL模式（用于检测潜在的SQL注入）
DANGEROUS_SQL_PATTERNS = [
    # 字符串拼接模式
    (r'execute\s*\(\s*f["\']', 'f-string SQL执行'),
    (r'execute\s*\(\s*["\'].*%[sd]', '字符串格式化SQL'),
    (r'execute\s*\(\s*["\'].*\{.*\}', '字符串插值SQL'),
    (r'execute\s*\(\s*["\']\+', '字符串拼接SQL'),
    (r'\.format\s*\([^)]*\)\s*\)', 'format方法SQL'),
    # SQL注入常见模式
    (r'--', 'SQL注释'),
    (r'/\*.*?\*/', 'SQL多行注释'),
    (r';\s*(DROP|DELETE|TRUNCATE|ALTER|CREATE)', '多语句攻击'),
    (r'UNION\s+SELECT', 'UNION注入'),
    (r'OR\s+1\s*=\s*1', '永真条件'),
    (r'AND\s+1\s*=\s*1', '永真条件'),
]

# 安全的SQL模式（参数化查询）
SAFE_SQL_PATTERNS = [
    (r'execute\s*\(\s*["\'][^"\']*\?[^"\']*["\']\s*,',
     '参数化查询（?占位符）'),
    (r'execute\s*\(\s*["\'][^"\']*%s[^"\']*["\']\s*,',
     '参数化查询（%s占位符）'),
]


class SQLInjectionError(Exception):
    """SQL注入检测异常"""
    pass


def detect_sql_injection(
    sql: str, params: Optional[Tuple[Any, ...]] = None
) -> Tuple[bool, Optional[str]]:
    """
    检测SQL语句是否存在注入风险

    Args:
        sql: SQL语句
        params: 参数元组（可选）

    Returns:
        (is_safe, warning_message): 是否安全，警告消息
    """
    if not isinstance(sql, str):
        return False, "SQL语句必须是字符串类型"

    # 检查是否使用参数化查询
    has_placeholders = '?' in sql or '%s' in sql
    has_params = params is not None and len(params) > 0

    # 如果SQL包含占位符但没有参数，可能是潜在问题
    if has_placeholders and not has_params:
        return False, "SQL包含占位符但未提供参数"

    # 检查危险的SQL模式
    for pattern, description in DANGEROUS_SQL_PATTERNS:
        if re.search(pattern, sql, re.IGNORECASE | re.DOTALL):
            # 允许在注释中的模式（如果SQL本身是注释）
            if pattern.startswith('--') and sql.strip().startswith('--'):
                continue
            return False, f"检测到潜在的SQL注入风险: {description}"

    # 检查是否包含多个语句（防止多语句攻击）
    # 允许在字符串字面量中的分号
    semicolon_count = sql.count(';')
    if semicolon_count > 1:
        # 检查是否在字符串字面量中
        in_string = False
        quote_char = None
        for i, char in enumerate(sql):
            if char in ("'", '"') and (i == 0 or sql[i-1] != '\\'):
                if not in_string:
                    in_string = True
                    quote_char = char
                elif char == quote_char:
                    in_string = False
                    quote_char = None
            elif char == ';' and not in_string:
                # 在字符串外的分号
                if i < len(sql) - 1:
                    # 分号后还有内容，可能是多语句攻击
                    remaining = sql[i+1:].strip()
                    if remaining and not remaining.startswith('--'):
                        return False, "检测到多语句SQL（可能的安全风险）"

    # 检查参数中是否包含危险的SQL关键字
    if params:
        for param in params:
            if isinstance(param, str):
                param_upper = param.upper()
                dangerous_keywords = [
                    'DROP', 'DELETE', 'TRUNCATE', 'ALTER',
                    'CREATE', 'EXEC', 'EXECUTE', 'UNION'
                ]
                for keyword in dangerous_keywords:
                    if keyword in param_upper:
                        # 检查是否是完整的单词（避免误报）
                        if re.search(rf'\b{keyword}\b', param_upper):
                            return False, (
                                f"参数中包含危险的SQL关键字: {keyword}"
                            )

    return True, None


def validate_sql_params(
    sql: str, params: Optional[Tuple[Any, ...]] = None
) -> None:
    """
    验证SQL语句和参数的安全性

    Args:
        sql: SQL语句
        params: 参数元组（可选）

    Raises:
        SQLInjectionError: 如果检测到SQL注入风险
    """
    is_safe, warning = detect_sql_injection(sql, params)
    if not is_safe:
        error_msg = f"SQL注入检测失败: {warning}"
        logger.error(error_msg)
        logger.error(f"SQL语句: {sql[:200]}...")  # 只记录前200个字符
        if params:
            logger.error(f"参数数量: {len(params)}")
        raise SQLInjectionError(error_msg)


def sql_injection_protection(func: Callable) -> Callable:
    """
    SQL注入防护装饰器
    在函数执行前检测SQL语句是否存在注入风险

    Usage:
        @sql_injection_protection
        def execute_query(sql, params):
            cursor.execute(sql, params)
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # 检查函数参数中是否包含SQL语句
        sql = None
        params = None

        # 尝试从位置参数获取SQL
        if args and isinstance(args[0], str):
            sql = args[0]
            if len(args) > 1:
                params = (
                    args[1] if isinstance(args[1], (tuple, list)) else None
                )

        # 尝试从关键字参数获取SQL
        if sql is None:
            sql = (
                kwargs.get('sql') or
                kwargs.get('query') or
                kwargs.get('statement')
            )
            params = kwargs.get('params') or kwargs.get('parameters')

        # 如果找到SQL语句，进行检测
        if sql:
            try:
                # 转换params为Tuple类型（如果它是list）
                if params is not None and isinstance(params, list):
                    params = tuple(params)
                validate_sql_params(sql, params)
            except SQLInjectionError:
                # 在生产环境中，可以选择记录日志并继续，或者抛出异常
                # 这里选择抛出异常，确保安全
                raise

        # 执行原函数
        return func(*args, **kwargs)

    return wrapper


def safe_execute_sql(
    cursor, sql: str, params: Optional[Tuple[Any, ...]] = None,
    conn=None, strict_mode: bool = True
) -> Any:
    """
    安全执行SQL语句（带注入检测）

    Args:
        cursor: 数据库游标
        sql: SQL语句
        params: 参数元组（可选）
        conn: 数据库连接（可选，用于SQL适配）
        strict_mode: 严格模式（True时检测到风险会抛出异常，
                     False时只记录警告）

    Returns:
        执行结果

    Raises:
        SQLInjectionError: 如果检测到SQL注入风险且strict_mode=True
    """
    # 检测SQL注入风险
    is_safe, warning = detect_sql_injection(sql, params)

    if not is_safe:
        if strict_mode:
            raise SQLInjectionError(f"SQL注入检测失败: {warning}")
        else:
            logger.warning(f"SQL注入警告: {warning}")
            logger.warning(f"SQL语句: {sql[:200]}...")

    # 适配SQL（如果需要）
    if conn is not None:
        try:
            from db_adapter import adapt_sql
        except ImportError:
            adapt_sql = None

        if adapt_sql is not None:
            sql = adapt_sql(sql)

    # 执行SQL
    if params:
        return cursor.execute(sql, params)
    else:
        return cursor.execute(sql)


def audit_sql_execution(
    sql: str, params: Optional[Tuple[Any, ...]] = None,
    file_path: Optional[str] = None,
    line_number: Optional[int] = None
) -> None:
    """
    审计SQL执行（记录日志）

    Args:
        sql: SQL语句
        params: 参数元组（可选）
        file_path: 文件路径（可选）
        line_number: 行号（可选）
    """
    is_safe, warning = detect_sql_injection(sql, params)

    if not is_safe:
        log_msg = f"SQL注入风险检测: {warning}"
        if file_path:
            log_msg += f" (文件: {file_path}"
            if line_number:
                log_msg += f", 行号: {line_number}"
            log_msg += ")"
        logger.warning(log_msg)
        logger.warning(f"SQL语句: {sql[:200]}...")

    # 记录所有SQL执行（用于审计）
    if logger.isEnabledFor(logging.DEBUG):
        log_msg = f"SQL执行: {sql[:100]}..."
        if params:
            log_msg += f" (参数数量: {len(params)})"
        if file_path:
            log_msg += f" [{file_path}:{line_number or '?'}]"
        logger.debug(log_msg)
