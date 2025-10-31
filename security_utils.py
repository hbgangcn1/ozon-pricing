# -*- coding: utf-8 -*-
"""
安全工具模块
提供SQL注入防护、XSS防护等安全功能
"""

import re
from html import escape as html_escape
from typing import List, Set


def validate_column_names(
    column_names: List[str],
    allowed_columns: Set[str],
) -> List[str]:
    """
    验证列名是否合法，防止SQL注入

    Args:
        column_names: 待验证的列名列表
        allowed_columns: 允许的列名集合

    Returns:
        验证通过的列名列表

    Raises:
        ValueError: 如果列名不在允许列表中
    """
    invalid_columns = [
        col for col in column_names if col not in allowed_columns
    ]
    if invalid_columns:
        raise ValueError(
            f"非法的列名: {invalid_columns}. "
            f"只允许使用以下列名: {sorted(allowed_columns)}"
        )
    return column_names


def sanitize_column_name(column_name: str) -> str:
    """
    清理列名，只允许字母、数字和下划线

    Args:
        column_name: 原始列名

    Returns:
        清理后的列名

    Raises:
        ValueError: 如果列名包含非法字符
    """
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', column_name):
        raise ValueError(
            f"列名 '{column_name}' 包含非法字符. "
            f"只允许字母、数字和下划线，且不能以数字开头"
        )
    return column_name


def escape_html_content(content: str) -> str:
    """
    转义HTML内容，防止XSS攻击

    Args:
        content: 待转义的字符串

    Returns:
        转义后的安全字符串
    """
    if content is None:
        return ''
    return html_escape(str(content))


def safe_format_html(template: str, **kwargs) -> str:
    """
    安全地格式化HTML模板，自动转义用户输入

    Args:
        template: HTML模板字符串
        **kwargs: 模板变量

    Returns:
        格式化后的HTML字符串，所有变量值已转义
    """
    escaped_kwargs = {
        key: escape_html_content(value)
        for key, value in kwargs.items()
    }
    return template.format(**escaped_kwargs)


def build_safe_in_clause(placeholders: str, param_count: int) -> tuple:
    """
    安全地构建IN子句

    Args:
        placeholders: 占位符字符串，如 "?,?,?"
        param_count: 参数数量

    Returns:
        (SQL片段, 验证状态)

    Note:
        此函数主要用于验证占位符格式是否正确
    """
    expected_placeholders = ','.join(['?' for _ in range(param_count)])
    if placeholders != expected_placeholders:
        raise ValueError(
            f"占位符数量不匹配: 期望 {param_count} 个，实际为 {placeholders}"
        )
    return placeholders, True
