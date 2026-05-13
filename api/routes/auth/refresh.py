import time

from fastapi import Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from db.sessions_crud import get_session, update_session_activity
from models.user import User
from security.tokens import (
    create_access_token,
    create_refresh_token,
    revoke_refresh_token_jti,
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
    revoke_refresh_token_jti(payload.get("jti"))
    body = RefreshResponse(access_token=access_token)
    response = JSONResponse(content=body.model_dump())
    set_token_cookie(response, request, access_token, new_refresh_token)
    return response


@router.post("/refresh-access", response_model=RefreshResponse)
async def refresh_access_token_bearer(
    request: Request,
    session: AsyncSession = Depends(get_db),
):
    """Refresh access token via HttpOnly refresh-token cookie only.

    [SEC-W12R2-03] Access/Bearer tokens are intentionally ignored here:
    only a refresh token with type="refresh" from the refresh_token cookie can
    mint new credentials, and every successful use rotates the refresh token.
    """
    refresh_token_value = request.cookies.get("refresh_token")
    if not refresh_token_value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少刷新令牌",
        )

    try:
        payload = decode_refresh_cookie(refresh_token_value)
    except (TokenExpiredError, TokenInvalidError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="刷新令牌无效或已过期",
        )
    user_id = int(payload["sub"])
    sid = payload["sid"]

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

    await update_session_activity(session, sid, time.time())
    username, role = normalize_user_identity(user)
    access_token = create_access_token(
        user_id=user.id,
        username=username,
        role=role,
        extra_claims={"sid": sid},
    )
    new_refresh_token = create_refresh_token(user_id=user.id, sid=sid)
    revoke_refresh_token_jti(payload.get("jti"))
    body = RefreshResponse(access_token=access_token)
    response = JSONResponse(content=body.model_dump())
    set_token_cookie(response, request, access_token, new_refresh_token)
    return response
