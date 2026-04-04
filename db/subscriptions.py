import math
import time
from datetime import date, datetime
from typing import Any, Mapping, Sequence, cast

from db._proxy import _db
from db.helpers import DB_EXCEPTIONS


def get_user_subscription_info(user_id):
    """获取用户订阅信息"""
    with _db.get_db_connection() as (conn, c):
        if c is None:
            return None
        sql_raw = (
            "SELECT id, username, user_type, expiry_date, "
            "remaining_calculations, first_login_date, "
            "test_days_remaining, role, subscription_type, "
            "subscription_expires "
            "FROM users WHERE id = ?"
        )
        sql = _db._safe_adapt_sql(sql_raw, conn)
        c.execute(sql, (user_id,))
        user = c.fetchone()

        if not user:
            return None

        fields = [
            "id",
            "username",
            "user_type",
            "expiry_date",
            "remaining_calculations",
            "first_login_date",
            "test_days_remaining",
            "role",
            "subscription_type",
            "subscription_expires",
        ]

        if isinstance(user, dict):
            return user
        if hasattr(user, "keys"):
            mapped = dict(cast(Mapping[str, Any], user))
            for field in fields:
                mapped.setdefault(field, None)
            return mapped

        values = list(cast(Sequence[Any], user))
        if len(values) < len(fields):
            values.extend([None] * (len(fields) - len(values)))
        return dict(zip(fields, values))


def update_user_subscription(user_id, updates):
    """更新用户订阅信息"""
    with _db.get_db_connection() as (conn, c):
        placeholder = _db.get_placeholder()
        set_clauses = []
        values = []
        for field, value in updates.items():
            set_clauses.append(f"{field} = {placeholder}")
            values.append(value)

        values.append(user_id)
        sql_raw = f"UPDATE users SET {', '.join(set_clauses)} WHERE id = {placeholder}"
        sql = _db._safe_adapt_sql(sql_raw, conn)
        c.execute(sql, values)
        conn.commit()
        return c.rowcount > 0


def _check_test_status(user_info, user_type):
    """检查测试用户状态"""
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
    """解析到期日期为datetime对象"""
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
    """检查按月付费用户状态"""
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
    """检查企业用户状态"""
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


def _check_new_tier_free(user_info, user_type, user_id):
    """检查免费版用户状态，修正异常-1"""
    remaining_calculations = user_info.get("remaining_calculations", 0)
    if remaining_calculations == -1:
        try:
            with _db.get_db_connection() as (fix_conn, fix_cur):
                sql_raw = "UPDATE users SET remaining_calculations = 10 WHERE id = ?"
                sql = _db._safe_adapt_sql(sql_raw, fix_conn)
                fix_cur.execute(sql, (user_id,))
                fix_conn.commit()
        except DB_EXCEPTIONS:
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
    """从订阅信息中计算剩余天数，返回 (days_remaining, error_dict_or_None)"""
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


def _check_new_tier_status(user_info, user_type, user_id):
    """检查新套餐类型用户状态"""
    if user_type == "free":
        return _check_new_tier_free(user_info, user_type, user_id)
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


def check_user_subscription_status(user_id):
    """检查用户订阅状态"""
    user_info = _db.get_user_subscription_info(user_id)
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
        return _check_new_tier_status(user_info, user_type, user_id)

    return {
        "valid": False,
        "message": "未知用户类型",
        "user_type": user_type,
    }


def decrement_user_calculations(user_id):
    """减少用户计算次数（以 subscription_type 优先判定用户类型）。"""
    with _db.get_db_connection() as (conn, c):
        sql_raw = (
            "SELECT user_type, subscription_type, "
            "remaining_calculations FROM users WHERE id = ?"
        )
        sql = _db._safe_adapt_sql(sql_raw, conn)
        user = _db._safe_execute_fetchone(c, sql, (user_id,), conn)

        if not user:
            return False

        db_user_type = user[0]
        db_subscription_type = user[1] if len(user) > 1 else None
        remaining = user[2] if len(user) > 2 else -1

        user_type = (db_subscription_type or db_user_type or "").strip()

        if user_type in [
            "admin",
            "permanent",
            "enterprise",
            "gratitude",
            "efficiency",
            "professional",
        ]:
            return True

        if user_type == "test":
            return True

        if user_type in ("free", "monthly"):
            if remaining <= 0:
                return False
            sql_raw = (
                "UPDATE users SET remaining_calculations = "
                "remaining_calculations - 1 WHERE id = ? "
                "AND remaining_calculations > 0"
            )
            sql = _db._safe_adapt_sql(sql_raw, conn)
            c.execute(sql, (user_id,))
            conn.commit()
            return c.rowcount > 0

        return False


def reset_free_users_daily_calculations():
    """每日重置免费用户的计算次数为10次"""
    with _db.get_db_connection() as (conn, c):
        try:
            c.execute(
                """
                UPDATE users
                SET remaining_calculations = 10
                WHERE user_type = 'free'
                """
            )
            affected_rows = c.rowcount
            conn.commit()

            from logger_config import logger

            logger.info(
                "每日计算次数重置完成：重置了 %d 个免费用户的计算次数",
                affected_rows,
            )

            return affected_rows
        except Exception as e:
            from logger_config import logger

            logger.error("重置免费用户计算次数失败: %s", e)
            return 0
