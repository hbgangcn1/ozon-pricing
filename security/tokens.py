import os
import uuid
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt


_MIN_SECRET_LENGTH = 32  # 256-bit minimum for HS256


def _get_jwt_secret() -> str:
    secret = os.environ.get("JWT_SECRET_KEY")
    if not secret:
        raise RuntimeError(
            "JWT_SECRET_KEY environment variable is required. "
            "Set it in .env for development or system environment for production."
        )
    if len(secret) < _MIN_SECRET_LENGTH:
        raise RuntimeError(
            f"JWT_SECRET_KEY is too short ({len(secret)} chars). "
            f"Minimum {_MIN_SECRET_LENGTH} characters required for HS256 security. "
            "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
        )
    return secret


_secret_key_cache: Optional[str] = None
ALGORITHM = "HS256"
ISSUER = "cbprice-api"
AUDIENCE = "cbprice-web"
ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.environ.get(
        "ACCESS_TOKEN_EXPIRE_MINUTES", os.environ.get("JWT_EXPIRE_MINUTES", "15")
    )
)
ACCESS_TOKEN_EXPIRE_SECONDS = ACCESS_TOKEN_EXPIRE_MINUTES * 60
REFRESH_TOKEN_EXPIRE_DAYS = int(
    os.environ.get("REFRESH_TOKEN_EXPIRE_DAYS", "7")
)
TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"
_REVOKED_REFRESH_JTIS: dict[str, float] = {}


def _revoked_jtis_cleanup() -> None:
    """Remove expired entries from the in-memory revoked-jti map."""
    cutoff = datetime.now(timezone.utc).timestamp() - (
        REFRESH_TOKEN_EXPIRE_DAYS * 86400 + 3600
    )
    stale = [jti for jti, ts in _REVOKED_REFRESH_JTIS.items() if ts < cutoff]
    for jti in stale:
        _REVOKED_REFRESH_JTIS.pop(jti, None)


def _get_secret_key() -> str:
    global _secret_key_cache
    if _secret_key_cache is None:
        _secret_key_cache = _get_jwt_secret()
    return _secret_key_cache


def __getattr__(name: str) -> object:
    if name == "SECRET_KEY":
        return _get_secret_key()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


class TokenError(Exception):
    """Token 相关错误的基类"""

    pass


class TokenExpiredError(TokenError):
    """Token 已过期"""

    pass


class TokenInvalidError(TokenError):
    """Token 无效（签名错误、格式错误等）"""

    pass


def create_access_token(
    user_id: int,
    username: str,
    role: str = "user",
    expires_delta: Optional[timedelta] = None,
    extra_claims: Optional[Mapping[str, object]] = None,
) -> str:
    if expires_delta is None:
        expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "type": TOKEN_TYPE_ACCESS,
        "token_type": TOKEN_TYPE_ACCESS,
        "iss": ISSUER,
        "aud": AUDIENCE,
        "iat": now,
        "exp": now + expires_delta,
    }
    if extra_claims:
        payload.update(dict(extra_claims))
    return jwt.encode(payload, _get_secret_key(), algorithm=ALGORITHM)


def create_access_token_from_payload(
    payload: dict,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """从已有 payload 提取 user_id/username/role，重新签发 token。

    用于 refresh 时避免重复查 DB 获取这些信息。
    """
    if expires_delta is None:
        expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    now = datetime.now(timezone.utc)
    new_payload = {
        "sub": payload["sub"],
        "username": payload["username"],
        "role": payload["role"],
        "type": TOKEN_TYPE_ACCESS,
        "token_type": TOKEN_TYPE_ACCESS,
        "iss": ISSUER,
        "aud": AUDIENCE,
        "iat": now,
        "exp": now + expires_delta,
    }
    if payload.get("sid"):
        new_payload["sid"] = payload["sid"]
    return jwt.encode(new_payload, _get_secret_key(), algorithm=ALGORITHM)


def create_refresh_token(
    user_id: int,
    sid: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """生成 refresh token。

    sid 必须是已写入 active_sessions 的会话 ID，refresh 时用它做服务端启停。
    """
    if expires_delta is None:
        expires_delta = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "sid": sid,
        "jti": uuid.uuid4().hex,
        "type": TOKEN_TYPE_REFRESH,
        "token_type": TOKEN_TYPE_REFRESH,
        "iss": ISSUER,
        "aud": AUDIENCE,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, _get_secret_key(), algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Raises TokenExpiredError or TokenInvalidError."""
    try:
        payload = jwt.decode(
            token,
            _get_secret_key(),
            algorithms=[ALGORITHM],
            audience=AUDIENCE,
            issuer=ISSUER,
            options={"require": ["exp", "iat", "iss", "aud"]},
        )
        # 拒绝把 refresh token 当 access token 用（防 token 类型混淆攻击）
        payload_type = payload.get("token_type") or payload.get("type")
        if payload_type == TOKEN_TYPE_REFRESH:
            raise TokenInvalidError("Refresh token 不能用作 access token")
        if payload.get("purpose") == "password_reset":
            raise TokenInvalidError("Password reset token 不能用作 access token")
        return payload
    except jwt.ExpiredSignatureError:
        raise TokenExpiredError("Token 已过期")
    except jwt.InvalidTokenError as e:
        raise TokenInvalidError(f"Token 无效: {e}")


def _decode_access_token_unsafe_for_testing(token: str) -> dict:
    """TESTING ONLY — NEVER call from production code.

    解码 access token，不验证 exp。
    Raises TokenInvalidError。
    """
    if not (
        os.environ.get("E2E_TEST") == "1"
        or os.environ.get("LOGISTICS_TESTING") == "1"
        or os.environ.get("PYTEST_CURRENT_TEST")
    ):
        raise RuntimeError("decode_token_unsafe must NOT be used outside testing")
    try:
        payload = jwt.decode(
            token,
            _get_secret_key(),
            algorithms=[ALGORITHM],
            audience=AUDIENCE,
            issuer=ISSUER,
            options={"verify_exp": False, "require": ["iat", "iss", "aud"]},
        )
        payload_type = payload.get("token_type") or payload.get("type")
        if payload_type == TOKEN_TYPE_REFRESH:
            raise TokenInvalidError("Refresh token 不能用作 access token")
        if payload.get("purpose") == "password_reset":
            raise TokenInvalidError("Password reset token 不能用作 access token")
        return payload
    except jwt.InvalidTokenError as e:
        raise TokenInvalidError(f"Token 无效: {e}")


decode_token_unsafe_for_testing = _decode_access_token_unsafe_for_testing


def decode_password_reset_token(token: str) -> dict:
    """Decode password reset token; raises TokenExpiredError or TokenInvalidError."""
    try:
        payload = jwt.decode(token, _get_secret_key(), algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise TokenExpiredError("Token 已过期")
    except jwt.InvalidTokenError as e:
        raise TokenInvalidError(f"Token 无效: {e}")

    payload_type = payload.get("token_type") or payload.get("type")
    if payload_type == TOKEN_TYPE_REFRESH:
        raise TokenInvalidError("Refresh token 不能用作 password reset token")
    if payload.get("purpose") != "password_reset":
        raise TokenInvalidError("Token 不是 password reset 类型")
    return payload


def decode_refresh_token(token: str) -> dict:
    """Raises TokenExpiredError or TokenInvalidError."""
    try:
        payload = jwt.decode(
            token,
            _get_secret_key(),
            algorithms=[ALGORITHM],
            audience=AUDIENCE,
            issuer=ISSUER,
            options={"require": ["exp", "iat", "iss", "aud"]},
        )
    except jwt.ExpiredSignatureError:
        raise TokenExpiredError("Refresh token 已过期")
    except jwt.InvalidTokenError as e:
        raise TokenInvalidError(f"Refresh token 无效: {e}")
    payload_type = payload.get("token_type") or payload.get("type")
    if payload_type != TOKEN_TYPE_REFRESH:
        raise TokenInvalidError("Token 不是 refresh 类型")
    if not payload.get("sid"):
        raise TokenInvalidError("Refresh token 缺少 sid 字段")
    if payload.get("sub") is None:
        raise TokenInvalidError("Refresh token 缺少 sub 字段")
    jti = payload.get("jti")
    if jti in _REVOKED_REFRESH_JTIS:
        raise TokenInvalidError("Refresh token 已撤销")
    return payload


def revoke_refresh_token_jti(jti: object) -> None:
    if isinstance(jti, str) and jti:
        _revoked_jtis_cleanup()
        _REVOKED_REFRESH_JTIS[jti] = datetime.now(timezone.utc).timestamp()


def get_user_id_from_token(token: str) -> int:
    """Raises TokenExpiredError or TokenInvalidError."""
    payload = decode_access_token(token)
    sub = payload.get("sub")
    if sub is None:
        raise TokenInvalidError("Token 缺少 sub 字段")
    try:
        return int(sub)
    except (ValueError, TypeError):
        raise TokenInvalidError("Token sub 字段不是有效的用户ID")
