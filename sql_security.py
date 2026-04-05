# -*- coding: utf-8 -*-
"""
SQL安全工具模块
提供安全的SQL构建和验证功能，防止SQL注入攻击
"""

import re
from typing import List, Any, Tuple, Set, Optional


class SQLSecurityError(Exception):
    """SQL安全相关异常"""
    pass


# 预定义的安全表名白名单
SAFE_TABLE_NAMES = {
    'users', 'products', 'logistics', 'payment_orders',
    'active_sessions', 'login_attempts', 'user_lockouts',
    'subscription_upgrade_history', 'user_login_log',
    'user_behavior_log', 'admin_action_log', 'alert_records',
    'statistics_cache', 'alert_config', 'plans', 'system_config',
    'password_recovery_log', 'audit_logs'
}

# 预定义的安全字段名模式（只允许字母、数字、下划线）
SAFE_FIELD_PATTERN = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')

# 危险的SQL关键字
DANGEROUS_KEYWORDS = {
    'DROP', 'DELETE', 'TRUNCATE', 'UPDATE', 'INSERT',
    'ALTER', 'CREATE', 'EXEC', 'EXECUTE', 'UNION',
    'SCRIPT', 'SELECT', 'SCRIPT'
}


def validate_table_name(table_name: str) -> str:
    """
    验证表名是否安全

    Args:
        table_name: 表名

    Returns:
        验证后的表名

    Raises:
        SQLSecurityError: 如果表名不安全
    """
    if not isinstance(table_name, str):
        raise SQLSecurityError(f"表名必须是字符串类型: {type(table_name)}")

    table_name = table_name.strip()
    if not table_name:
        raise SQLSecurityError("表名不能为空")

    if table_name not in SAFE_TABLE_NAMES:
        raise SQLSecurityError(
            f"非法的表名: {table_name}. "
            f"只允许使用以下表名: {sorted(SAFE_TABLE_NAMES)}"
        )

    return table_name


def validate_field_name(
    field_name: str, allowed_fields: Optional[Set[str]] = None
) -> str:
    """
    验证字段名是否安全

    Args:
        field_name: 字段名
        allowed_fields: 允许的字段名白名单（如果提供，则只允许白名单中的字段）

    Returns:
        验证后的字段名

    Raises:
        SQLSecurityError: 如果字段名不安全
    """
    if not isinstance(field_name, str):
        raise SQLSecurityError(f"字段名必须是字符串类型: {type(field_name)}")

    field_name = field_name.strip()
    if not field_name:
        raise SQLSecurityError("字段名不能为空")

    # 检查字段名格式（只允许字母、数字、下划线，且必须以字母或下划线开头）
    if not SAFE_FIELD_PATTERN.match(field_name):
        raise SQLSecurityError(
            f"非法的字段名格式: {field_name}. "
            f"字段名只能包含字母、数字、下划线，且必须以字母或下划线开头"
        )

    # 检查是否包含危险关键字
    field_upper = field_name.upper()
    for keyword in DANGEROUS_KEYWORDS:
        if keyword in field_upper:
            raise SQLSecurityError(
                f"字段名包含危险的SQL关键字: {keyword} (在 {field_name} 中)"
            )

    # 如果提供了白名单，检查字段是否在白名单中
    if allowed_fields is not None:
        if field_name not in allowed_fields:
            raise SQLSecurityError(
                f"非法的字段名: {field_name}. "
                f"只允许使用以下字段: {sorted(allowed_fields)}"
            )

    return field_name


def validate_field_names(
    field_names: List[str],
    allowed_fields: Optional[Set[str]] = None
) -> List[str]:
    """
    批量验证字段名

    Args:
        field_names: 字段名列表
        allowed_fields: 允许的字段名白名单

    Returns:
        验证后的字段名列表

    Raises:
        SQLSecurityError: 如果任何字段名不安全
    """
    validated = []
    for field_name in field_names:
        validated.append(validate_field_name(field_name, allowed_fields))
    return validated


def validate_id_list(id_list: List[Any], max_size: int = 1000) -> List[int]:
    """
    验证ID列表是否安全（必须是整数列表）

    Args:
        id_list: ID列表
        max_size: 最大列表大小（防止过大的IN子句）

    Returns:
        验证后的整数ID列表

    Raises:
        SQLSecurityError: 如果ID列表不安全
    """
    if not isinstance(id_list, list):
        raise SQLSecurityError(f"ID列表必须是列表类型: {type(id_list)}")

    if len(id_list) > max_size:
        raise SQLSecurityError(
            f"ID列表大小({len(id_list)})超过最大限制({max_size})"
        )

    validated_ids = []
    for item in id_list:
        try:
            # 转换为整数
            item_id = int(item)
            if item_id <= 0:
                raise SQLSecurityError(f"ID必须是正整数: {item}")
            validated_ids.append(item_id)
        except (ValueError, TypeError) as e:
            raise SQLSecurityError(f"无效的ID: {item} ({e})")

    return validated_ids


def build_update_set_clause(
    updates: dict, allowed_fields: Set[str]
) -> Tuple[str, List[Any]]:
    """
    安全地构建UPDATE语句的SET子句

    Args:
        updates: 要更新的字段和值的字典
        allowed_fields: 允许的字段名白名单

    Returns:
        (SET子句SQL片段, 参数值列表)

    Raises:
        SQLSecurityError: 如果字段名不安全
    """
    if not updates:
        raise SQLSecurityError("更新字典不能为空")

    set_clauses = []
    values = []

    for field_name, value in updates.items():
        # 验证字段名
        validated_field = validate_field_name(field_name, allowed_fields)
        set_clauses.append(f"{validated_field} = ?")
        values.append(value)

    set_clause = ", ".join(set_clauses)
    return set_clause, values


def build_in_clause(
    id_list: List[Any], max_size: int = 1000
) -> Tuple[str, List[int]]:
    """
    安全地构建IN子句

    Args:
        id_list: ID列表
        max_size: 最大列表大小

    Returns:
        (IN子句SQL片段, 参数值列表)

    Raises:
        SQLSecurityError: 如果ID列表不安全
    """
    if not id_list:
        return "IN (NULL)", []

    validated_ids = validate_id_list(id_list, max_size)
    placeholders = ",".join(["?" for _ in validated_ids])
    in_clause = f"IN ({placeholders})"
    return in_clause, validated_ids


def build_where_clause(
    conditions: List[str], params: List[Any]
) -> Tuple[str, List[Any]]:
    """
    安全地构建WHERE子句

    Args:
        conditions: WHERE条件列表（每个条件应该是已参数化的，如 "field = ?"）
        params: 参数值列表

    Returns:
        (WHERE子句SQL片段, 参数值列表)

    Raises:
        SQLSecurityError: 如果条件不安全
    """
    if not conditions:
        return "1=1", []

    # 验证每个条件都包含占位符（防止直接拼接值）
    for condition in conditions:
        if not isinstance(condition, str):
            raise SQLSecurityError(f"WHERE条件必须是字符串: {type(condition)}")
        if "?" not in condition and "%s" not in condition:
            raise SQLSecurityError(
                f"WHERE条件必须使用参数化查询: {condition}"
            )

        # 检查是否包含危险关键字（在非参数化上下文中）
        condition_upper = condition.upper()
        for keyword in DANGEROUS_KEYWORDS:
            # 允许在参数化查询中使用这些关键字，但不允许直接拼接值
            if keyword in condition_upper and "?" not in condition:
                raise SQLSecurityError(
                    f"WHERE条件包含危险的SQL关键字: {keyword}"
                )

    where_clause = " AND ".join(conditions)
    return where_clause, params


def sanitize_sql_fragment(fragment: str) -> str:
    """
    清理SQL片段，移除潜在的危险字符

    Args:
        fragment: SQL片段

    Returns:
        清理后的SQL片段

    Note:
        此函数用于清理已知安全的SQL片段（如表名、字段名）
        不应直接用于用户输入
    """
    if not isinstance(fragment, str):
        raise SQLSecurityError(f"SQL片段必须是字符串: {type(fragment)}")

    # 移除注释
    fragment = re.sub(r'--.*', '', fragment)
    fragment = re.sub(r'/\*.*?\*/', '', fragment, flags=re.DOTALL)

    # 移除分号（防止多语句攻击）
    fragment = fragment.replace(';', '')

    return fragment.strip()


def validate_sql_statement(
    sql: str, allowed_operations: Optional[Set[str]] = None
) -> str:
    """
    验证SQL语句是否安全

    Args:
        sql: SQL语句
        allowed_operations: 允许的操作类型（SELECT, INSERT, UPDATE, DELETE）

    Returns:
        验证后的SQL语句

    Raises:
        SQLSecurityError: 如果SQL语句不安全
    """
    if not isinstance(sql, str):
        raise SQLSecurityError(f"SQL语句必须是字符串: {type(sql)}")

    sql_upper = sql.upper().strip()

    # 检查是否包含多个语句（防止SQL注入）
    if (sql.count(';') > 1 or
            (sql.count(';') == 1 and not sql.strip().endswith(';'))):
        raise SQLSecurityError("SQL语句不能包含多个语句")

    # 如果指定了允许的操作，检查操作类型
    if allowed_operations:
        sql_start = sql_upper.split()[0] if sql_upper.split() else ""
        if sql_start not in allowed_operations:
            raise SQLSecurityError(
                f"不允许的SQL操作: {sql_start}. "
                f"只允许: {sorted(allowed_operations)}"
            )

    return sql
