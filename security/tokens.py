import os
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


_SECRET_KEY: Optional[str] = None
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.environ.get(
        "ACCESS_TOKEN_EXPIRE_MINUTES", os.environ.get("JWT_EXPIRE_MINUTES", "15")
    )
)
REFRESH_TOKEN_EXPIRE_DAYS = int(
    os.environ.get("REFRESH_TOKEN_EXPIRE_DAYS", "7")
)
TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"


def _get_secret_key() -> str:
    global _SECRET_KEY
    if _SECRET_KEY is None:
        _SECRET_KEY = _get_jwt_secret()
    return _SECRET_KEY


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
) -> str:
    if expires_delta is None:
        expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "type": TOKEN_TYPE_ACCESS,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, _get_secret_key(), algorithm=ALGORITHM)


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
        "type": TOKEN_TYPE_REFRESH,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, _get_secret_key(), algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Raises TokenExpiredError or TokenInvalidError."""
    try:
        payload = jwt.decode(token, _get_secret_key(), algorithms=[ALGORITHM])
        # 拒绝把 refresh token 当 access token 用（防 token 类型混淆攻击）
        if payload.get("type") == TOKEN_TYPE_REFRESH:
            raise TokenInvalidError("Refresh token 不能用作 access token")
        return payload
    except jwt.ExpiredSignatureError:
        raise TokenExpiredError("Token 已过期")
    except jwt.InvalidTokenError as e:
        raise TokenInvalidError(f"Token 无效: {e}")


def decode_refresh_token(token: str) -> dict:
    """Raises TokenExpiredError or TokenInvalidError."""
    try:
        payload = jwt.decode(token, _get_secret_key(), algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise TokenExpiredError("Refresh token 已过期")
    except jwt.InvalidTokenError as e:
        raise TokenInvalidError(f"Refresh token 无效: {e}")
    if payload.get("type") != TOKEN_TYPE_REFRESH:
        raise TokenInvalidError("Token 不是 refresh 类型")
    if not payload.get("sid"):
        raise TokenInvalidError("Refresh token 缺少 sid 字段")
    if payload.get("sub") is None:
        raise TokenInvalidError("Refresh token 缺少 sub 字段")
    return payload


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
