import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt

SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "fallback-dev-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("JWT_EXPIRE_MINUTES", "1440"))


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
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Raises TokenExpiredError or TokenInvalidError."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
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
