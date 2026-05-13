# -*- coding: utf-8 -*-
"""SEC-W13-04: SESSION_HMAC_SECRET 缺失时的环境感知 fallback。

- 测试环境（PYTEST_CURRENT_TEST 或 sys.modules['pytest']）允许 dev 默认值
- 生产环境必须 raise ValueError
"""
import os
from unittest.mock import patch

import pytest

from session_security import SessionSecurityEnhanced


@pytest.fixture(autouse=True)
def _reset_hmac_cache():
    """每个测试前清掉 lru-style 缓存，确保重新走分支判定。"""
    SessionSecurityEnhanced._hmac_secret_cache = None
    yield
    SessionSecurityEnhanced._hmac_secret_cache = None


def test_hmac_secret_uses_env_when_set(monkeypatch):
    monkeypatch.setenv("SESSION_HMAC_SECRET", "x" * 48)
    secret = SessionSecurityEnhanced.hmac_secret()
    assert secret == "x" * 48


def test_hmac_secret_test_env_fallback(monkeypatch):
    """pytest 环境下未设置 SESSION_HMAC_SECRET 仍可工作（不崩）。"""
    monkeypatch.delenv("SESSION_HMAC_SECRET", raising=False)
    # 当前进程肯定有 PYTEST_CURRENT_TEST + sys.modules['pytest']
    secret = SessionSecurityEnhanced.hmac_secret()
    assert isinstance(secret, str) and len(secret) > 0


def test_hmac_secret_production_raises(monkeypatch):
    """无 pytest 标记 + 无 env → raise ValueError。"""
    monkeypatch.delenv("SESSION_HMAC_SECRET", raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    import sys
    with patch.dict(sys.modules, {"pytest": None}):
        # 删掉 pytest module 引用
        sys.modules.pop("pytest", None)
        try:
            with pytest.raises(ValueError, match="SESSION_HMAC_SECRET"):
                SessionSecurityEnhanced.hmac_secret()
        finally:
            # 恢复 pytest 引用以免影响后续测试
            import importlib
            sys.modules["pytest"] = importlib.import_module("pytest")


def test_hmac_secret_caches_result(monkeypatch):
    """二次调用应命中缓存。"""
    monkeypatch.setenv("SESSION_HMAC_SECRET", "cached_secret_value_xxxxxxxxxxxxx")
    s1 = SessionSecurityEnhanced.hmac_secret()
    monkeypatch.setenv("SESSION_HMAC_SECRET", "different_value_yyyyyyyyyyyyyyyyy")
    s2 = SessionSecurityEnhanced.hmac_secret()
    assert s1 == s2  # 缓存命中
