import json
import logging
import time
from typing import Optional

from sqlalchemy import select, func, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from models.cache import StatisticsCache
from models.user import User
from models.product import Product
from models.order import PaymentOrder
from models.log import UserLoginLog

logger = logging.getLogger(__name__)


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
    return result.rowcount


async def clear_all_statistics_cache(session: AsyncSession) -> int:
    stmt = sa_delete(StatisticsCache)
    result = await session.execute(stmt)
    return result.rowcount


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
            pass

    try:
        current_time = int(time.time())
        today_start = current_time - (current_time % 86400)
        yesterday_start = today_start - 86400
        month_start = current_time - (current_time % (30 * 86400))

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


async def count_total_products(session: AsyncSession) -> int:
    result = await session.scalar(select(func.count(Product.id)))
    return result or 0
