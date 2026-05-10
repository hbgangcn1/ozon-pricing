import math
import logging
import time
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal, Optional

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User
from models.logistics import Logistics
from db.plans import get_plan_by_code
# overflow_service imported lazily in apply_subscription_change to break
# db <-> services circular import (services/__init__ imports payment_service
# which imports db.subscriptions).

logger = logging.getLogger(__name__)


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

    Transactional steps (caller commits):
      1. Load user (404 → ValueError).
      2. Read old plan code.
      3. Same plan + same expires → idempotent noop (still updates billing_cycle
         if provided; does NOT touch subscription_expires unless given).
      4. Write subscription_type / billing_cycle / subscription_expires.
      5. Resolve new plan's logistics_limit.
      6. UPGRADE branch: new plan in {professional, enterprise} OR new_limit==-1
         OR new_limit > old active_count → restore_all_overflow(reason='upgraded').
      7. DOWNGRADE branch: new_limit > 0 AND new_limit < active_count
         → auto_trim_user_rules(user_id, new_limit).
      8. Otherwise: same_tier (e.g. monthly→yearly free).

    `source` is for audit logging only (e.g. 'wechat_pay', 'admin_grant').
    Returns ChangeResult with audit fields. Caller commits.
    """
    from services import overflow_service  # lazy: see module-level note
    user = await session.get(User, user_id)
    if user is None:
        raise ValueError(f"user not found: id={user_id}")

    old_plan = (user.subscription_type or "free").strip() or "free"
    new_plan_norm = (new_plan or "free").strip() or "free"

    # Idempotent same-plan path: still allow billing_cycle / expires refresh
    # (e.g. renewal of same tier extends expiry without overflow recompute).
    if old_plan == new_plan_norm:
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

    if new_limit > 0 and active_count > new_limit:
        trim = await overflow_service.auto_trim_user_rules(
            session, user_id, new_limit,
        )
        logger.info(
            "subscription_change downgrade: user=%d %s→%s trimmed=%d window=%d source=%s",
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


async def decrement_user_calculations(
    session: AsyncSession,
    user_id,
) -> bool:
    try:
        await session.flush()
        user = await session.get(User, user_id)
        if not user:
            return False
        user_role = getattr(user, "role", None)
        if user_role == "admin":
            return True
        user_type_raw = getattr(user, "subscription_type", None) or getattr(user, "user_type", None) or ""
        if not isinstance(user_type_raw, str):
            return True
        user_type = user_type_raw.strip()
    except Exception:
        logger.warning("获取用户信息失败，跳过计算次数扣减", exc_info=True)
        return True

    if user_type in [
        "admin",
        "permanent",
        "enterprise",
        "gratitude",
        "efficiency",
        "professional",
        "test",
    ]:
        return True

    if user_type in ("free", "monthly"):
        try:
            result = await session.execute(
                update(User)
                .where(User.id == user_id, User.remaining_calculations > 0)
                .values(remaining_calculations=User.remaining_calculations - 1)
                .execution_options(synchronize_session=False)
            )
            rowcount = int(getattr(result, "rowcount", 0) or 0)
            if rowcount == 0:
                return False
            await session.flush()
            return True
        except Exception:
            logger.warning("扣减计算次数失败", exc_info=True)
            return True

    return False


async def reset_free_users_daily_calculations(
    session: AsyncSession,
) -> int:
    try:
        result = await session.execute(
            update(User)
            .where(User.user_type == "free")
            .values(remaining_calculations=10)
        )
        return int(getattr(result, "rowcount", 0) or 0)
    except Exception:
        logger.warning("重置免费用户每日计算次数失败", exc_info=True)
        return 0


async def reset_user_daily_calculations(
    session: AsyncSession,
    user_id: int,
) -> bool:
    """
    每日重置检查：
    - 如果用户套餐的 calc_limit == -1（无限），不处理
    - 如果今天已经重置过，不处理
    - 否则重置 remaining_calculations = calc_limit，并更新 last_calculations_reset_date
    """
    try:
        user = await session.get(User, user_id)
        if not user:
            return False

        plan = await get_plan_by_code(session, user.subscription_type or "free")
        if not plan:
            return False

        calc_limit = plan.get("calc_limit", -1)
        if calc_limit == -1:
            return False

        today = date.today().isoformat()
        if user.last_calculations_reset_date == today:
            return False

        user.remaining_calculations = calc_limit
        user.last_calculations_reset_date = today
        await session.commit()
        return True
    except Exception:
        logger.warning("重置用户每日计算次数失败", exc_info=True)
        return False


def _check_test_status(user_info, user_type):
    first_login = user_info.get("first_login_date")
    if not first_login:
        return {
            "valid": True,
            "message": "测试用户未开始计时",
            "user_type": user_type,
        }
    try:
        first_login_date = datetime.fromisoformat(first_login)
        days_elapsed = (datetime.now() - first_login_date).days
        remaining_days = 7 - days_elapsed
        if remaining_days <= 0:
            return {
                "valid": False,
                "message": "测试期已过期",
                "user_type": user_type,
            }
        return {
            "valid": True,
            "message": f"测试用户，剩余{remaining_days}天",
            "remaining_days": remaining_days,
            "user_type": user_type,
        }
    except (ValueError, TypeError):
        return {"valid": True, "message": "测试用户", "user_type": user_type}


def _parse_expiry_date(expiry_date):
    if isinstance(expiry_date, datetime):
        return expiry_date
    if isinstance(expiry_date, date):
        return datetime.combine(expiry_date, datetime.min.time())
    if isinstance(expiry_date, str):
        if "T" in expiry_date:
            return datetime.fromisoformat(expiry_date.replace("Z", "+00:00"))
        try:
            return datetime.strptime(expiry_date, "%Y-%m-%d")
        except ValueError:
            return datetime.fromisoformat(expiry_date)
    raise ValueError(f"不支持的日期类型: {type(expiry_date)}")


def _check_monthly_status(user_info, user_type):
    expiry_date = user_info.get("expiry_date")
    remaining_calculations = user_info.get("remaining_calculations", 0)
    if not expiry_date:
        return {"valid": False, "message": "订阅信息不完整"}
    try:
        expiry = _parse_expiry_date(expiry_date)
        today = date.today()
        days_remaining = (expiry.date() - today).days
        if days_remaining <= 0:
            return {
                "valid": False,
                "message": "订阅已过期",
                "remaining_days": 0,
                "remaining_calculations": remaining_calculations,
                "user_type": user_type,
            }
        if remaining_calculations == -1:
            calculations_display = "无限次"
        else:
            calculations_display = f"{remaining_calculations}次"
        return {
            "valid": True,
            "message": (
                f"按月付费用户，剩余{days_remaining}天，剩余{calculations_display}计算"
            ),
            "remaining_days": days_remaining,
            "remaining_calculations": remaining_calculations,
            "user_type": user_type,
        }
    except (ValueError, TypeError):
        return {
            "valid": False,
            "message": "订阅信息错误",
            "user_type": user_type,
        }


def _check_enterprise_status(user_info, user_type):
    expiry_date = user_info.get("expiry_date")
    if not expiry_date:
        return {
            "valid": False,
            "message": "订阅信息不完整",
            "user_type": user_type,
        }
    try:
        expiry = _parse_expiry_date(expiry_date)
        today = date.today()
        days_remaining = (expiry.date() - today).days
        if days_remaining <= 0:
            return {
                "valid": False,
                "message": "订阅已过期",
                "remaining_days": 0,
                "user_type": user_type,
            }
        return {
            "valid": True,
            "message": f"企业版用户，剩余{days_remaining}天",
            "remaining_days": days_remaining,
            "user_type": user_type,
        }
    except (ValueError, TypeError):
        return {
            "valid": False,
            "message": "订阅信息错误",
            "user_type": user_type,
        }


async def _check_new_tier_free(
    session: AsyncSession,
    user_info,
    user_type,
    user_id,
):
    remaining_calculations = user_info.get("remaining_calculations", 0)
    if remaining_calculations == -1:
        try:
            await session.execute(
                update(User).where(User.id == user_id).values(remaining_calculations=10)
            )
        except Exception:
            logger.debug("更新新套餐免费用户计算次数失败", exc_info=True)
        remaining_calculations = 10
    calculations_display = f"{remaining_calculations}次"
    return {
        "valid": True,
        "message": f"免费版用户，剩余{calculations_display}计算",
        "remaining_calculations": remaining_calculations,
        "user_type": user_type,
    }


def _get_days_remaining_from_info(user_info, user_type):
    subscription_expires = user_info.get("subscription_expires")
    expiry_date = user_info.get("expiry_date")
    remaining_calculations = user_info.get("remaining_calculations", 0)

    if subscription_expires:
        current_time = int(time.time())
        subscription_expires = int(subscription_expires)
        days_remaining = math.ceil((subscription_expires - current_time) / (24 * 3600))
        return days_remaining, remaining_calculations, None
    if expiry_date:
        try:
            expiry = datetime.fromisoformat(expiry_date)
            today = date.today()
            days_remaining = (expiry.date() - today).days
            return days_remaining, remaining_calculations, None
        except (ValueError, TypeError):
            return (
                None,
                remaining_calculations,
                {
                    "valid": False,
                    "message": "订阅信息错误",
                    "user_type": user_type,
                },
            )
    return (
        None,
        remaining_calculations,
        {
            "valid": False,
            "message": "订阅信息不完整",
            "user_type": user_type,
        },
    )


async def _check_new_tier_status(
    session: AsyncSession,
    user_info,
    user_type,
    user_id,
):
    if user_type == "free":
        return await _check_new_tier_free(session, user_info, user_type, user_id)
    if user_type == "gratitude":
        return {
            "valid": True,
            "message": "感谢版用户，永久有效",
            "remaining_days": -1,
            "remaining_calculations": -1,
            "user_type": user_type,
        }

    days_remaining, remaining_calculations, err = _get_days_remaining_from_info(
        user_info, user_type
    )
    if err is not None:
        return err

    try:
        if days_remaining <= 0:
            return {
                "valid": False,
                "message": "订阅到期，请续订",
                "remaining_days": 0,
                "remaining_calculations": remaining_calculations,
                "user_type": user_type,
            }
        user_type_display_names = {
            "free": "免费版用户",
            "efficiency": "效率版用户",
            "professional": "专业版用户",
            "enterprise": "企业版用户",
            "gratitude": "感谢版用户",
        }
        display_name = user_type_display_names.get(user_type, f"{user_type}用户")
        if user_type == "free":
            if remaining_calculations == -1:
                calculations_display = "无限次"
            else:
                calculations_display = f"{remaining_calculations}次"
            message = (
                f"{display_name}，剩余{days_remaining}天，"
                f"剩余{calculations_display}计算"
            )
        else:
            message = f"{display_name}，剩余{days_remaining}天"
        return {
            "valid": True,
            "message": message,
            "remaining_days": days_remaining,
            "remaining_calculations": remaining_calculations,
            "user_type": user_type,
        }
    except (ValueError, TypeError):
        return {
            "valid": False,
            "message": "订阅信息错误",
            "user_type": user_type,
        }
