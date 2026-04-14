import math
import time
from datetime import date, datetime
from typing import Optional

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User


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
    user = await session.get(User, user_id)
    if not user:
        return False

    user_type = (user.subscription_type or user.user_type or "").strip()

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
        remaining = user.remaining_calculations or 0
        if remaining <= 0:
            return False
        await session.execute(
            update(User)
            .where(
                User.id == user_id,
                User.remaining_calculations > 0,
            )
            .values(remaining_calculations=User.remaining_calculations - 1)
        )
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
        return 0


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
            pass
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
