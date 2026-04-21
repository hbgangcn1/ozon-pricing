import logging
import secrets
import string
import time
from datetime import date, timedelta
from typing import Optional

import bcrypt
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from db import admin_helpers
from db.logging_utils import log_admin_action
from models.log import AuditLog
from models.logistics import Logistics
from models.product import Product
from models.user import User

logger = logging.getLogger(__name__)

build_users_filter = getattr(admin_helpers, "_build_users_filter")
format_audit_log_rows = getattr(admin_helpers, "_format_audit_log_rows")
format_user_row = getattr(admin_helpers, "_format_user_row")
subscription_expires_to_datetime = getattr(
    admin_helpers,
    "_subscription_expires_to_datetime",
)

_ALLOWED_SUBSCRIPTION_FIELDS = {
    "user_type",
    "subscription_start",
    "remaining_calculations",
    "logistics_templates_limit",
    "is_auto_renew",
    "is_frozen",
}


async def authenticate_admin(
    session: AsyncSession,
    username,
    password,
) -> Optional[dict]:
    stmt = select(User).where(
        User.username == username,
        User.role == "admin",
    )
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        return None

    stored = user.password or ""
    try:
        if not bcrypt.checkpw(password.encode("utf-8"), stored.encode("utf-8")):
            return None
    except (ValueError, TypeError):
        return None

    user.last_login = str(int(time.time()))
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "email": user.email,
    }


async def get_all_users(
    session: AsyncSession,
    page=1,
    per_page=20,
    search=None,
    user_type_filter=None,
    status_filter=None,
) -> dict:
    conditions = build_users_filter(search, user_type_filter, status_filter)
    base = select(User)
    for cond in conditions:
        base = base.where(cond)

    count_stmt = select(func.count()).select_from(base.subquery())
    total_count = await session.scalar(count_stmt) or 0

    offset = (page - 1) * per_page
    query = base.order_by(User.id.asc()).limit(per_page).offset(offset)
    result = await session.execute(query)
    users = result.scalars().all()

    user_logistics_counts = await get_logistics_counts_for_users(
        session,
        [user.id for user in users],
    )

    formatted = [format_user_row(u, user_logistics_counts) for u in users]
    return {
        "users": formatted,
        "total_count": total_count,
        "total_pages": (total_count + per_page - 1) // per_page,
        "current_page": page,
    }


async def get_logistics_counts_for_users(
    session: AsyncSession,
    user_ids: list[int],
) -> dict[int, int]:
    if not user_ids:
        return {}
    result = await session.execute(
        select(Logistics.user_id, func.count(Logistics.id))
        .where(Logistics.user_id.in_(user_ids))
        .group_by(Logistics.user_id)
    )
    return {user_id: count for user_id, count in result.all()}


async def get_user_detail(
    session: AsyncSession,
    user_id,
) -> Optional[dict]:
    user = await session.get(User, user_id)
    if not user:
        return None

    logistics_count = (
        await session.scalar(
            select(func.count(Logistics.id)).where(Logistics.user_id == user_id)
        )
        or 0
    )
    products_count = (
        await session.scalar(
            select(func.count(Product.id)).where(Product.user_id == user_id)
        )
        or 0
    )

    remaining_days = None
    subscription_end_iso = None
    expiry_dt = subscription_expires_to_datetime(user.subscription_expires)
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
        "current_logistics_count": logistics_count,
        "products_count": products_count,
        "is_auto_renew": user.is_auto_renew,
        "created_at": user.created_at,
        "last_login": user.last_login,
        "is_frozen": user.is_frozen,
    }


async def update_user_subscription_admin(
    session: AsyncSession,
    user_id,
    updates: dict,
    admin_id,
) -> bool:
    user = await session.get(User, user_id)
    if not user:
        return False

    changed = False
    for field, value in updates.items():
        if field == "subscription_end":
            expiry_dt = subscription_expires_to_datetime(value)
            if expiry_dt is not None:
                user.subscription_expires = int(expiry_dt.timestamp())
                changed = True
        elif field in _ALLOWED_SUBSCRIPTION_FIELDS:
            setattr(user, field, value)
            changed = True

    if not changed:
        return False

    details_pairs = [f"{k}={v}" for k, v in updates.items()]
    action_details = "管理员更新用户订阅: " + ", ".join(details_pairs)
    audit = AuditLog(
        admin_id=admin_id,
        user_id=user_id,
        action="update_subscription",
        details=action_details,
    )
    session.add(audit)
    await log_admin_action(
        session=session,
        admin_id=admin_id,
        action_type="更新订阅",
        action_detail=action_details,
        target_user_id=user_id,
        target_type="subscription",
    )
    return True


async def freeze_user(
    session: AsyncSession,
    user_id,
    admin_id,
) -> bool:
    user = await session.get(User, user_id)
    if not user:
        return False
    user.is_frozen = 1
    audit = AuditLog(
        admin_id=admin_id,
        user_id=user_id,
        action="freeze_user",
        details="管理员冻结用户",
    )
    session.add(audit)
    await log_admin_action(
        session=session,
        admin_id=admin_id,
        action_type="冻结用户",
        action_detail=f"管理员冻结了用户ID: {user_id}",
        target_user_id=user_id,
        target_type="user",
    )
    return True


async def unfreeze_user(
    session: AsyncSession,
    user_id,
    admin_id,
) -> bool:
    user = await session.get(User, user_id)
    if not user:
        return False
    user.is_frozen = 0
    audit = AuditLog(
        admin_id=admin_id,
        user_id=user_id,
        action="unfreeze_user",
        details="管理员解冻用户",
    )
    session.add(audit)
    await log_admin_action(
        session=session,
        admin_id=admin_id,
        action_type="解冻用户",
        action_detail=f"管理员解冻了用户ID: {user_id}",
        target_user_id=user_id,
        target_type="user",
    )
    return True


async def delete_user_admin(
    session: AsyncSession,
    user_id,
    admin_id,
) -> bool:
    user = await session.get(User, user_id)
    if not user:
        return False
    if user.role == "admin":
        logger.info("删除失败: 不允许删除管理员账号及其数据")
        return False

    username = user.username or f"ID:{user_id}"
    from db.users import delete_user

    deleted = await delete_user(session, user_id)
    if not deleted:
        return False

    await log_admin_action(
        session=session,
        admin_id=admin_id,
        action_type="删除用户",
        action_detail=f"管理员删除了用户: {username} (ID: {user_id})",
        target_user_id=None,
        target_type="user",
    )
    return True


async def batch_update_users(
    session: AsyncSession,
    user_ids: list,
    updates: dict,
    admin_id,
) -> int:
    success_count = 0
    for uid in user_ids:
        user = await session.get(User, uid)
        if not user:
            continue
        changed = False
        for field, value in updates.items():
            if field == "subscription_end":
                expiry_dt = subscription_expires_to_datetime(value)
                if expiry_dt is not None:
                    user.subscription_expires = int(expiry_dt.timestamp())
                    changed = True
            elif field in _ALLOWED_SUBSCRIPTION_FIELDS:
                setattr(user, field, value)
                changed = True
        if changed:
            success_count += 1
            details_pairs = [f"{k}={v}" for k, v in updates.items()]
            action_details = "批量更新: " + ", ".join(details_pairs)
            audit = AuditLog(
                admin_id=admin_id,
                user_id=uid,
                action="batch_update",
                details=action_details,
            )
            session.add(audit)
    return success_count


async def get_audit_logs(
    session: AsyncSession,
    page=1,
    per_page=50,
    admin_id=None,
    user_id=None,
    action=None,
) -> dict:
    AdminUser = aliased(User, name="admin_user")
    TargetUser = aliased(User, name="target_user")

    stmt = (
        select(
            AuditLog,
            AdminUser.username.label("admin_username"),
            TargetUser.username.label("user_username"),
        )
        .outerjoin(
            AdminUser,
            (AuditLog.admin_id == AdminUser.id) & (AdminUser.role == "admin"),
        )
        .outerjoin(TargetUser, AuditLog.user_id == TargetUser.id)
    )

    conditions = []
    if admin_id:
        conditions.append(AuditLog.admin_id == admin_id)
    if user_id:
        conditions.append(AuditLog.user_id == user_id)
    if action:
        conditions.append(AuditLog.action == action)
    for cond in conditions:
        stmt = stmt.where(cond)

    count_base = select(func.count(AuditLog.id))
    for cond in conditions:
        count_base = count_base.where(cond)
    total_count = await session.scalar(count_base) or 0

    offset = (page - 1) * per_page
    stmt = stmt.order_by(AuditLog.timestamp.desc()).limit(per_page).offset(offset)
    result = await session.execute(stmt)
    rows = result.all()

    formatted = format_audit_log_rows(rows)
    return {
        "logs": formatted,
        "total_count": total_count,
        "total_pages": (total_count + per_page - 1) // per_page,
        "current_page": page,
    }


async def reset_user_password(
    session: AsyncSession,
    user_id,
    admin_id,
) -> Optional[str]:
    user = await session.get(User, user_id)
    if not user:
        return None

    alphabet = string.ascii_letters + string.digits
    new_password = "".join(secrets.choice(alphabet) for _ in range(12))
    password_hash = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt())
    user.password = password_hash.decode("utf-8")

    details_text = "管理员重置了用户密码"
    audit = AuditLog(
        admin_id=admin_id,
        user_id=user_id,
        action="reset_password",
        details=details_text,
    )
    session.add(audit)
    await log_admin_action(
        session=session,
        admin_id=admin_id,
        action_type="重置密码",
        action_detail=f"管理员重置了用户ID: {user_id} 的密码",
        target_user_id=user_id,
        target_type="user",
    )
    return new_password


_ALLOWED_USER_TYPES = {
    "free",
    "efficiency",
    "professional",
    "enterprise",
    "test",
    "thanks",
}


async def extend_subscription(
    session: AsyncSession,
    user_id,
    days: int,
) -> bool:
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        logger.warning("extend_subscription failed: user %s not found", user_id)
        return False

    today = date.today()
    expires_at = subscription_expires_to_datetime(user.subscription_expires)
    base_date = today
    if expires_at is not None and expires_at.date() >= today:
        base_date = expires_at.date()

    new_expiry = base_date + timedelta(days=days)
    user.subscription_expires = int(time.mktime(new_expiry.timetuple()))
    await session.flush()
    return True


async def adjust_calculations(
    session: AsyncSession,
    user_id,
    delta: int,
) -> bool:
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        logger.warning("adjust_calculations failed: user %s not found", user_id)
        return False

    current = user.remaining_calculations or 0
    user.remaining_calculations = max(0, current + delta)
    await session.flush()
    return True


async def set_user_type(
    session: AsyncSession,
    user_id,
    user_type: str,
) -> bool:
    if user_type not in _ALLOWED_USER_TYPES:
        logger.warning("set_user_type failed: invalid user_type %s", user_type)
        return False

    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        logger.warning("set_user_type failed: user %s not found", user_id)
        return False

    user.user_type = user_type
    await session.flush()
    return True
