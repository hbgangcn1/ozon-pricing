from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from pydantic import BaseModel
from typing import Optional
import bcrypt

from db_utils import verify_user, get_db_connection
from api.models.schemas import UserLogin, UserResponse, TokenResponse, MessageResponse

router = APIRouter(prefix="/api/auth", tags=["认证"])
security = HTTPBearer()


@router.post("/login", response_model=TokenResponse)
async def login(credentials: UserLogin):
    user = verify_user(credentials.username, credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误"
        )

    return TokenResponse(
        access_token=credentials.username,
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


@router.get("/me", response_model=UserResponse)
async def get_current_user(user_id: int = Depends(lambda: 1)):
    with get_db_connection() as (conn, c):
        sql = "SELECT id, username, role, user_type, remaining_calculations FROM users WHERE id = ?"
        c.execute(sql, (user_id,))
        row = c.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="用户不存在")
        return UserResponse(
            id=row[0],
            username=row[1],
            role=row[2],
            user_type=row[3] or "free",
            remaining_calculations=row[4] if row[4] is not None else -1,
        )
