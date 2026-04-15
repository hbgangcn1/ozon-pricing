from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.user import User
from security.tokens import (
    get_user_id_from_token,
    TokenExpiredError,
    TokenInvalidError,
)

security = HTTPBearer()
COMMISSION_ALLOWED_TIERS = {"professional", "enterprise", "gratitude", "test"}
EXCEL_ALLOWED_TIERS = {"enterprise", "gratitude", "test"}


def _resolve_user_id(token: str) -> int:
    try:
        return get_user_id_from_token(token)
    except (TokenExpiredError, TokenInvalidError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭证",
        )


async def get_current_user_id(
    api_key=Depends(security),
    session: AsyncSession = Depends(get_db),
) -> int:
    token = api_key.credentials
    user_id = _resolve_user_id(token)
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
        )
    if user.is_frozen == 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账户已被冻结",
        )
    return user_id


async def get_current_user(
    api_key=Depends(security),
    session: AsyncSession = Depends(get_db),
) -> dict:
    token = api_key.credentials
    user_id = _resolve_user_id(token)
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
        )
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "user_type": user.user_type,
        "subscription_type": user.subscription_type or "free",
        "remaining_calculations": user.remaining_calculations,
    }


async def get_user_with_subscription(
    api_key=Depends(security),
    session: AsyncSession = Depends(get_db),
) -> dict:
    token = api_key.credentials
    user_id = _resolve_user_id(token)
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
        )
    if user.is_frozen == 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账户已被冻结",
        )
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "user_type": user.user_type,
        "subscription_type": user.subscription_type or "free",
        "remaining_calculations": user.remaining_calculations,
    }


async def require_admin(
    api_key=Depends(security),
    session: AsyncSession = Depends(get_db),
) -> int:
    token = api_key.credentials
    user_id = _resolve_user_id(token)
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
        )
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限",
        )
    return user_id
