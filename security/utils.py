# -*- coding: utf-8 -*-
"""
安全模块工具
提供安全相关的工具函数
"""

import os

from fastapi import Request


def get_client_headers() -> dict:
    """获取当前请求头（placeholder 实现）"""
    return {}


def mask_sensitive_value(value: str, visible_chars: int = 4) -> str:
    """掩码敏感信息，仅显示前 N 个字符"""
    if not value or len(value) <= visible_chars:
        return "*" * len(value) if value else ""
    return value[:visible_chars] + "*" * (len(value) - visible_chars)


def _environment_name() -> str:
    return (
        os.getenv("ENVIRONMENT")
        or os.getenv("ENV")
        or "development"
    ).lower()


def auth_cookie_kwargs(request: Request) -> dict:
    """Return uniform auth-cookie security settings.

    [SEC-W12R2-04] Login, refresh, and logout must derive Secure/HttpOnly/
    SameSite in one place so production/staging never emit insecure auth
    cookies while local HTTP development remains usable.
    """
    env_name = _environment_name()
    secure = env_name in {"production", "staging"} or request.url.scheme == "https"
    return {
        "httponly": True,
        "secure": secure,
        "samesite": "lax",
        "path": "/",
    }


def auth_cookie_domain() -> str | None:
    env_name = _environment_name()
    if env_name == "production":
        return ".cbprice.cn"
    return None
