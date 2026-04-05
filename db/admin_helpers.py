import time
from datetime import date, datetime
from typing import Optional

from models.user import User

__all__ = [
    "_build_users_filter",
    "_format_user_row",
    "_format_audit_log_rows",
    "_subscription_expires_to_datetime",
]


def _subscription_expires_to_datetime(value) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(int(value))
        except (OSError, OverflowError, ValueError):
            return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            pass
        try:
            return datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            return None
    return None


def _build_users_filter(search, user_type_filter, status_filter):
    conditions = []

    if search:
        pattern = f"%{search}%"
        conditions.append(User.username.ilike(pattern) | User.email.ilike(pattern))

    if user_type_filter and user_type_filter != "all":
        conditions.append(User.user_type == user_type_filter)

    if status_filter:
        current_ts = int(time.time())
        if status_filter == "expired":
            conditions.append(
                User.subscription_expires.isnot(None)
                & (User.subscription_expires < current_ts)
            )
        elif status_filter == "expiring_soon":
            conditions.append(
                User.subscription_expires.isnot(None)
                & (User.subscription_expires >= current_ts)
                & (User.subscription_expires <= current_ts + 7 * 24 * 3600)
            )
        elif status_filter == "active":
            conditions.append(
                User.subscription_expires.is_(None)
                | (User.subscription_expires >= current_ts)
            )

    return conditions


def _format_user_row(user: User, user_logistics_counts: dict) -> dict:
    remaining_days = None
    subscription_end_iso = None
    expiry_dt = _subscription_expires_to_datetime(user.subscription_expires)
    if expiry_dt is not None:
        subscription_end_iso = expiry_dt.isoformat()
        today = date.today()
        remaining_days = (expiry_dt.date() - today).days

    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "user_type": user.user_type,
        "subscription_start": user.subscription_start,
        "subscription_end": subscription_end_iso,
        "remaining_days": remaining_days,
        "remaining_calculations": user.remaining_calculations,
        "logistics_templates_limit": user.logistics_templates_limit,
        "current_logistics_count": user_logistics_counts.get(user.id, 0),
        "is_auto_renew": user.is_auto_renew,
        "created_at": user.created_at,
        "last_login": user.last_login,
        "is_frozen": user.is_frozen,
    }


def _format_audit_log_rows(rows) -> list:
    formatted = []
    for row in rows:
        formatted.append(
            {
                "id": row.id,
                "admin_id": row.admin_id,
                "user_id": row.user_id,
                "action": row.action,
                "details": row.details,
                "timestamp": row.timestamp,
                "admin_username": getattr(row, "admin_username", None),
                "user_username": getattr(row, "user_username", None),
            }
        )
    return formatted
