import re
import time
from typing import cast

from fastapi import Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from api.dependencies import validate_cookie_csrf
from api.models.schemas import (
    MessageResponse,
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
)
from api.middleware.login_limiter import login_limiter
from api.middleware.username_check_limiter import username_check_limiter
from api.routes.auth_support import clear_token_cookies, set_token_cookie
from logger_config import logger

from ._router import router
from .helpers import (
    get_request_ip,
    get_username_check_client_ip,
    auth_module,
    issue_auth_tokens,
    validate_password,
)


@router.post("/login")
async def login(
    credentials: UserLogin,
    request: Request,
    session: AsyncSession = Depends(get_db),
):
    client_ip = get_request_ip(request)
    login_limiter.check(client_ip)
    auth = auth_module()

    user = await auth.verify_user(session, credentials.username, credentials.password)
    if not user:
        login_limiter.record_attempt(client_ip)
        logger.warning(
            "auth.login.failed username=%s ip=%s",
            credentials.username,
            client_ip,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    login_limiter.clear(client_ip)
    logger.info(
        "auth.login.success user_id=%s username=%s ip=%s",
        user["id"],
        user["username"],
        client_ip,
    )
    await auth.reset_user_daily_calculations(session, user["id"])
    refreshed_user = await auth.get_user_by_id(session, user["id"])
    access_token, refresh_token = await issue_auth_tokens(
        session=session,
        request=request,
        user_id=user["id"],
        username=user["username"],
        role=user.get("role", "user"),
    )
    body = TokenResponse(
        access_token=access_token,
        user=UserResponse(
            id=user["id"],
            username=user["username"],
            role=user["role"],
            user_type=user.get("user_type", "free"),
            subscription_type=user.get("subscription_type", "free"),
            remaining_calculations=cast(
                int,
                refreshed_user.remaining_calculations if refreshed_user else -1,
            ),
            has_security_question=bool(user.get("security_q1")),
            trial_used=(refreshed_user.trial_used or 0) if refreshed_user else 0,
            trial_started_at=(refreshed_user.trial_started_at or 0) if refreshed_user else 0,
            trial_expires_at=(refreshed_user.trial_expires_at or 0) if refreshed_user else 0,
            trial_plan_at_start=(refreshed_user.trial_plan_at_start or "") if refreshed_user else "",
        ),
    )
    response = JSONResponse(content=body.model_dump())
    set_token_cookie(response, access_token, refresh_token)
    return response


@router.get("/check-username")
async def check_username(
    request: Request,
    username: str,
    session: AsyncSession = Depends(get_db),
):
    # 不抛 4xx：前端 axios 拦截器会把 4xx 当全局错误，破坏注册表单的 inline 提示
    client_ip = get_username_check_client_ip(request)
    auth = auth_module()
    try:
        username_check_limiter.check(client_ip)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
            logger.warning(
                "auth.check_username.rate_limited ip=%s username=%s timestamp=%s",
                client_ip,
                username,
                int(time.time()),
            )
        raise

    if not re.match(r"^[a-zA-Z0-9_]{3,50}$", username):
        return {"available": False, "reason": "用户名只能包含字母、数字和下划线，长度3-50位"}
    existing = await auth.find_by_username(session, username)
    if existing:
        return {"available": False, "reason": "用户名已被占用"}
    return {"available": True, "reason": None}


@router.get("/security-questions")
async def list_security_questions():
    # 公开接口：返回预设安全问题列表，供注册/找回密码页面动态加载
    # 避免前后端硬编码漂移（参见 SECURITY_QUESTIONS in security_questions.py）
    from security_questions import get_security_questions
    return {"questions": get_security_questions()}


@router.post("/register")
async def register(
    user_data: UserRegister,
    request: Request,
    session: AsyncSession = Depends(get_db),
):
    auth = auth_module()
    if not await auth.is_registration_open(session):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="注册功能已关闭",
        )

    if not re.match(r"^[a-zA-Z0-9_]{3,50}$", user_data.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名只能包含字母、数字和下划线，长度3-50位",
        )

    if not validate_password(user_data.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="密码必须至少13位，包含大小写字母、数字和特殊字符",
        )

    existing = await auth.find_by_username(session, user_data.username)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该用户名不可用",
        )

    user_id = await auth.create_user(
        session,
        username=user_data.username,
        password=user_data.password,
        role="user",
        security_question=user_data.security_question,
        security_answer=user_data.security_answer,
    )
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="创建用户失败",
        )

    client_ip = get_request_ip(request)
    auth = auth_module()
    logger.info(
        "auth.register.success user_id=%s username=%s ip=%s",
        user_id,
        user_data.username,
        client_ip,
    )

    access_token, refresh_token = await issue_auth_tokens(
        session=session,
        request=request,
        user_id=user_id,
        username=user_data.username,
        role="user",
    )
    body = TokenResponse(
        access_token=access_token,
        user=UserResponse(
            id=user_id,
            username=user_data.username,
            role="user",
            user_type="free",
            subscription_type="free",
            remaining_calculations=-1,
            has_security_question=bool(
                user_data.security_question and user_data.security_answer
            ),
            trial_used=0,
            trial_started_at=0,
            trial_expires_at=0,
            trial_plan_at_start="",
        ),
    )
    response = JSONResponse(content=body.model_dump())
    set_token_cookie(response, access_token, refresh_token)
    return response


@router.post("/logout")
async def logout(
    request: Request,
    session: AsyncSession = Depends(get_db),
):
    client_ip = get_request_ip(request)
    auth = auth_module()
    logger.info("auth.logout ip=%s", client_ip)
    if request.cookies.get("access_token") or request.cookies.get("refresh_token"):
        validate_cookie_csrf(request)
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        try:
            payload = auth.decode_refresh_token(refresh_token)
            await auth.deactivate_session(
                session,
                payload["sid"],
                reason="manual_logout",
            )
        except (auth.TokenExpiredError, auth.TokenInvalidError):
            pass
    response = JSONResponse(
        content=MessageResponse(message="登出成功").model_dump(),
    )
    clear_token_cookies(response)
    return response
