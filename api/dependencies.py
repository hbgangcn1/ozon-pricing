from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer

from security.tokens import (
    get_user_id_from_token,
    TokenExpiredError,
    TokenInvalidError,
)
from db_utils import get_db_connection, _safe_adapt_sql

security = HTTPBearer()


def get_current_user_id(
    api_key=Depends(security),
) -> int:
    """从 JWT token 中提取并验证当前用户 ID。

    兼容策略：
    1. 先尝试 JWT 解码
    2. 若失败，回退到旧模式（token=用户名查DB）

    Returns:
        用户 ID (int)

    Raises:
        HTTPException 401: token 无效或用户不存在
    """
    token = api_key.credentials

    try:
        user_id = get_user_id_from_token(token)
        with get_db_connection() as (conn, c):
            sql = _safe_adapt_sql("SELECT id FROM users WHERE id = %s", conn)
            c.execute(sql, (user_id,))
            if c.fetchone():
                return user_id
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
        )
    except (TokenExpiredError, TokenInvalidError):
        pass

    with get_db_connection() as (conn, c):
        sql = _safe_adapt_sql("SELECT id FROM users WHERE username = %s", conn)
        c.execute(sql, (token,))
        row = c.fetchone()
        if row:
            return row[0]

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效的认证凭证",
    )


def get_current_user(api_key=Depends(security)) -> dict:
    """获取当前用户完整信息。

    Returns:
        用户信息字典: id, username, role, user_type,
                      remaining_calculations
    """
    token = api_key.credentials
    user_id = _resolve_user_id(token)

    with get_db_connection() as (conn, c):
        sql = _safe_adapt_sql(
            "SELECT id, username, role, user_type, "
            "remaining_calculations FROM users WHERE id = %s",
            conn,
        )
        c.execute(sql, (user_id,))
        row = c.fetchone()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户不存在",
            )
        return {
            "id": row[0],
            "username": row[1],
            "role": row[2],
            "user_type": row[3],
            "remaining_calculations": row[4],
        }


def _resolve_user_id(token: str) -> int:
    """JWT → user_id，失败则回退到旧模式（token=用户名查DB）。"""
    try:
        return get_user_id_from_token(token)
    except (TokenExpiredError, TokenInvalidError):
        pass

    with get_db_connection() as (conn, c):
        sql = _safe_adapt_sql("SELECT id FROM users WHERE username = %s", conn)
        c.execute(sql, (token,))
        row = c.fetchone()
        if row:
            return row[0]

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效的认证凭证",
    )


def require_admin(
    api_key=Depends(security),
) -> int:
    """要求管理员权限。401=未认证，403=非管理员。"""
    token = api_key.credentials
    user_id = _resolve_user_id(token)

    with get_db_connection() as (conn, c):
        sql = _safe_adapt_sql("SELECT role FROM users WHERE id = %s", conn)
        c.execute(sql, (user_id,))
        row = c.fetchone()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户不存在",
            )
        if row[0] != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="需要管理员权限",
            )
    return user_id
