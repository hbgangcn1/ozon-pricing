import time
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.main import app


client = TestClient(app, raise_server_exceptions=False)


def test_health_ok():
    with patch("api.main._check_redis_ok", return_value=True), \
         patch("api.main._check_wechat_cert_expiry_days", return_value=42):
        r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["db_ok"] is True
    assert body["redis_ok"] is True
    assert body["wechat_pay_cert_expires_in_days"] == 42
    assert body["uptime_s"] >= 0
    assert "version" in body


def test_health_db_down():
    class _BadConn:
        async def __aenter__(self): raise RuntimeError("db unavailable")
        async def __aexit__(self, *a): return False

    with patch("api.main.engine") as eng, \
         patch("api.main._check_redis_ok", return_value=True), \
         patch("api.main._check_wechat_cert_expiry_days", return_value=None):
        eng.connect.return_value = _BadConn()
        r = client.get("/health")
    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "down"
    assert body["db_ok"] is False


def test_health_redis_down():
    with patch("api.main._check_redis_ok", return_value=False), \
         patch("api.main._check_wechat_cert_expiry_days", return_value=None):
        r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "degraded"
    assert body["db_ok"] is True
    assert body["redis_ok"] is False


def test_health_response_under_500ms():
    with patch("api.main._check_redis_ok", return_value=True), \
         patch("api.main._check_wechat_cert_expiry_days", return_value=10):
        t0 = time.perf_counter()
        r = client.get("/health")
        elapsed_ms = (time.perf_counter() - t0) * 1000
    assert r.status_code == 200
    assert elapsed_ms < 500, f"/health took {elapsed_ms:.1f}ms (>500ms budget)"


def test_health_no_auth_required():
    r = client.get("/health")
    assert r.status_code in (200, 503)


def test_health_wechat_cert_none_when_unavailable():
    with patch("api.main._check_redis_ok", return_value=True), \
         patch("api.main._check_wechat_cert_expiry_days", return_value=None):
        r = client.get("/health")
    assert r.json()["wechat_pay_cert_expires_in_days"] is None


@pytest.mark.parametrize("git_sha,expected", [("abc1234", "abc1234"), (None, "unknown")])
def test_health_version_field(monkeypatch, git_sha, expected):
    if git_sha is None:
        monkeypatch.delenv("GIT_SHA", raising=False)
    else:
        monkeypatch.setenv("GIT_SHA", git_sha)
    with patch("api.main._check_redis_ok", return_value=True), \
         patch("api.main._check_wechat_cert_expiry_days", return_value=None):
        r = client.get("/health")
    assert r.json()["version"] == expected
