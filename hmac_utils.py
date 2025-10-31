#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
HMAC签名工具：用于回调接口的签名验证与防重放
"""

import hmac
import time
import hashlib
import os
from typing import Optional


def generate_signature(
    secret: str,
    timestamp: str,
    nonce: str,
    body: bytes,
) -> str:
    """生成 HMAC-SHA256 签名，十六进制小写。
    参与签名的串: f"{timestamp}\n{nonce}\n" + body
    """
    key = secret.encode("utf-8")
    base = (
        timestamp.encode("utf-8")
        + b"\n"
        + nonce.encode("utf-8")
        + b"\n"
        + body
    )
    return hmac.new(key, base, hashlib.sha256).hexdigest()


def verify_signature(
    secret: str,
    timestamp: str,
    nonce: str,
    body: bytes,
    signature: str,
    window_seconds: int = 300,
) -> bool:
    """验证签名与防重放。
    - window_seconds: 允许的时间窗口，默认5分钟
    """
    try:
        ts = int(timestamp)
    except (ValueError, TypeError):
        return False
    now = int(time.time())
    if abs(now - ts) > window_seconds:
        return False
    expect = generate_signature(secret, timestamp, nonce, body)
    try:
        # 常量时间比较
        return hmac.compare_digest(expect, str(signature or "").lower())
    except (TypeError, AttributeError, ValueError):
        return False


def get_callback_secret() -> Optional[str]:
    """从环境变量读取回调签名密钥。"""
    return os.getenv("CALLBACK_HMAC_SECRET")
