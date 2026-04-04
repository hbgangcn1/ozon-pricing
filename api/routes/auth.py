import re
from fastapi import APIRouter, Depends, HTTPException, status

from db_utils import (
    verify_user,
    get_db_connection,
    _safe_adapt_sql,
    is_registration_open,
    create_user,
    update_user_password,
)
from api.models.schemas import (
    UserLogin,
    UserResponse,
    TokenResponse,
    MessageResponse,
    UserRegister,
    ChangePassword,
)
from security.tokens import create_access_token
from api.dependencies import (
    get_current_user_id,
    get_current_user as get_current_user_dep,
)


def validate_password(password: str) -> bool:
    """验证密码强度：至少13位，包含大小写字母、数字和特殊字符"""
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


@router.post("/login", response_model=TokenResponse)
async def login(credentials: UserLogin):
    user = verify_user(credentials.username, credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    token = create_access_token(
        user_id=user["id"],
        username=user["username"],
        role=user.get("role", "user"),
    )
    return TokenResponse(
        access_token=token,
        user=UserResponse(
            id=user["id"],
            username=user["username"],
            role=user["role"],
            user_type=user.get("user_type", "free"),
            remaining_calculations=user.get("remaining_calculations", -1),
        ),
    )


@router.post("/logout", response_model=MessageResponse)
async def logout():
    return MessageResponse(message="登出成功")


@router.post("/register", response_model=TokenResponse)
async def register(user_data: UserRegister):
    # 检查注册是否开放
    if not is_registration_open():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="注册功能已关闭",
        )

    # 验证用户名格式
    if not re.match(r"^[a-zA-Z0-9_]{3,50}$", user_data.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名只能包含字母、数字和下划线，长度3-50位",
        )

    # 验证密码强度
    if not validate_password(user_data.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="密码必须至少13位，包含大小写字母、数字和特殊字符",
        )

    # 检查用户名是否已存在
    with get_db_connection() as (conn, c):
        sql_raw = "SELECT id FROM users WHERE username = %s"
        sql = _safe_adapt_sql(sql_raw, conn)
        c.execute(sql, (user_data.username,))
        if c.fetchone():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户名已存在",
            )

    # 创建用户
    user_id = create_user(
        username=user_data.username,
        password=user_data.password,
        role="user",
    )

    token = create_access_token(
        user_id=user_id,
        username=user_data.username,
        role="user",
    )
    return TokenResponse(
        access_token=token,
        user=UserResponse(
            id=user_id,
            username=user_data.username,
            role="user",
            user_type="free",
            remaining_calculations=-1,
        ),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(
    user: dict = Depends(get_current_user_dep),
):
    return UserResponse(
        id=user["id"],
        username=user["username"],
        role=user["role"],
        user_type=user.get("user_type") or "free",
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
):
    # 验证新密码强度
    if not validate_password(data.new_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="密码必须至少13位，包含大小写字母、数字和特殊字符",
        )

    # 使用现有的 update_user_password 函数更新密码
    success = update_user_password(
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
