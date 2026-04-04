"""Internal admin helper functions — not part of public API."""

import time
from datetime import date

from db._proxy import _db

__all__ = [
    "_build_users_filter",
    "_get_users_query",
    "_format_user_row",
]


def _build_users_filter(search, user_type_filter, status_filter):
    """构建用户列表过滤条件"""
    from sql_security import build_where_clause

    where_conditions = []
    params = []

    if search:
        where_conditions.append("(username LIKE ? OR email LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])

    if user_type_filter and user_type_filter != "all":
        where_conditions.append("user_type = ?")
        params.append(user_type_filter)

    if status_filter:
        current_ts = int(time.time())
        if status_filter == "expired":
            where_conditions.append(
                "(subscription_expires IS NOT NULL AND subscription_expires < ?)"
            )
            params.append(current_ts)
        elif status_filter == "expiring_soon":
            where_conditions.append(
                "(subscription_expires IS NOT NULL"
                " AND subscription_expires BETWEEN ? AND ?)"
            )
            params.extend([current_ts, current_ts + 7 * 24 * 3600])
        elif status_filter == "active":
            where_conditions.append(
                "(subscription_expires IS NULL OR subscription_expires >= ?)"
            )
            params.append(current_ts)

    return build_where_clause(where_conditions, params)


def _get_users_query(where_clause, has_logistics_limit):
    """构建用户列表查询SQL"""
    if has_logistics_limit:
        return f"""
        SELECT id, username, email, role, user_type,
               subscription_start, subscription_expires,
               remaining_calculations, logistics_templates_limit,
               is_auto_renew, created_at, last_login, is_frozen
        FROM users
        WHERE {where_clause}
        ORDER BY created_at DESC, id DESC
        LIMIT ? OFFSET ?
        """
    return f"""
    SELECT id, username, email, role, user_type,
           subscription_start, subscription_expires,
           remaining_calculations, -1,
           is_auto_renew, created_at, last_login, is_frozen
    FROM users
    WHERE {where_clause}
    ORDER BY created_at DESC, id DESC
    LIMIT ? OFFSET ?
    """


def _format_user_row(user, user_logistics_counts):
    """格式化单行用户数据"""
    (
        user_id,
        username,
        email,
        role,
        user_type,
        subscription_start,
        subscription_expires_raw,
        remaining_calculations,
        logistics_templates_limit,
        is_auto_renew,
        created_at,
        last_login,
        is_frozen,
    ) = user

    remaining_days = None
    subscription_end_iso = None
    expiry_dt = _db._subscription_expires_to_datetime(subscription_expires_raw)
    if expiry_dt is not None:
        subscription_end_iso = expiry_dt.isoformat()
        today = date.today()
        remaining_days = (expiry_dt.date() - today).days

    return {
        "id": user_id,
        "username": username,
        "email": email,
        "role": role,
        "user_type": user_type,
        "subscription_start": subscription_start,
        "subscription_end": subscription_end_iso,
        "remaining_days": remaining_days,
        "remaining_calculations": remaining_calculations,
        "logistics_templates_limit": logistics_templates_limit,
        "current_logistics_count": user_logistics_counts.get(user_id, 0),
        "is_auto_renew": is_auto_renew,
        "created_at": created_at,
        "last_login": last_login,
        "is_frozen": is_frozen,
    }


def _get_all_users_rows(c, conn, safe_params, per_page, offset, where_clause):
    """获取用户列表行数据"""
    cols = _db._get_table_columns(c, "users")
    has_logistics_limit = "logistics_templates_limit" in cols

    query = _db._safe_adapt_sql(
        _get_users_query(where_clause, has_logistics_limit), conn
    )
    c.execute(query, safe_params + [per_page, offset])
    return c.fetchall()


def _format_audit_log_rows(logs):
    formatted = []
    for log in logs:
        (log_id, a_id, u_id, act, details, ts, admin_uname, user_uname) = log
        formatted.append(
            {
                "id": log_id,
                "admin_id": a_id,
                "user_id": u_id,
                "action": act,
                "details": details,
                "timestamp": ts,
                "admin_username": admin_uname,
                "user_username": user_uname,
            }
        )
    return formatted
