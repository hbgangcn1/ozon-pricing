import logging
from dataclasses import dataclass
from typing import Literal, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from db import subscription_quota as _quota
from models.user import User
from models.logistics import Logistics
from db.plans import get_plan_by_code
# overflow_service imported lazily in apply_subscription_change to break
# db <-> services circular import (services/__init__ imports payment_service
# which imports db.subscriptions).

logger = logging.getLogger(__name__)

_check_enterprise_status = _quota.check_enterprise_status
_check_monthly_status = _quota.check_monthly_status
_check_new_tier_free = _quota.check_new_tier_free
_check_new_tier_status = _quota.check_new_tier_status
_check_test_status = _quota.check_test_status
_get_days_remaining_from_info = _quota.get_days_remaining_from_info
_parse_expiry_date = _quota.parse_expiry_date
decrement_user_calculations = _quota.decrement_user_calculations
reset_free_users_daily_calculations = _quota.reset_free_users_daily_calculations
reset_user_daily_calculations = _quota.reset_user_daily_calculations

__all__ = [
    "ChangeAction",
    "ChangeResult",
    "apply_paid_subscription",
    "apply_subscription_change",
    "check_user_subscription_status",
    "decrement_user_calculations",
    "get_user_subscription_info",
    "reset_free_users_daily_calculations",
    "reset_user_daily_calculations",
    "update_user_subscription",
    "_check_enterprise_status",
    "_check_monthly_status",
    "_check_new_tier_free",
    "_check_test_status",
    "_get_days_remaining_from_info",
    "_parse_expiry_date",
]


# --- apply_subscription_change ------------------------------------------------
#
# SINGLE source of truth for mutating users.subscription_type. All payment
# success paths, admin grants, and downgrades MUST funnel here so trial-overflow
# bookkeeping (auto-trim on downgrade, restore on upgrade, window close) stays
# consistent. Direct `user.subscription_type = X` writes elsewhere are forbidden
# (enforced by code review + grep).

ChangeAction = Literal["noop", "upgraded", "downgraded", "same_tier"]


@dataclass
class ChangeResult:
    action: ChangeAction
    old_plan: str
    new_plan: str
    new_limit: int
    active_count: int
    restored_count: int = 0
    trimmed_count: int = 0
    window_id: int = 0


# Hardcoded fallback (mirrors plan_resolution._FALLBACK_LIMITS) for tests that
# don't seed Plan rows. Kept private; production hits real plans table.
_FALLBACK_LIMITS = {
    "free": 1,
    "efficiency": 3,
    "professional": 10,
    "enterprise": -1,
    "gratitude": -1,
}


async def _resolve_plan_limit(session: AsyncSession, plan_code: str) -> int:
    plan = await get_plan_by_code(session, plan_code)
    if plan and plan.get("logistics_limit") is not None:
        return int(plan["logistics_limit"])
    return _FALLBACK_LIMITS.get(plan_code, 1)


async def _count_active_rules(session: AsyncSession, user_id: int) -> int:
    stmt = (
        select(func.count())
        .select_from(Logistics)
        .where(
            Logistics.user_id == user_id,
            Logistics.is_active == 1,
            Logistics.disabled_by_overflow == 0,
        )
    )
    return int((await session.execute(stmt)).scalar_one() or 0)


async def _apply_noop_change(
    session: AsyncSession,
    user: User,
    user_id: int,
    old_plan: str,
    new_plan_norm: str,
    billing_cycle: Optional[str],
    subscription_expires: Optional[int],
    source: str,
) -> ChangeResult:
    if billing_cycle is not None:
        user.billing_cycle = billing_cycle
    if subscription_expires is not None:
        user.subscription_expires = subscription_expires
    active_count = await _count_active_rules(session, user_id)
    new_limit = await _resolve_plan_limit(session, new_plan_norm)
    logger.info(
        "subscription_change noop: user=%d plan=%s source=%s",
        user_id, new_plan_norm, source,
    )
    return ChangeResult(
        action="noop",
        old_plan=old_plan,
        new_plan=new_plan_norm,
        new_limit=new_limit,
        active_count=active_count,
    )


async def _apply_upgrade_change(
    session: AsyncSession,
    user_id: int,
    old_plan: str,
    new_plan_norm: str,
    new_limit: int,
    active_count: int,
    source: str,
) -> ChangeResult:
    from services import overflow_service
    restored = await overflow_service.restore_all_overflow(
        session, user_id, reason="upgraded",
    )
    logger.info(
        "subscription_change upgrade: user=%d %s→%s restored=%d source=%s",
        user_id, old_plan, new_plan_norm, restored, source,
    )
    return ChangeResult(
        action="upgraded",
        old_plan=old_plan,
        new_plan=new_plan_norm,
        new_limit=new_limit,
        active_count=active_count,
        restored_count=restored,
    )


async def _apply_downgrade_change(
    session: AsyncSession,
    user_id: int,
    old_plan: str,
    new_plan_norm: str,
    new_limit: int,
    active_count: int,
    source: str,
) -> ChangeResult:
    from services import overflow_service
    trim = await overflow_service.auto_trim_user_rules(
        session, user_id, new_limit,
    )
    logger.info(
        "subscription_change downgrade: user=%d %s→%s trimmed=%d "
        "window=%d source=%s",
        user_id, old_plan, new_plan_norm, trim.trimmed_count,
        trim.window_id, source,
    )
    return ChangeResult(
        action="downgraded",
        old_plan=old_plan,
        new_plan=new_plan_norm,
        new_limit=new_limit,
        active_count=active_count,
        trimmed_count=trim.trimmed_count,
        window_id=trim.window_id,
    )


async def apply_subscription_change(
    session: AsyncSession,
    user_id: int,
    new_plan: str,
    *,
    billing_cycle: Optional[str] = None,
    subscription_expires: Optional[int] = None,
    source: str = "unknown",
) -> ChangeResult:
    """ONLY allowed entry point for writing users.subscription_type.

    Steps (caller commits): noop / upgrade (restore_all_overflow) /
    downgrade (auto_trim) / same_tier. `source` is for audit logs.
    """
    user = await session.get(User, user_id)
    if user is None:
        raise ValueError(f"user not found: id={user_id}")

    old_plan = (user.subscription_type or "free").strip() or "free"
    new_plan_norm = (new_plan or "free").strip() or "free"

    if old_plan == new_plan_norm:
        return await _apply_noop_change(
            session, user, user_id, old_plan, new_plan_norm,
            billing_cycle, subscription_expires, source,
        )

    user.subscription_type = new_plan_norm
    if billing_cycle is not None:
        user.billing_cycle = billing_cycle
    if subscription_expires is not None:
        user.subscription_expires = subscription_expires

    new_limit = await _resolve_plan_limit(session, new_plan_norm)
    active_count = await _count_active_rules(session, user_id)

    is_upgrade = (
        new_plan_norm in ("professional", "enterprise", "gratitude")
        or new_limit == -1
        or new_limit > active_count
    )

    if is_upgrade:
        return await _apply_upgrade_change(
            session, user_id, old_plan, new_plan_norm,
            new_limit, active_count, source,
        )

    if new_limit > 0 and active_count > new_limit:
        return await _apply_downgrade_change(
            session, user_id, old_plan, new_plan_norm,
            new_limit, active_count, source,
        )

    logger.info(
        "subscription_change same_tier: user=%d %s→%s source=%s",
        user_id, old_plan, new_plan_norm, source,
    )
    return ChangeResult(
        action="same_tier",
        old_plan=old_plan,
        new_plan=new_plan_norm,
        new_limit=new_limit,
        active_count=active_count,
    )


async def get_user_subscription_info(
    session: AsyncSession,
    user_id,
) -> Optional[dict]:
    user = await session.get(User, user_id)
    if not user:
        return None
    return {
        "id": user.id,
        "username": user.username,
        "user_type": user.user_type,
        "expiry_date": user.expiry_date,
        "remaining_calculations": user.remaining_calculations,
        "first_login_date": user.first_login_date,
        "test_days_remaining": user.test_days_remaining,
        "role": user.role,
        "subscription_type": user.subscription_type,
        "subscription_expires": user.subscription_expires,
    }


async def update_user_subscription(
    session: AsyncSession,
    user_id,
    updates: dict,
) -> bool:
    user = await session.get(User, user_id)
    if not user:
        return False
    for field, value in updates.items():
        if hasattr(user, field):
            setattr(user, field, value)
    return True


async def check_user_subscription_status(
    session: AsyncSession,
    user_id,
) -> dict:
    user_info = await get_user_subscription_info(session, user_id)
    if not user_info:
        return {"valid": False, "message": "用户不存在"}

    user_role = user_info.get("role", "user")
    if user_role == "admin":
        return {
            "valid": True,
            "message": "管理员用户",
            "user_type": "admin",
            "role": "admin",
        }

    user_type = user_info.get("subscription_type") or user_info.get(
        "user_type", "permanent"
    )

    if user_type == "permanent":
        return {"valid": True, "message": "永久用户", "user_type": user_type}

    if user_type == "test":
        return _check_test_status(user_info, user_type)

    if user_type == "monthly":
        return _check_monthly_status(user_info, user_type)

    if user_type == "enterprise":
        return _check_enterprise_status(user_info, user_type)

    if user_type in [
        "free",
        "efficiency",
        "professional",
        "enterprise",
        "gratitude",
    ]:
        return await _check_new_tier_status(session, user_info, user_type, user_id)

    return {"valid": False, "message": "未知用户类型", "user_type": user_type}


# --- apply_paid_subscription --------------------------------------------------
#
# Single funnel for ALL paid (WeChat + legacy) subscription activations.
# Wraps apply_subscription_change and centralises the paid-only side effects:
# user_type / subscription_start / remaining_calculations. Direct writes to
# these three fields outside this helper are forbidden in payment paths so a
# future refactor of activation semantics only needs to touch one place.

async def apply_paid_subscription(
    session: AsyncSession,
    user_id: int,
    plan_code: str,
    *,
    subscription_expires: int,
    started_at: int,
    source: str,
    billing_cycle: Optional[str] = None,
) -> ChangeResult:
    result = await apply_subscription_change(
        session,
        user_id,
        plan_code,
        billing_cycle=billing_cycle,
        subscription_expires=subscription_expires,
        source=source,
    )
    user = await session.get(User, user_id)
    if user is not None:
        user.user_type = plan_code
        user.subscription_start = started_at
        user.remaining_calculations = -1
    return result
