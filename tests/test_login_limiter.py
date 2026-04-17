import time
import pytest
from fastapi import HTTPException
from api.middleware.login_limiter import LoginRateLimiter


def make_limiter(**kwargs):
    return LoginRateLimiter(**kwargs)


def test_check_allows_attempts_below_limit():
    limiter = make_limiter(max_attempts=5, window_seconds=60, lockout_seconds=900)
    for _ in range(4):
        limiter.record_attempt("1.2.3.4")
    limiter.check("1.2.3.4")


def test_check_raises_429_when_limit_reached():
    limiter = make_limiter(max_attempts=3, window_seconds=60, lockout_seconds=900)
    for _ in range(3):
        limiter.record_attempt("1.2.3.4")
    with pytest.raises(HTTPException) as exc_info:
        limiter.check("1.2.3.4")
    assert exc_info.value.status_code == 429


def test_check_raises_429_during_lockout():
    limiter = make_limiter(max_attempts=3, window_seconds=60, lockout_seconds=900)
    for _ in range(3):
        limiter.record_attempt("1.2.3.4")
    try:
        limiter.check("1.2.3.4")
    except HTTPException:
        pass
    with pytest.raises(HTTPException) as exc_info:
        limiter.check("1.2.3.4")
    assert exc_info.value.status_code == 429


def test_lockout_expires_and_allows_new_attempts():
    limiter = make_limiter(max_attempts=2, window_seconds=1, lockout_seconds=1)
    for _ in range(2):
        limiter.record_attempt("5.6.7.8")
    try:
        limiter.check("5.6.7.8")
    except HTTPException:
        pass
    limiter.lockouts["5.6.7.8"] = time.time() - 1
    limiter.attempts["5.6.7.8"] = [time.time() - 2, time.time() - 2]
    limiter.check("5.6.7.8")


def test_expired_window_resets_attempts():
    limiter = make_limiter(max_attempts=3, window_seconds=1, lockout_seconds=900)
    old_time = time.time() - 2
    limiter.attempts["9.9.9.9"] = [old_time, old_time, old_time]
    limiter.check("9.9.9.9")


def test_record_attempt_tracks_timestamps():
    limiter = make_limiter()
    before = time.time()
    limiter.record_attempt("10.0.0.1")
    after = time.time()
    assert len(limiter.attempts["10.0.0.1"]) == 1
    assert before <= limiter.attempts["10.0.0.1"][0] <= after


def test_clear_removes_attempts_and_lockout():
    limiter = make_limiter(max_attempts=3, window_seconds=60, lockout_seconds=900)
    limiter.record_attempt("2.2.2.2")
    limiter.lockouts["2.2.2.2"] = time.time() + 900
    limiter.clear("2.2.2.2")
    assert "2.2.2.2" not in limiter.attempts
    assert "2.2.2.2" not in limiter.lockouts


def test_clear_on_unknown_ip_is_safe():
    limiter = make_limiter()
    limiter.clear("0.0.0.0")


def test_evict_old_entries_when_max_tracked_ips_exceeded():
    from api.middleware.login_limiter import MAX_TRACKED_IPS

    limiter = make_limiter()
    base_time = time.time()
    for i in range(MAX_TRACKED_IPS):
        ip = f"10.{i // 65536 % 256}.{i // 256 % 256}.{i % 256}"
        limiter.attempts[ip] = [base_time + i]
    new_ip = "192.168.1.1"
    limiter.attempts[new_ip] = [base_time + MAX_TRACKED_IPS]
    limiter._evict_old_entries()
    assert len(limiter.attempts) <= MAX_TRACKED_IPS


def test_check_detail_contains_remaining_seconds():
    limiter = make_limiter(max_attempts=1, window_seconds=60, lockout_seconds=900)
    limiter.record_attempt("3.3.3.3")
    try:
        limiter.check("3.3.3.3")
    except HTTPException:
        pass
    with pytest.raises(HTTPException) as exc_info:
        limiter.check("3.3.3.3")
    assert "秒" in exc_info.value.detail


def test_different_ips_are_tracked_independently():
    limiter = make_limiter(max_attempts=2, window_seconds=60, lockout_seconds=900)
    limiter.record_attempt("1.1.1.1")
    limiter.record_attempt("1.1.1.1")
    with pytest.raises(HTTPException):
        limiter.check("1.1.1.1")
    limiter.check("2.2.2.2")
