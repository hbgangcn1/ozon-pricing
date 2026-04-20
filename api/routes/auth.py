import os
import re

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from db.users import (
    verify_user,
    create_user,
    update_user_password,
    find_by_username,
)
from db.config import is_registration_open
from api.models.schemas import (
    UserLogin,
    UserResponse,
    TokenResponse,
    MessageResponse,
    UserRegister,
    ChangePassword,
)
from security.tokens import create_access_token
from security.csrf import generate_csrf_token
from api.dependencies import (
    get_current_user_id,
    get_current_user as get_current_user_dep,
)
from api.middleware.login_limiter import login_limiter

_is_production = os.environ.get("PRODUCTION_MODE", "").lower() == "true"
_cookie_secure = (
    os.environ.get("COOKIE_SECURE", "true" if _is_production else "false").lower()
    == "true"
)
_COOKIE_MAX_AGE = 8 * 3600  # 8 hours


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


def _set_token_cookie(response: JSONResponse, token: str) -> None:
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=_cookie_secure,
        samesite="strict",
        max_age=_COOKIE_MAX_AGE,
        path="/",
    )
    response.set_cookie(
        key="csrf_token",
        value=generate_csrf_token(),
        httponly=False,
        secure=_cookie_secure,
        samesite="strict",
        max_age=_COOKIE_MAX_AGE,
        path="/",
    )


@router.post("/login")
async def login(
    credentials: UserLogin,
    request: Request,
    session: AsyncSession = Depends(get_db),
):
    client_ip = request.client.host if request.client else "unknown"
    login_limiter.check(client_ip)

    user = await verify_user(session, credentials.username, credentials.password)
    if not user:
        login_limiter.record_attempt(client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    login_limiter.clear(client_ip)
    token = create_access_token(
        user_id=user["id"],
        username=user["username"],
        role=user.get("role", "user"),
    )
    body = TokenResponse(
        access_token=token,
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
    _set_token_cookie(response, token)
    return response


@router.post("/logout")
async def logout():
    response = JSONResponse(
        content=MessageResponse(message="登出成功").model_dump(),
    )
    response.delete_cookie(
        key="access_token",
        path="/",
        httponly=True,
        secure=_cookie_secure,
        samesite="strict",
    )
    response.delete_cookie(
        key="csrf_token",
        path="/",
        httponly=False,
        secure=_cookie_secure,
        samesite="strict",
    )
    return response


@router.post("/register")
async def register(
    user_data: UserRegister,
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
            detail="用户名已存在",
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

    token = create_access_token(
        user_id=user_id,
        username=user_data.username,
        role="user",
    )
    body = TokenResponse(
        access_token=token,
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
    _set_token_cookie(response, token)
    return response


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
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    if not validate_password(data.new_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="密码必须至少13位，包含大小写字母、数字和特殊字符",
        )

    success = await update_user_password(
        session,
        user_id,
        data.current_password,
        data.new_password,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="当前密码错误或用户不存在",
        )

    return MessageResponse(message="密码修改成功")
