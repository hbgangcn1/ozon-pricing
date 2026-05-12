import time

from fastapi import Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from db.sessions_crud import get_session, update_session_activity
from models.user import User
from security.tokens import (
    create_access_token,
    create_access_token_from_payload,
    create_refresh_token,
    decode_access_token,
    TokenExpiredError,
    TokenInvalidError,
)
from api.dependencies import validate_cookie_csrf
from api.models.schemas import RefreshResponse
from api.routes.auth_support import (
    decode_refresh_cookie,
    normalize_user_identity,
    set_token_cookie,
)

from ._router import router


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_token(
    request: Request,
    session: AsyncSession = Depends(get_db),
):
    validate_cookie_csrf(request)
    refresh_token_value = request.cookies.get("refresh_token")
    if not refresh_token_value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少刷新令牌",
        )

    payload = decode_refresh_cookie(refresh_token_value)
    sid = payload["sid"]
    session_row = await get_session(session, sid)
    if not session_row or not session_row.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="会话无效或已失效",
        )

    user = await session.get(User, int(payload["sub"]))
    if not user or bool(user.is_frozen):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="会话无效或已失效",
        )

    now = time.time()
    await update_session_activity(session, sid, now)
    username, role = normalize_user_identity(user)
    access_token = create_access_token(
        user_id=user.id,
        username=username,
        role=role,
        extra_claims={"sid": sid},
    )
    new_refresh_token = create_refresh_token(user_id=user.id, sid=sid)
    body = RefreshResponse(access_token=access_token)
    response = JSONResponse(content=body.model_dump())
    set_token_cookie(response, access_token, new_refresh_token)
    return response


@router.post("/refresh-access", response_model=RefreshResponse)
async def refresh_access_token_bearer(
    request: Request,
    session: AsyncSession = Depends(get_db),
):
    """Proactive access token refresh via Bearer auth (no CSRF).

    Frontend calls this when token is near expiry (< 5 min remaining).
    Decodes the Bearer token, verifies user exists and not frozen, then
    issues a fresh access token.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少或无效的 Bearer token",
        )
    token = auth_header[7:]

    try:
        payload = decode_access_token(token)
    except (TokenExpiredError, TokenInvalidError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 无效或已过期",
        )
    user_id = int(payload["sub"])
    sid = payload.get("sid")

    if sid:
        session_row = await get_session(session, sid)
        if not session_row or not session_row.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="会话无效或已失效",
            )

    user = await session.get(User, user_id)
    if not user or bool(user.is_frozen):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在或已冻结",
        )

    if sid:
        await update_session_activity(session, sid, time.time())
    access_token = create_access_token_from_payload(payload)
    return JSONResponse(content=RefreshResponse(access_token=access_token).model_dump())
