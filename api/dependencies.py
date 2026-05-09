import os
import secrets
from urllib.parse import urlparse

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from db.sessions_crud import get_session
from models.user import User
from security.tokens import (
    decode_access_token,
    TokenExpiredError,
    TokenInvalidError,
)

security = HTTPBearer(auto_error=False)
COMMISSION_ALLOWED_TIERS = {"professional", "enterprise", "gratitude", "test"}
EXCEL_ALLOWED_TIERS = {"enterprise", "gratitude", "test"}

_allowed_origins_raw = os.environ.get("ALLOWED_ORIGINS", "")
_ALLOWED_ORIGINS = {
    o.strip().rstrip("/") for o in _allowed_origins_raw.split(",") if o.strip()
}


def _check_csrf_origin(request: Request) -> None:
    """Validate Origin for cookie-auth state-changing requests."""
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    if not _ALLOWED_ORIGINS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="服务器未配置允许的来源，禁止 cookie 认证的状态变更请求",
        )
    origin = request.headers.get("origin")
    if not origin:
        referer = request.headers.get("referer")
        if referer:
            parsed = urlparse(referer)
            origin = f"{parsed.scheme}://{parsed.netloc}"
    if not origin or origin.rstrip("/") not in _ALLOWED_ORIGINS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="请求来源不合法",
        )


def _check_csrf_double_submit(request: Request) -> None:
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    cookie_csrf = request.cookies.get("csrf_token")
    header_csrf = request.headers.get("x-csrf-token")
    if not cookie_csrf or not header_csrf:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="缺少CSRF令牌",
        )
    if not secrets.compare_digest(cookie_csrf, header_csrf):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF令牌不匹配",
        )


def validate_cookie_csrf(request: Request) -> None:
    _check_csrf_origin(request)
    _check_csrf_double_submit(request)


def _extract_token(api_key, request: Request) -> str:
    if api_key and api_key.credentials:
        return api_key.credentials
    cookie_token = request.cookies.get("access_token")
    if cookie_token:
        validate_cookie_csrf(request)
        return cookie_token
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="未提供认证凭证",
    )


async def _get_user(token: str, session: AsyncSession) -> User:
    try:
        payload = decode_access_token(token)
    except (TokenExpiredError, TokenInvalidError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭证",
        )
    try:
        sub = payload.get("sub")
        user_id = int(sub) if sub is not None else None
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭证",
        )
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭证",
        )
    sid = payload.get("sid")
    if sid:
        active_session = await get_session(session, sid)
        if not active_session or not active_session.is_active:
            reason = active_session.inactive_reason if active_session else None
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "会话已失效", "reason": reason},
            )
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
        )
    if bool(user.is_frozen):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账户已被冻结",
        )
    return user


async def get_current_user_id(
    request: Request,
    api_key=Depends(security),
    session: AsyncSession = Depends(get_db),
) -> int:
    token = _extract_token(api_key, request)
    user = await _get_user(token, session)
    return user.id


async def get_current_user(
    request: Request,
    api_key=Depends(security),
    session: AsyncSession = Depends(get_db),
) -> dict:
    token = _extract_token(api_key, request)
    user = await _get_user(token, session)
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "user_type": user.user_type,
        "subscription_type": user.subscription_type or "free",
        "remaining_calculations": user.remaining_calculations,
        "security_q1": user.security_q1,
        "trial_used": user.trial_used or 0,
        "trial_started_at": user.trial_started_at or 0,
        "trial_expires_at": user.trial_expires_at or 0,
        "trial_plan_at_start": user.trial_plan_at_start or "",
    }


async def get_user_with_subscription(
    request: Request,
    api_key=Depends(security),
    session: AsyncSession = Depends(get_db),
) -> dict:
    token = _extract_token(api_key, request)
    user = await _get_user(token, session)
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "user_type": user.user_type,
        "subscription_type": user.subscription_type or "free",
        "remaining_calculations": user.remaining_calculations,
        "trial_used": user.trial_used or 0,
        "trial_started_at": user.trial_started_at or 0,
        "trial_expires_at": user.trial_expires_at or 0,
        "trial_plan_at_start": user.trial_plan_at_start or "",
    }


async def require_admin(
    request: Request,
    api_key=Depends(security),
    session: AsyncSession = Depends(get_db),
) -> int:
    token = _extract_token(api_key, request)
    user = await _get_user(token, session)
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限",
        )
    return user.id
