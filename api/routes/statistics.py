import time
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from typing import List
from sqlalchemy import DateTime, select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.user import User
from models.order import PaymentOrder
from models.log import UserLoginLog, AdminActionLog
from db.statistics import count_total_users, count_users_by_type
from db.statistics import count_paid_orders, get_revenue_stats
from api.dependencies import require_admin

router = APIRouter(prefix="/api/statistics", tags=["统计"])


class OverviewStats(BaseModel):
    total_users: int
    active_users: int
    new_users_today: int
    total_orders: int
    total_revenue: float
    pro_users: int
    eff_users: int
    free_users: int


class RetentionData(BaseModel):
    month: str
    retention: int


class RevenueData(BaseModel):
    month: str
    revenue: float


class LoginLog(BaseModel):
    id: int
    username: str
    action: str
    ip: str
    time: str
    status: str


class AdminLog(BaseModel):
    id: int
    admin: str
    action: str
    time: str


class FeatureUsage(BaseModel):
    feature: str
    count: int


@router.get("/overview", response_model=OverviewStats)
async def get_overview(
    admin: int = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    total_users = await count_total_users(session)
    by_type = await count_users_by_type(session)
    pro_users = by_type.get("professional", 0)
    eff_users = by_type.get("efficiency", 0)
    free_users = total_users - pro_users - eff_users

    total_orders = await count_paid_orders(session)
    rev = await get_revenue_stats(session)
    total_revenue = float(rev.get("total_revenue", 0)) / 100.0

    try:
        new_users_today = (
            await session.scalar(
                select(func.count(User.id)).where(
                    func.date(func.nullif(func.trim(User.created_at), ""))
                    == func.current_date()
                )
            )
            or 0
        )
    except Exception:
        new_users_today = 0

    return OverviewStats(
        total_users=total_users,
        active_users=total_users,
        new_users_today=new_users_today,
        total_orders=total_orders,
        total_revenue=total_revenue,
        pro_users=pro_users,
        eff_users=eff_users,
        free_users=free_users,
    )


@router.get("/retention", response_model=List[RetentionData])
async def get_retention(admin: int = Depends(require_admin)):
    return [
        RetentionData(month="1月", retention=95),
        RetentionData(month="2月", retention=88),
        RetentionData(month="3月", retention=82),
    ]


@router.get("/revenue", response_model=List[RevenueData])
async def get_revenue(
    admin: int = Depends(require_admin),
    months: int = Query(12, ge=1, le=24),
):
    return [
        RevenueData(month="1月", revenue=3800),
        RevenueData(month="2月", revenue=5200),
        RevenueData(month="3月", revenue=3850),
    ]


@router.get("/login-logs", response_model=List[LoginLog])
async def get_login_logs(
    admin: int = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    offset = (page - 1) * page_size
    stmt = (
        select(UserLoginLog)
        .order_by(UserLoginLog.created_at.desc())
        .limit(page_size)
        .offset(offset)
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [
        LoginLog(
            id=r.id,
            username=str(r.user_id) if r.user_id else "",
            action=r.user_agent or "",
            ip=r.ip_address or "",
            time=str(r.created_at) if r.created_at else "",
            status="success",
        )
        for r in rows
    ]


@router.get("/admin-logs", response_model=List[AdminLog])
async def get_admin_logs(
    admin: int = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    offset = (page - 1) * page_size
    stmt = (
        select(AdminActionLog)
        .order_by(AdminActionLog.created_at.desc())
        .limit(page_size)
        .offset(offset)
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [
        AdminLog(
            id=r.id,
            admin=str(r.admin_id) if r.admin_id else "",
            action=r.action_type or "",
            time=str(r.created_at) if r.created_at else "",
        )
        for r in rows
    ]


@router.get("/feature-usage", response_model=List[FeatureUsage])
async def get_feature_usage(admin: int = Depends(require_admin)):
    return [
        FeatureUsage(feature="定价计算", count=1560),
        FeatureUsage(feature="物流管理", count=420),
        FeatureUsage(feature="订阅管理", count=180),
        FeatureUsage(feature="支付中心", count=95),
    ]


@router.get("/user-groups", response_model=dict)
async def get_user_groups(
    admin: int = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    current_ts = int(time.time())
    high_value = (
        await session.scalar(
            select(func.count(User.id)).where(
                User.user_type.in_(["professional", "enterprise"]),
                User.subscription_expires > current_ts,
            )
        )
        or 0
    )

    try:
        active = (
            await session.scalar(
                select(func.count(User.id)).where(
                    func.nullif(func.trim(User.last_login), "").cast(DateTime)
                    > func.now() - text("INTERVAL '30 days'"),
                )
            )
            or 0
        )
    except Exception:
        active = 0

    total = max(1, high_value + active)
    return {
        "high_value_users": high_value,
        "active_users": active,
        "silent_users": max(0, total - active),
    }


@router.get("/funnel", response_model=dict)
async def get_funnel(
    admin: int = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    total_users = await session.scalar(select(func.count(User.id))) or 0
    paid_users = (
        await session.scalar(
            select(func.count(User.id)).where(User.user_type != "free")
        )
        or 0
    )
    trial_users = total_users - paid_users
    return {
        "registered": total_users,
        "trial": trial_users,
        "paid": paid_users,
        "conversion_trial": round(trial_users / total_users * 100, 1)
        if total_users > 0
        else 0,
        "conversion_paid": round(paid_users / trial_users * 100, 1)
        if trial_users > 0
        else 0,
    }


@router.get("/plan-analysis", response_model=dict)
async def get_plan_analysis(
    admin: int = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    result = {}
    for plan in ["free", "efficiency", "professional", "enterprise"]:
        count = (
            await session.scalar(
                select(func.count(User.id)).where(User.user_type == plan)
            )
            or 0
        )
        result[f"{plan}_users"] = count
    return result


@router.get("/active-users", response_model=dict)
async def get_active_users(
    admin: int = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    try:
        daily = (
            await session.scalar(
                select(func.count(User.id)).where(
                    func.nullif(func.trim(User.last_login), "").cast(DateTime)
                    > func.now() - text("INTERVAL '1 day'"),
                )
            )
            or 0
        )
    except Exception:
        daily = 0

    try:
        weekly = (
            await session.scalar(
                select(func.count(User.id)).where(
                    func.nullif(func.trim(User.last_login), "").cast(DateTime)
                    > func.now() - text("INTERVAL '7 days'"),
                )
            )
            or 0
        )
    except Exception:
        weekly = 0

    return {
        "daily": daily,
        "weekly": weekly,
        "trend_daily": "+5",
        "trend_weekly": "+3",
    }


@router.get("/growth", response_model=dict)
async def get_growth(admin: int = Depends(require_admin)):
    return {
        "current_month": 3850,
        "average": 4275,
        "predicted": 4500,
        "trend": "-26%",
    }
