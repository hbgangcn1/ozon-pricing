from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from db_utils import get_db_connection, _safe_adapt_sql
from api.models.schemas import MessageResponse
from api.dependencies import require_admin

router = APIRouter(prefix="/api/admin", tags=["管理员"])


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


@router.get("/users")
def get_all_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = None,
    admin: int = Depends(require_admin),
):
    offset = (page - 1) * page_size
    with get_db_connection() as (conn, c):
        # 查询总数
        if keyword:
            count_sql = _safe_adapt_sql(
                "SELECT COUNT(*) FROM users WHERE username LIKE %s", conn
            )
            c.execute(count_sql, (f"%{keyword}%",))
        else:
            count_sql = _safe_adapt_sql("SELECT COUNT(*) FROM users", conn)
            c.execute(count_sql)
        total = c.fetchone()[0]

        if keyword:
            sql_raw = """
                SELECT id, username, role, user_type, subscription_expires, (CASE WHEN is_frozen THEN '冻结' ELSE '正常' END) AS status
                FROM users
                WHERE username LIKE %s
                ORDER BY id
                LIMIT %s OFFSET %s
            """
            sql = _safe_adapt_sql(sql_raw, conn)
            c.execute(sql, (f"%{keyword}%", page_size, offset))
        else:
            sql_raw = """
                SELECT id, username, role, user_type, subscription_expires, (CASE WHEN is_frozen THEN '冻结' ELSE '正常' END) AS status
                FROM users
                ORDER BY id
                LIMIT %s OFFSET %s
            """
            sql = _safe_adapt_sql(sql_raw, conn)
            c.execute(sql, (page_size, offset))

        columns = [desc[0] for desc in c.description]
        users = []
        for row in c.fetchall():
            user = dict(zip(columns, row))
            users.append(
                UserResponse(
                    id=user["id"],
                    username=user["username"],
                    role=user["role"],
                    user_type=user.get("user_type", "free"),
                    subscription_expired_at=str(user["subscription_expires"])
                    if user.get("subscription_expires")
                    else None,
                    status=user.get("status", "正常"),
                )
            )
        return {"users": users, "total": total, "page": page, "page_size": page_size}


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(user: UserCreate, admin: int = Depends(require_admin)):
    import bcrypt

    password_hash = bcrypt.hashpw(user.password.encode(), bcrypt.gensalt()).decode()

    with get_db_connection() as (conn, c):
        sql_raw = """
            INSERT INTO users (username, password, role, user_type, created_at)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """
        sql = _safe_adapt_sql(sql_raw, conn)
        c.execute(
            sql,
            (user.username, password_hash, user.role, user.user_type, datetime.now()),
        )
        conn.commit()
        user_id = c.fetchone()[0]

        return UserResponse(
            id=user_id,
            username=user.username,
            role=user.role,
            user_type=user.user_type,
            status="正常",
        )


@router.put("/users/{user_id}", response_model=UserResponse)
def update_user(user_id: int, update: UserUpdate, admin: int = Depends(require_admin)):
    with get_db_connection() as (conn, c):
        sql_raw = "SELECT id FROM users WHERE id = %s"
        sql = _safe_adapt_sql(sql_raw, conn)
        c.execute(sql, (user_id,))
        if not c.fetchone():
            raise HTTPException(status_code=404, detail="用户不存在")

        ALLOWED_USER_UPDATE_FIELDS = {"role", "user_type"}
        update_data = update.model_dump(exclude_unset=True)
        sanitized = {
            k: v for k, v in update_data.items() if k in ALLOWED_USER_UPDATE_FIELDS
        }
        if sanitized:
            set_clause = ", ".join([f"{k} = %s" for k in sanitized.keys()])
            sql_raw = f"UPDATE users SET {set_clause} WHERE id = %s"
            sql = _safe_adapt_sql(sql_raw, conn)
            c.execute(sql, list(sanitized.values()) + [user_id])
            conn.commit()

        sql_raw = """
            SELECT id, username, role, user_type, subscription_expires, (CASE WHEN is_frozen THEN '冻结' ELSE '正常' END) AS status
            FROM users WHERE id = %s
        """
        sql = _safe_adapt_sql(sql_raw, conn)
        c.execute(sql, (user_id,))
        row = c.fetchone()
        return UserResponse(
            id=row[0],
            username=row[1],
            role=row[2],
            user_type=row[3] or "free",
            subscription_expired_at=str(row[4]) if row[4] else None,
            status=row[5] or "正常",
        )


@router.post("/users/{user_id}/reset-password", response_model=MessageResponse)
def reset_user_password(user_id: int, admin: int = Depends(require_admin)):
    import bcrypt
    import secrets

    new_password = secrets.token_urlsafe(12)
    password_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()

    with get_db_connection() as (conn, c):
        sql_raw = "UPDATE users SET password = %s WHERE id = %s"
        sql = _safe_adapt_sql(sql_raw, conn)
        c.execute(sql, (password_hash, user_id))
        conn.commit()
        if c.rowcount == 0:
            raise HTTPException(status_code=404, detail="用户不存在")
    return MessageResponse(message=f"密码已重置为: {new_password}")


@router.delete("/users/{user_id}", response_model=MessageResponse)
def delete_user(user_id: int, admin: int = Depends(require_admin)):
    if user_id == 1:
        raise HTTPException(status_code=400, detail="不能删除超级管理员")

    with get_db_connection() as (conn, c):
        sql_raw = "DELETE FROM users WHERE id = %s"
        sql = _safe_adapt_sql(sql_raw, conn)
        c.execute(sql, (user_id,))
        conn.commit()
        if c.rowcount == 0:
            raise HTTPException(status_code=404, detail="用户不存在")
    return MessageResponse(message="删除成功")
