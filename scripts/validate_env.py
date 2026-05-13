"""Validate production .env before deployment.

Stdlib-only script. Reads .env from current directory or an explicit path.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REQUIRED_KEYS = {
    "DATABASE_URL": ("DATABASE_URL",),
    "SECRET_KEY": ("SECRET_KEY", "JWT_SECRET_KEY"),
    "WECHAT_PAY_MCH_ID": ("WECHAT_PAY_MCH_ID", "WECHAT_MCH_ID"),
    "WECHAT_PAY_API_V3_KEY": ("WECHAT_PAY_API_V3_KEY", "WECHAT_API_V3_KEY"),
    "WECHAT_PAY_CERT_SERIAL": ("WECHAT_PAY_CERT_SERIAL", "WECHAT_CERT_SERIAL_NO"),
    "WECHAT_PAY_PRIVATE_KEY_PATH": ("WECHAT_PAY_PRIVATE_KEY_PATH", "WECHAT_PRIVATE_KEY_PATH"),
    "ALLOWED_ORIGINS": ("ALLOWED_ORIGINS",),
}


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def parse_env(path: Path) -> tuple[dict[str, str], list[str]]:
    values: dict[str, str] = {}
    errors: list[str] = []
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("export "):
            stripped = stripped[7:].lstrip()
        if "=" not in stripped:
            errors.append(f"{line_no}:1: invalid line, expected KEY=value")
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        if not key:
            errors.append(f"{line_no}:1: empty key")
            continue
        values[key] = _strip_quotes(value.strip())
    return values, errors


def _first_column(lines: list[str], key: str) -> int:
    prefix = f"{key}="
    export_prefix = f"export {key}="
    for raw in lines:
        stripped = raw.strip()
        if stripped.startswith(prefix) or stripped.startswith(export_prefix):
            return raw.find("=") + 2
    return 1


def _value(values: dict[str, str], logical_key: str) -> str:
    for key in REQUIRED_KEYS[logical_key]:
        if values.get(key):
            return values[key]
    return ""


def _has_postgres_parts(values: dict[str, str]) -> bool:
    return all(
        values.get(key)
        for key in ("POSTGRES_HOST", "POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD")
    )


def validate(path: Path) -> list[str]:
    if not path.exists():
        return [f"1:1: .env file not found: {path}"]
    values, errors = parse_env(path)
    lines = path.read_text(encoding="utf-8").splitlines()
    is_production = values.get("PRODUCTION_MODE", "true").lower() == "true"
    for key in sorted(REQUIRED_KEYS):
        if key.startswith("WECHAT_PAY_") and not is_production:
            continue
        if key == "DATABASE_URL" and _has_postgres_parts(values):
            continue
        if key == "ALLOWED_ORIGINS" and not is_production:
            continue
        if not _value(values, key):
            errors.append(f"1:1: missing or empty required key {key}")
    secret = _value(values, "SECRET_KEY")
    if secret and len(secret) < 32:
        errors.append(f"{_line_no(lines, 'SECRET_KEY')}:1: SECRET_KEY must be at least 32 chars")
    db_url = _value(values, "DATABASE_URL")
    if db_url and not db_url.startswith("postgresql://"):
        col = _first_column(lines, "DATABASE_URL")
        errors.append(f"{_line_no(lines, 'DATABASE_URL')}:{col}: DATABASE_URL must start with postgresql://")
    return errors


def _line_no(lines: list[str], key: str) -> int:
    prefixes = (f"{key}=", f"export {key}=")
    for index, raw in enumerate(lines, 1):
        stripped = raw.strip()
        if stripped.startswith(prefixes):
            return index
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate deployment .env")
    parser.add_argument("env_file", nargs="?", default=".env")
    args = parser.parse_args(argv)
    errors = validate(Path(args.env_file))
    if errors:
        print("Environment validation failed:")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("Environment validation OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
