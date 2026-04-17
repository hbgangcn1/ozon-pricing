import json
import logging
import time
from datetime import datetime
from typing import Optional

from sqlalchemy import delete as sa_delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.cache import StatisticsCache
from models.user import User
from models.product import Product
from models.order import PaymentOrder
from models.log import UserLoginLog

logger = logging.getLogger(__name__)


def _parse_user_created_at(value: Optional[str]) -> Optional[datetime]:
    if value is None:
        return None

    trimmed = value.strip()
    if not trimmed:
        return None

    if trimmed.isdigit() and len(trimmed) == 10:
        return datetime.fromtimestamp(int(trimmed))

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(trimmed, fmt)
        except ValueError:
            continue
    return None


def _month_start(dt: datetime) -> datetime:
    return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _shift_month(dt: datetime, months: int) -> datetime:
    month_index = (dt.year * 12 + (dt.month - 1)) + months
    year = month_index // 12
    month = month_index % 12 + 1
    return dt.replace(year=year, month=month, day=1)


async def get_statistics_cache(
    session: AsyncSession,
    cache_key: str,
) -> Optional[str]:
    now = int(time.time())
    stmt = select(StatisticsCache.cache_data).where(
        StatisticsCache.cache_key == cache_key,
        StatisticsCache.expires_at > now,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def set_statistics_cache(
    session: AsyncSession,
    cache_key: str,
    data: str,
    ttl: int = 300,
) -> None:
    now = int(time.time())
    stmt = select(StatisticsCache).where(
        StatisticsCache.cache_key == cache_key,
    )
    result = await session.execute(stmt)
    record = result.scalar_one_or_none()
    if record:
        record.cache_data = data
        record.expires_at = now + ttl
        record.updated_at = now
    else:
        record = StatisticsCache(
            cache_key=cache_key,
            cache_data=data,
            expires_at=now + ttl,
        )
        session.add(record)


async def clear_expired_cache(session: AsyncSession) -> int:
    now = int(time.time())
    stmt = sa_delete(StatisticsCache).where(
        StatisticsCache.expires_at <= now,
    )
    result = await session.execute(stmt)
    return int(getattr(result, "rowcount", 0) or 0)


async def clear_all_statistics_cache(session: AsyncSession) -> int:
    stmt = sa_delete(StatisticsCache)
    result = await session.execute(stmt)
    return int(getattr(result, "rowcount", 0) or 0)


async def _get_user_stats_orm(
    session: AsyncSession,
    today_start: int,
    current_time: int,
) -> dict:
    active_today = await session.scalar(
        select(func.count(func.distinct(UserLoginLog.user_id))).where(
            UserLoginLog.login_time >= today_start,
        ),
    )
    new_today = await session.scalar(
        select(func.count(User.id)).where(
            User.role != "admin",
            User.created_at >= today_start,
        ),
    )
    total = await session.scalar(
        select(func.count(User.id)).where(User.role != "admin"),
    )
    online = await session.scalar(
        select(func.count(func.distinct(UserLoginLog.user_id))).where(
            UserLoginLog.login_time >= current_time - 300,
        ),
    )
    return {
        "active_users_today": active_today or 0,
        "new_users_today": new_today or 0,
        "total_users": total or 0,
        "online_users": online or 0,
    }


async def _get_revenue_stats_orm(
    session: AsyncSession,
    today_start: int,
    yesterday_start: int,
    month_start: int,
) -> dict:
    total = await session.scalar(
        select(func.coalesce(func.sum(PaymentOrder.amount), 0)).where(
            PaymentOrder.status == "SUCCESS",
        ),
    )
    today_rev = await session.scalar(
        select(func.coalesce(func.sum(PaymentOrder.amount), 0)).where(
            PaymentOrder.status == "SUCCESS",
            PaymentOrder.created_at >= today_start,
        ),
    )
    yest_rev = await session.scalar(
        select(func.coalesce(func.sum(PaymentOrder.amount), 0)).where(
            PaymentOrder.status == "SUCCESS",
            PaymentOrder.created_at >= yesterday_start,
            PaymentOrder.created_at < today_start,
        ),
    )
    month_rev = await session.scalar(
        select(func.coalesce(func.sum(PaymentOrder.amount), 0)).where(
            PaymentOrder.status == "SUCCESS",
            PaymentOrder.created_at >= month_start,
        ),
    )
    return {
        "total_revenue": round((total or 0) / 100.0, 2),
        "revenue_today": round((today_rev or 0) / 100.0, 2),
        "revenue_yesterday": round((yest_rev or 0) / 100.0, 2),
        "revenue_month": round((month_rev or 0) / 100.0, 2),
    }


async def get_dashboard_stats(session: AsyncSession) -> dict:
    cache_key = "dashboard_stats"
    cached = await get_statistics_cache(session, cache_key)
    if cached:
        try:
            return json.loads(cached)
        except Exception:
            logger.warning("统计缓存JSON解析失败: key=%s", cache_key)

    try:
        current_time = int(time.time())
        today_start = current_time - (current_time % 86400)
        yesterday_start = today_start - 86400
        month_start_dt = _month_start(datetime.now())
        month_start = int(month_start_dt.timestamp())

        user_stats = await _get_user_stats_orm(
            session,
            today_start,
            current_time,
        )
        rev_stats = await _get_revenue_stats_orm(
            session,
            today_start,
            yesterday_start,
            month_start,
        )

        result = {**user_stats, **rev_stats, "timestamp": current_time}
        await set_statistics_cache(
            session,
            cache_key,
            json.dumps(result, ensure_ascii=False),
            300,
        )
        return result
    except Exception:
        logger.warning("获取总览数据失败", exc_info=True)
        return {}


async def count_total_users(session: AsyncSession) -> int:
    result = await session.scalar(select(func.count(User.id)))
    return result or 0


async def count_users_by_type(session: AsyncSession) -> dict:
    stmt = select(
        User.subscription_type,
        func.count(User.id),
    ).group_by(User.subscription_type)
    result = await session.execute(stmt)
    return {row[0] or "free": row[1] for row in result.all()}


async def count_paid_orders(session: AsyncSession) -> int:
    result = await session.scalar(
        select(func.count(PaymentOrder.id)).where(
            PaymentOrder.status == "SUCCESS",
        ),
    )
    return result or 0


async def get_revenue_stats(session: AsyncSession) -> dict:
    total = await session.scalar(
        select(func.sum(PaymentOrder.amount)).where(
            PaymentOrder.status == "SUCCESS",
        ),
    )
    return {"total_revenue": total or 0}


async def get_monthly_retention(
    session: AsyncSession,
    months: int = 6,
) -> list[dict]:
    current_month = _month_start(datetime.now())
    cohort_months = [
        _shift_month(current_month, -offset) for offset in range(max(months, 1), 0, -1)
    ]
    cohort_lookup = {month: set() for month in cohort_months}

    user_rows = (
        await session.execute(
            select(User.id, User.created_at).where(
                User.created_at.is_not(None),
                func.nullif(func.trim(User.created_at), "").is_not(None),
            )
        )
    ).all()

    for user_id, created_at in user_rows:
        created_dt = _parse_user_created_at(created_at)
        if created_dt is None:
            continue
        cohort_month = _month_start(created_dt)
        if cohort_month in cohort_lookup:
            cohort_lookup[cohort_month].add(user_id)

    cohort_user_ids = {
        user_id for user_ids in cohort_lookup.values() for user_id in user_ids
    }
    if not cohort_user_ids:
        return []

    earliest_login = int(_shift_month(cohort_months[0], 1).timestamp())
    latest_login = int(_shift_month(current_month, 1).timestamp())
    login_rows = (
        await session.execute(
            select(UserLoginLog.user_id, UserLoginLog.login_time).where(
                UserLoginLog.user_id.in_(cohort_user_ids),
                UserLoginLog.login_time >= earliest_login,
                UserLoginLog.login_time < latest_login,
            )
        )
    ).all()
    logins_by_month: dict[datetime, set[int]] = {}
    for user_id, login_time in login_rows:
        login_month = _month_start(datetime.fromtimestamp(login_time))
        logins_by_month.setdefault(login_month, set()).add(user_id)

    retention_data: list[dict] = []
    for cohort_month in cohort_months:
        cohort_users = cohort_lookup[cohort_month]
        total_users = len(cohort_users)
        if total_users == 0:
            continue
        next_month = _shift_month(cohort_month, 1)
        retained_users = len(cohort_users & logins_by_month.get(next_month, set()))
        retention = (
            int(round((retained_users / total_users) * 100)) if total_users else 0
        )
        retention_data.append(
            {
                "month": cohort_month.strftime("%Y-%m"),
                "retention": retention,
            }
        )

    return retention_data


async def get_monthly_revenue(
    session: AsyncSession,
    months: int = 12,
) -> list[dict]:
    month_count = max(months, 1)
    current_month = _month_start(datetime.now())
    earliest_month = _shift_month(current_month, -(month_count - 1))
    next_month = _shift_month(current_month, 1)
    rows = (
        await session.execute(
            select(PaymentOrder.amount, PaymentOrder.created_at).where(
                PaymentOrder.status == "SUCCESS",
                PaymentOrder.created_at >= int(earliest_month.timestamp()),
                PaymentOrder.created_at < int(next_month.timestamp()),
            )
        )
    ).all()
    if not rows:
        return []

    totals: dict[str, float] = {}
    for amount, created_at in rows:
        month_label = _month_start(datetime.fromtimestamp(created_at)).strftime("%Y-%m")
        totals[month_label] = round(totals.get(month_label, 0.0) + amount / 100.0, 2)

    month_labels = [
        _shift_month(earliest_month, offset).strftime("%Y-%m")
        for offset in range(month_count)
    ]
    return [
        {
            "month": label,
            "revenue": totals.get(label, 0.0),
        }
        for label in month_labels
    ]


async def count_total_products(session: AsyncSession) -> int:
    result = await session.scalar(select(func.count(Product.id)))
    return result or 0
