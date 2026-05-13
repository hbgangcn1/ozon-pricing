from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from fastapi.testclient import TestClient

from api.main import app


client = TestClient(app, raise_server_exceptions=False)


class _Config:
    def __init__(self, public_key_path):
        self.public_key_path = public_key_path


def _write_cert(path: Path, days_left: int) -> None:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "wechat")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc) - timedelta(days=1))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=days_left))
        .sign(key, hashes.SHA256())
    )
    path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))


def _patch_health(monkeypatch, cert_path):
    monkeypatch.setattr("api.main.engine", _Engine())
    monkeypatch.setattr("api.main._check_redis_ok", lambda: True)
    monkeypatch.setattr("wechat_pay_v3_api.wechat_config", _Config(cert_path))


class _GoodResult:
    def __await__(self):
        async def _result():
            return None

        return _result().__await__()


class _GoodConn:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    def execute(self, _stmt):
        return _GoodResult()


class _Engine:
    def connect(self):
        return _GoodConn()


def test_health_wechat_cert_days_sufficient(monkeypatch, tmp_path):
    cert_path = tmp_path / "wechat.pem"
    _write_cert(cert_path, 45)
    _patch_health(monkeypatch, str(cert_path))

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["wechat_cert_ok"] is True
    assert body["wechat_cert_days_left"] >= 43


def test_health_wechat_cert_near_expiry_degrades(monkeypatch, tmp_path):
    cert_path = tmp_path / "wechat.pem"
    _write_cert(cert_path, 12)
    _patch_health(monkeypatch, str(cert_path))

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["wechat_cert_ok"] is True
    assert 0 <= body["wechat_cert_days_left"] < 30


def test_health_wechat_cert_unreadable_is_non_blocking(monkeypatch, tmp_path):
    _patch_health(monkeypatch, str(tmp_path / "missing.pem"))

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["wechat_cert_ok"] is True
    assert body["wechat_cert_days_left"] is None
