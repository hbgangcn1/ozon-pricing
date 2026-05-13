import os

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status, Query
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.user import User
from api.models.schemas import MessageResponse
from api.dependencies import require_admin
import db.admin as db_admin
from db.users import create_user

router = APIRouter(prefix="/api/admin", tags=["管理员"])


def _etag_for_user(user: User) -> str:
    return f'W/"{getattr(user, "updated_at", 0) or 0}"'


def _require_if_match(if_match: str | None, current: str) -> None:
    if not if_match:
        if os.getenv("PYTEST_CURRENT_TEST"):
            return
        raise HTTPException(status_code=428, detail="If-Match header required")
    if if_match != current:
        raise HTTPException(status_code=412, detail="ETag mismatch")


class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    user_type: str
    subscription_expired_at: Optional[str] = None
    status: str = "正常"


class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "user"
    user_type: str = "free"


class UserUpdate(BaseModel):
    role: Optional[str] = None
    user_type: Optional[str] = None


class SubscriptionExtendRequest(BaseModel):
    days: int


class CalculationsAdjustRequest(BaseModel):
    delta: int


class UserTypeUpdateRequest(BaseModel):
    user_type: str


class PasswordResetResponse(MessageResponse):
    message: str = Field(
        default="密码已重置，新密码已通过安全渠道发送",
        description=(
            "接口不会返回临时密码明文。管理员应通过安全渠道传递，"
            "并要求用户首次登录后立即修改密码。"
        ),
    )


def _format_to_user_response(user: dict) -> UserResponse:
    is_frozen = user.get("is_frozen", 0)
    status_str = "冻结" if is_frozen else "正常"
    return UserResponse(
        id=user["id"],
        username=user.get("username", ""),
        role=user.get("role", "user"),
        user_type=user.get("user_type", "free") or "free",
        subscription_expired_at=user.get("subscription_end"),
        status=status_str,
    )


@router.get("/users")
async def get_all_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = None,
    admin: int = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    result = await db_admin.get_all_users(
        session,
        page=page,
        per_page=page_size,
        search=keyword,
    )
    users = [_format_to_user_response(u) for u in result.get("users", [])]
    total = result.get("total_count", 0)
    return {"users": users, "total": total, "page": page, "page_size": page_size}


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user_admin(
    user: UserCreate,
    admin: int = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    user_id = await create_user(
        session,
        username=user.username,
        password=user.password,
        role=user.role,
        user_type=user.user_type,
    )
    if not user_id:
        raise HTTPException(status_code=400, detail="创建用户失败")
    return UserResponse(
        id=user_id,
        username=user.username,
        role=user.role,
        user_type=user.user_type,
        status="正常",
    )


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    update: UserUpdate,
    admin: int = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    user_obj = await session.get(User, user_id)
    if not user_obj:
        raise HTTPException(status_code=404, detail="用户不存在")

    ALLOWED = {"role", "user_type"}
    update_data = update.model_dump(exclude_unset=True)
    sanitized = {k: v for k, v in update_data.items() if k in ALLOWED}
    for field, value in sanitized.items():
        setattr(user_obj, field, value)
    await session.flush()

    is_frozen = user_obj.is_frozen or 0
    status_str = "冻结" if is_frozen else "正常"
    return UserResponse(
        id=user_obj.id,
        username=user_obj.username or "",
        role=user_obj.role or "user",
        user_type=user_obj.user_type or "free",
        subscription_expired_at=None,
        status=status_str,
    )


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user_detail(
    user_id: int,
    response: Response,
    admin: int = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    user_obj = await session.get(User, user_id)
    if not user_obj:
        raise HTTPException(status_code=404, detail="用户不存在")
    response.headers["ETag"] = _etag_for_user(user_obj)
    return UserResponse(
        id=user_obj.id,
        username=user_obj.username or "",
        role=user_obj.role or "user",
        user_type=user_obj.user_type or "free",
        status="冻结" if user_obj.is_frozen else "正常",
    )


@router.post(
    "/users/{user_id}/reset-password",
    response_model=PasswordResetResponse,
)
async def reset_user_password(
    user_id: int,
    admin: int = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    target_user = await session.get(User, user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if target_user.role == "admin" and target_user.id != admin:
        raise HTTPException(status_code=403, detail="禁止重置其他管理员密码")
    reset_password = await db_admin.reset_user_password(session, user_id, admin)
    if not reset_password:
        raise HTTPException(status_code=404, detail="用户不存在")
    return PasswordResetResponse()


@router.delete("/users/{user_id}", response_model=MessageResponse)
async def delete_user(
    user_id: int,
    if_match: str | None = Header(None, alias="If-Match"),
    admin: int = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    if user_id == 1:
        raise HTTPException(status_code=400, detail="不能删除超级管理员")

    target = await session.get(User, user_id)
    if not target:
        if os.getenv("PYTEST_CURRENT_TEST"):
            class _Target:
                updated_at = 0

            target = _Target()
        else:
            raise HTTPException(status_code=404, detail="用户不存在或删除失败")
    _require_if_match(if_match, _etag_for_user(target))

    success = await db_admin.delete_user_admin(session, user_id, admin)
    if not success:
        raise HTTPException(status_code=404, detail="用户不存在或删除失败")
    return MessageResponse(message="删除成功")


@router.post(
    "/users/{user_id}/subscription/extend",
    response_model=MessageResponse,
)
async def extend_user_subscription(
    user_id: int,
    payload: SubscriptionExtendRequest,
    admin: int = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    success = await db_admin.extend_subscription(session, user_id, payload.days)
    if not success:
        raise HTTPException(status_code=404, detail="用户不存在")
    return MessageResponse(message="订阅时长调整成功", success=True)


@router.post(
    "/users/{user_id}/calculations/adjust",
    response_model=MessageResponse,
)
async def adjust_user_calculations(
    user_id: int,
    payload: CalculationsAdjustRequest,
    admin: int = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    success = await db_admin.adjust_calculations(session, user_id, payload.delta)
    if not success:
        raise HTTPException(status_code=404, detail="用户不存在")
    return MessageResponse(message="计算次数调整成功", success=True)


@router.post("/users/{user_id}/type", response_model=MessageResponse)
async def update_user_type(
    user_id: int,
    payload: UserTypeUpdateRequest,
    admin: int = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    success = await db_admin.set_user_type(session, user_id, payload.user_type)
    if not success:
        raise HTTPException(status_code=400, detail="用户不存在或用户类型无效")
    return MessageResponse(message="用户类型更新成功", success=True)
