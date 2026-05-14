import logging
import math
import sys
import time
from datetime import date, datetime, timezone

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from db.plans import get_plan_by_code
from models.user import User

logger = logging.getLogger(__name__)


def _patched_get_plan_by_code():
    subscriptions_module = sys.modules.get("db.subscriptions")
    if subscriptions_module is not None:
        return getattr(subscriptions_module, "get_plan_by_code", get_plan_by_code)
    return get_plan_by_code


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
        user_type_raw = (
            getattr(user, "subscription_type", None)
            or getattr(user, "user_type", None)
            or ""
        )
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
    try:
        user = await session.get(User, user_id)
        if not user:
            return False

        plan_lookup = _patched_get_plan_by_code()
        plan = await plan_lookup(session, user.subscription_type or "free")
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
        await session.flush()
        return True
    except Exception:
        logger.warning("重置用户每日计算次数失败", exc_info=True)
        return False


def check_test_status(user_info, user_type):
    first_login = user_info.get("first_login_date")
    if not first_login:
        return {
            "valid": True,
            "message": "测试用户未开始计时",
            "user_type": user_type,
        }
    try:
        first_login_date = datetime.fromisoformat(first_login)
        if first_login_date.tzinfo is None:
            days_elapsed = (datetime.now() - first_login_date).days
        else:
            days_elapsed = (datetime.now(timezone.utc) - first_login_date).days
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


def parse_expiry_date(expiry_date):
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


def check_monthly_status(user_info, user_type):
    expiry_date = user_info.get("expiry_date")
    remaining_calculations = user_info.get("remaining_calculations", 0)
    if not expiry_date:
        return {"valid": False, "message": "订阅信息不完整"}
    try:
        expiry = parse_expiry_date(expiry_date)
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


def check_enterprise_status(user_info, user_type):
    expiry_date = user_info.get("expiry_date")
    if not expiry_date:
        return {
            "valid": False,
            "message": "订阅信息不完整",
            "user_type": user_type,
        }
    try:
        expiry = parse_expiry_date(expiry_date)
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


async def check_new_tier_free(
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


def get_days_remaining_from_info(user_info, user_type):
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


async def check_new_tier_status(
    session: AsyncSession,
    user_info,
    user_type,
    user_id,
):
    if user_type == "free":
        return await check_new_tier_free(session, user_info, user_type, user_id)
    if user_type == "gratitude":
        return {
            "valid": True,
            "message": "感谢版用户，永久有效",
            "remaining_days": -1,
            "remaining_calculations": -1,
            "user_type": user_type,
        }

    days_remaining, remaining_calculations, err = get_days_remaining_from_info(
        user_info, user_type
    )
    if err is not None:
        return err
    assert days_remaining is not None

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
