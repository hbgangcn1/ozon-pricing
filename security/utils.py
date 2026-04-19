# -*- coding: utf-8 -*-
"""
安全模块工具
提供安全相关的工具函数
"""

from typing import Any


def get_client_headers() -> dict:
    """获取当前请求头（placeholder 实现）"""
    return {}


def mask_sensitive_value(value: str, visible_chars: int = 4) -> str:
    """掩码敏感信息，仅显示前 N 个字符"""
    if not value or len(value) <= visible_chars:
        return "*" * len(value) if value else ""
    return value[:visible_chars] + "*" * (len(value) - visible_chars)
