import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt


def _get_jwt_secret() -> str:
    secret = os.environ.get("JWT_SECRET_KEY")
    if secret:
        return secret
    raise RuntimeError(
        "JWT_SECRET_KEY environment variable is required. "
        "Set it in .env for development or system environment for production."
    )


_SECRET_KEY: Optional[str] = None
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.environ.get(
        "ACCESS_TOKEN_EXPIRE_MINUTES", os.environ.get("JWT_EXPIRE_MINUTES", "15")
    )
)


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
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, _get_secret_key(), algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Raises TokenExpiredError or TokenInvalidError."""
    try:
        payload = jwt.decode(token, _get_secret_key(), algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise TokenExpiredError("Token 已过期")
    except jwt.InvalidTokenError as e:
        raise TokenInvalidError(f"Token 无效: {e}")


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
