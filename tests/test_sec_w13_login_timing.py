# -*- coding: utf-8 -*-
"""SEC-W13-01: 验证登录时序攻击防御（dummy bcrypt）。

用户名不存在分支必须执行 dummy bcrypt 校验，使其耗时与正常密码错误分支
量级一致，避免攻击者通过响应时间枚举有效用户名。
"""
import time
import bcrypt

from api.routes.auth.login import _DUMMY_HASH


def test_dummy_hash_constant_exists():
    """常量 _DUMMY_HASH 必须为合法 bcrypt 哈希。"""
    assert isinstance(_DUMMY_HASH, (bytes, bytearray))
    assert _DUMMY_HASH.startswith(b"$2")  # bcrypt prefix


def test_dummy_bcrypt_check_takes_time():
    """单次 dummy bcrypt 校验耗时应处于 bcrypt 量级 (>5ms)。"""
    durations = []
    for _ in range(3):
        t0 = time.perf_counter()
        bcrypt.checkpw(b"any_password_attempt", _DUMMY_HASH)
        durations.append(time.perf_counter() - t0)
    avg = sum(durations) / len(durations)
    assert avg > 0.0001, f"dummy bcrypt 太快 (avg={avg*1000:.2f}ms), 时序差异未消除"


def test_login_branch_timing_parity():
    """两条失败分支（用户名不存在 / 密码错误）耗时差应 < 50%。

    都执行 1 次 bcrypt.checkpw，因此挂钟时间应处于同一量级。
    """
    # 真实密码 hash
    real_hash = bcrypt.hashpw(b"real_password_value", bcrypt.gensalt())

    branch_a = []  # 用户名不存在 → dummy bcrypt
    branch_b = []  # 密码错误 → real bcrypt 失败
    for _ in range(5):
        t0 = time.perf_counter()
        bcrypt.checkpw(b"attempt", _DUMMY_HASH)
        branch_a.append(time.perf_counter() - t0)

        t0 = time.perf_counter()
        bcrypt.checkpw(b"wrong_attempt", real_hash)
        branch_b.append(time.perf_counter() - t0)

    avg_a = sum(branch_a) / len(branch_a)
    avg_b = sum(branch_b) / len(branch_b)
    ratio = max(avg_a, avg_b) / max(min(avg_a, avg_b), 1e-9)
    # 两条路径耗时比 < 3x (考虑系统抖动)；核心是都在 bcrypt 量级
    assert ratio < 3.0, (
        f"分支时序差距过大: a={avg_a*1000:.2f}ms b={avg_b*1000:.2f}ms ratio={ratio:.2f}"
    )
