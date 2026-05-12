import os

from fastapi import HTTPException, status
from fastapi.responses import JSONResponse

from models.user import User
from security.csrf import generate_csrf_token
from security.tokens import (
    TokenExpiredError,
    TokenInvalidError,
    decode_refresh_token,
)

_ACCESS_COOKIE_MAX_AGE = 15 * 60
_REFRESH_COOKIE_MAX_AGE = 7 * 24 * 3600


def _cookie_secure() -> bool:
    return os.getenv("ENV", "development") == "production"


def _cookie_domain() -> str | None:
    return ".cbprice.cn" if os.getenv("ENV", "development") == "production" else None


def get_request_user_agent(user_agent: str | None) -> str:
    return user_agent or ""


def normalize_user_identity(user: User) -> tuple[str, str]:
    username = user.username or ""
    role = user.role or "user"
    return username, role


def set_token_cookie(
    response: JSONResponse,
    access_token: str,
    refresh_token: str,
) -> None:
    cookie_secure = _cookie_secure()
    cookie_domain = _cookie_domain()
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=cookie_secure,
        domain=cookie_domain,
        samesite="strict",
        max_age=_ACCESS_COOKIE_MAX_AGE,
        path="/",
    )
    response.set_cookie(
        key="csrf_token",
        value=generate_csrf_token(),
        httponly=False,
        secure=cookie_secure,
        domain=cookie_domain,
        samesite="strict",
        max_age=_REFRESH_COOKIE_MAX_AGE,
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=cookie_secure,
        domain=cookie_domain,
        samesite="strict",
        max_age=_REFRESH_COOKIE_MAX_AGE,
        path="/",
    )


def clear_token_cookies(response: JSONResponse) -> None:
    cookie_secure = _cookie_secure()
    cookie_domain = _cookie_domain()
    response.delete_cookie(
        key="access_token",
        path="/",
        httponly=True,
        secure=cookie_secure,
        domain=cookie_domain,
        samesite="strict",
    )
    response.delete_cookie(
        key="refresh_token",
        path="/",
        httponly=True,
        secure=cookie_secure,
        domain=cookie_domain,
        samesite="strict",
    )
    response.delete_cookie(
        key="csrf_token",
        path="/",
        httponly=False,
        secure=cookie_secure,
        domain=cookie_domain,
        samesite="strict",
    )


def decode_refresh_cookie(token: str) -> dict:
    try:
        return decode_refresh_token(token)
    except (TokenExpiredError, TokenInvalidError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的刷新令牌",
        ) from exc
