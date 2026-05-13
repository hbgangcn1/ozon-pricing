import subprocess
import sys


def _write_env(path, **overrides):
    values = {
        "DATABASE_URL": "postgresql://user:pass@localhost:5432/logistics",
        "SECRET_KEY": "x" * 32,
        "WECHAT_PAY_MCH_ID": "mch",
        "WECHAT_PAY_API_V3_KEY": "v3" * 16,
        "WECHAT_PAY_CERT_SERIAL": "serial",
        "WECHAT_PAY_PRIVATE_KEY_PATH": "cert/apiclient_key.pem",
        "ALLOWED_ORIGINS": "https://www.cbprice.cn",
    }
    values.update(overrides)
    path.write_text("\n".join(f"{key}={value}" for key, value in values.items()))


def _run(path):
    return subprocess.run(
        [sys.executable, "scripts/validate_env.py", str(path)],
        text=True,
        capture_output=True,
        check=False,
    )


def test_validate_env_happy_path(tmp_path):
    env = tmp_path / ".env"
    _write_env(env)

    result = _run(env)

    assert result.returncode == 0
    assert "OK" in result.stdout


def test_validate_env_missing_key(tmp_path):
    env = tmp_path / ".env"
    _write_env(env, WECHAT_PAY_MCH_ID="")

    result = _run(env)

    assert result.returncode == 1
    assert "WECHAT_PAY_MCH_ID" in result.stdout


def test_validate_env_secret_key_too_short(tmp_path):
    env = tmp_path / ".env"
    _write_env(env, SECRET_KEY="short")

    result = _run(env)

    assert result.returncode == 1
    assert "SECRET_KEY" in result.stdout


def test_validate_env_database_url_protocol(tmp_path):
    env = tmp_path / ".env"
    _write_env(env, DATABASE_URL="sqlite:///local.db")

    result = _run(env)

    assert result.returncode == 1
    assert "DATABASE_URL must start with postgresql://" in result.stdout
