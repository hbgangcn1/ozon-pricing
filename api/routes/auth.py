import re
import secrets
import time

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from db.sessions_crud import (
    deactivate_all_sessions,
    deactivate_session,
    get_session,
    insert_session,
    update_session_activity,
)
from db.users import (
    verify_user,
    create_user,
    update_user_password,
    find_by_username,
    get_user_by_id,
)
from db.config import is_registration_open
from api.models.schemas import (
    UserLogin,
    UserResponse,
    TokenResponse,
    MessageResponse,
    RefreshResponse,
    UserRegister,
    ChangePassword,
    PasswordRecoveryStartRequest,
    PasswordRecoveryStartResponse,
    PasswordRecoveryVerifyRequest,
    PasswordRecoveryVerifyResponse,
    PasswordRecoveryResetRequest,
)
from models.user import User
from security.tokens import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    TokenExpiredError,
    TokenInvalidError,
)
from api.dependencies import (
    get_current_user_id,
    get_current_user as get_current_user_dep,
    validate_cookie_csrf,
)
from api.middleware.login_limiter import login_limiter
from api.middleware.username_check_limiter import (
    UsernameCheckRateLimiter,
    username_check_limiter,
)
from api.routes.auth_recovery import (
    reset_password_with_token,
    start_password_recovery,
    verify_password_recovery,
)
from api.routes.auth_support import (
    clear_token_cookies,
    decode_refresh_cookie,
    get_request_user_agent,
    normalize_user_identity,
    set_token_cookie,
)
from logger_config import logger

_TRUSTED_RATE_LIMIT_PROXIES = {"127.0.0.1", "::1", "localhost", "testclient"}
recover_start_limiter = UsernameCheckRateLimiter(max_requests=5, window_seconds=60)
recover_verify_limiter = UsernameCheckRateLimiter(max_requests=5, window_seconds=60)


def validate_password(password: str) -> bool:
    if len(password) < 13:
        return False
    if not re.search(r"[a-z]", password):
        return False
    if not re.search(r"[A-Z]", password):
        return False
    if not re.search(r"\d", password):
        return False
    if not re.search(r"[^a-zA-Z0-9]", password):
        return False
    return True


router = APIRouter(prefix="/api/auth", tags=["认证"])


def _get_request_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _get_username_check_client_ip(request: Request) -> str:
    client_ip = _get_request_ip(request)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for and client_ip in _TRUSTED_RATE_LIMIT_PROXIES:
        return forwarded_for.split(",")[0].strip()
    return client_ip


async def _issue_auth_tokens(
    session: AsyncSession,
    request: Request,
    user_id: int,
    username: str,
    role: str,
) -> tuple[str, str]:
    sid = secrets.token_urlsafe(32)
    now = time.time()
    await insert_session(
        session,
        session_id=sid,
        user_id=user_id,
        ip_address=_get_request_ip(request),
        user_agent=get_request_user_agent(request.headers.get("user-agent")),
        now=now,
    )
    await deactivate_all_sessions(
        session,
        user_id,
        exclude_session_id=sid,
        reason="kicked_by_new_login",
    )
    access_token = create_access_token(
        user_id=user_id,
        username=username,
        role=role,
        extra_claims={"sid": sid},
    )
    refresh_token = create_refresh_token(user_id=user_id, sid=sid)
    return access_token, refresh_token


@router.post("/login")
async def login(
    credentials: UserLogin,
    request: Request,
    session: AsyncSession = Depends(get_db),
):
    client_ip = _get_request_ip(request)
    login_limiter.check(client_ip)

    user = await verify_user(session, credentials.username, credentials.password)
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
    access_token, refresh_token = await _issue_auth_tokens(
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
            remaining_calculations=user.get("remaining_calculations", -1),
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
    client_ip = _get_request_ip(request)
    logger.info("auth.logout ip=%s", client_ip)
    if request.cookies.get("access_token") or request.cookies.get("refresh_token"):
        validate_cookie_csrf(request)
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        try:
            payload = decode_refresh_token(refresh_token)
            await deactivate_session(
                session,
                payload["sid"],
                reason="manual_logout",
            )
        except (TokenExpiredError, TokenInvalidError):
            pass
    response = JSONResponse(
        content=MessageResponse(message="登出成功").model_dump(),
    )
    clear_token_cookies(response)
    return response


@router.get("/check-username")
async def check_username(
    request: Request,
    username: str,
    session: AsyncSession = Depends(get_db),
):
    # 不抛 4xx：前端 axios 拦截器会把 4xx 当全局错误，破坏注册表单的 inline 提示
    client_ip = _get_username_check_client_ip(request)
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
    existing = await find_by_username(session, username)
    if existing:
        return {"available": False, "reason": "用户名已被占用"}
    return {"available": True, "reason": None}


@router.post("/register")
async def register(
    user_data: UserRegister,
    request: Request,
    session: AsyncSession = Depends(get_db),
):
    if not await is_registration_open(session):
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

    existing = await find_by_username(session, user_data.username)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该用户名不可用",
        )

    user_id = await create_user(
        session,
        username=user_data.username,
        password=user_data.password,
        role="user",
    )
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="创建用户失败",
        )

    client_ip = _get_request_ip(request)
    logger.info(
        "auth.register.success user_id=%s username=%s ip=%s",
        user_id,
        user_data.username,
        client_ip,
    )

    access_token, refresh_token = await _issue_auth_tokens(
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
        ),
    )
    response = JSONResponse(content=body.model_dump())
    set_token_cookie(response, access_token, refresh_token)
    return response


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


@router.post("/recover/start", response_model=PasswordRecoveryStartResponse)
async def recover_start(
    payload: PasswordRecoveryStartRequest,
    request: Request,
):
    client_ip = _get_username_check_client_ip(request)
    recover_start_limiter.check(client_ip)
    return await start_password_recovery(payload.username, client_ip)


@router.post("/recover/verify", response_model=PasswordRecoveryVerifyResponse)
async def recover_verify(
    payload: PasswordRecoveryVerifyRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
):
    client_ip = _get_username_check_client_ip(request)
    recover_verify_limiter.check(client_ip)
    reset_token = await verify_password_recovery(
        session=session,
        username=payload.username,
        answer1=payload.answer1,
        answer2=payload.answer2,
        client_ip=client_ip,
    )
    return {"reset_token": reset_token}


@router.post("/recover/reset", response_model=MessageResponse)
async def recover_reset(
    payload: PasswordRecoveryResetRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
):
    message = await reset_password_with_token(
        session=session,
        reset_token=payload.reset_token,
        new_password=payload.new_password,
        client_ip=_get_request_ip(request),
    )
    return MessageResponse(message=message)


@router.get("/me", response_model=UserResponse)
async def get_me(
    user: dict = Depends(get_current_user_dep),
):
    return UserResponse(
        id=user["id"],
        username=user["username"],
        role=user["role"],
        user_type=user.get("user_type") or "free",
        subscription_type=user.get("subscription_type") or "free",
        remaining_calculations=(
            user["remaining_calculations"]
            if user.get("remaining_calculations") is not None
            else -1
        ),
    )


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    data: ChangePassword,
    request: Request,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    if not validate_password(data.new_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="密码必须至少13位，包含大小写字母、数字和特殊字符",
        )

    existing_user = await get_user_by_id(session, user_id)
    if not existing_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="认证已失效",
        )

    success = await update_user_password(
        session,
        user_id,
        data.current_password,
        data.new_password,
    )
    client_ip = _get_request_ip(request)
    if not success:
        logger.warning(
            "auth.change_password.failed user_id=%s ip=%s",
            user_id,
            client_ip,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="当前密码错误",
        )

    logger.info(
        "auth.change_password.success user_id=%s ip=%s",
        user_id,
        client_ip,
    )
    return MessageResponse(message="密码修改成功")
