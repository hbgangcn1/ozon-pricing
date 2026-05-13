from fastapi import HTTPException, status
from fastapi import Request
from fastapi.responses import JSONResponse

from models.user import User
from security.csrf import generate_csrf_token
from security.utils import auth_cookie_domain, auth_cookie_kwargs
from security.tokens import (
    TokenExpiredError,
    TokenInvalidError,
    decode_refresh_token,
)

_ACCESS_COOKIE_MAX_AGE = 15 * 60
_REFRESH_COOKIE_MAX_AGE = 7 * 24 * 3600


def get_request_user_agent(user_agent: str | None) -> str:
    return user_agent or ""


def normalize_user_identity(user: User) -> tuple[str, str]:
    username = user.username or ""
    role = user.role or "user"
    return username, role


def set_token_cookie(
    response: JSONResponse,
    request: Request,
    access_token: str,
    refresh_token: str,
) -> None:
    """Set auth cookies with centralized security attributes.

    [SEC-W12R2-04] access_token, refresh_token, and csrf_token cookies must use
    the same Secure/SameSite/path derivation on login and refresh responses.
    """
    cookie_kwargs = auth_cookie_kwargs(request)
    cookie_domain = auth_cookie_domain()
    response.set_cookie(
        key="access_token",
        value=access_token,
        domain=cookie_domain,
        max_age=_ACCESS_COOKIE_MAX_AGE,
        **cookie_kwargs,
    )
    csrf_cookie_kwargs = {**cookie_kwargs, "httponly": False}
    response.set_cookie(
        key="csrf_token",
        value=generate_csrf_token(),
        domain=cookie_domain,
        max_age=_REFRESH_COOKIE_MAX_AGE,
        **csrf_cookie_kwargs,
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        domain=cookie_domain,
        max_age=_REFRESH_COOKIE_MAX_AGE,
        **cookie_kwargs,
    )


def clear_token_cookies(response: JSONResponse, request: Request) -> None:
    cookie_kwargs = auth_cookie_kwargs(request)
    cookie_domain = auth_cookie_domain()
    response.delete_cookie(
        key="access_token",
        domain=cookie_domain,
        **cookie_kwargs,
    )
    response.delete_cookie(
        key="refresh_token",
        domain=cookie_domain,
        **cookie_kwargs,
    )
    csrf_cookie_kwargs = {**cookie_kwargs, "httponly": False}
    response.delete_cookie(
        key="csrf_token",
        domain=cookie_domain,
        **csrf_cookie_kwargs,
    )


def decode_refresh_cookie(token: str) -> dict:
    try:
        return decode_refresh_token(token)
    except (TokenExpiredError, TokenInvalidError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的刷新令牌",
        ) from exc
