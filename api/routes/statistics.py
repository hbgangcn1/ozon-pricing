from decimal import Decimal
from loguru import logger
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import Float, and_, case, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.user import User
from models.log import UserLoginLog, AdminActionLog
from db.statistics import (
    count_new_users_today,
    count_paid_orders,
    count_total_users,
    count_users_by_type,
    get_monthly_retention,
    get_monthly_revenue,
    get_revenue_stats,
)
from db.orders import get_all_orders
from api.models.schemas import DecimalField
from api.dependencies import require_admin

router = APIRouter(prefix="/api/statistics", tags=["统计"])

_CENTS_DIVISOR = Decimal("100")
_MONEY_PRECISION = Decimal("0.01")


def _quantize_money(value: object) -> Decimal:
    return Decimal(str(value or 0)).quantize(_MONEY_PRECISION)


def _to_decimal_money(value: object) -> Decimal:
    return _quantize_money(Decimal(str(value or 0)) / _CENTS_DIVISOR)


class OverviewStats(BaseModel):
    total_users: int
    active_users: int
    new_users_today: int
    total_orders: int
    total_revenue: DecimalField
    pro_users: int
    eff_users: int
    free_users: int


class RetentionData(BaseModel):
    month: str
    retention: int


class RevenueData(BaseModel):
    month: str
    revenue: DecimalField


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


class LoginLogPage(BaseModel):
    items: List[LoginLog]
    total: int
    page: int
    page_size: int


class AdminLogPage(BaseModel):
    items: List[AdminLog]
    total: int
    page: int
    page_size: int


class OrderItem(BaseModel):
    order_id: str
    username: str
    amount: float
    order_type: str
    status: str
    created_at: str


class OrderPage(BaseModel):
    items: List[OrderItem]
    total: int
    page: int
    page_size: int


def _last_login_expr():
    trimmed = func.nullif(func.trim(User.last_login), "")
    is_epoch = trimmed.op("~")(r"^\d+$")
    return case(
        (is_epoch, func.to_timestamp(trimmed.cast(Float))),
        else_=None,
    )


def _format_trend(current: int, previous: int) -> str:
    delta = current - previous
    return f"+{delta}" if delta > 0 else str(delta)


def _format_unix_timestamp(timestamp: Optional[int]) -> str:
    if not timestamp:
        return ""
    try:
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
    except (OSError, OverflowError, TypeError, ValueError):
        return ""


def _parse_date_filter(
    value: Optional[str], *, end_of_day: bool = False
) -> Optional[int]:
    if not value:
        return None
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail="日期格式必须为 YYYY-MM-DD"
        ) from exc
    if end_of_day:
        parsed = parsed + timedelta(days=1) - timedelta(seconds=1)
    return int(parsed.timestamp())


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
    total_revenue = _to_decimal_money(rev.get("total_revenue", 0))

    try:
        new_users_today = await count_new_users_today(session)
    except Exception as e:
        logger.exception(f"查询今日新用户失败: {e}")
        new_users_today = 0

    try:
        active_users = (
            await session.scalar(
                select(func.count(User.id)).where(
                    _last_login_expr() > func.now() - text("INTERVAL '30 days'"),
                )
            )
            or 0
        )
    except Exception as e:
        logger.exception(f"查询活跃用户失败: {e}")
        active_users = 0

    return OverviewStats(
        total_users=total_users,
        active_users=active_users,
        new_users_today=new_users_today,
        total_orders=total_orders,
        total_revenue=total_revenue,
        pro_users=pro_users,
        eff_users=eff_users,
        free_users=free_users,
    )


@router.get("/retention", response_model=List[RetentionData])
async def get_retention(
    admin: int = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
    months: int = Query(6, ge=1, le=24),
):
    data = await get_monthly_retention(session, months=months)
    return [RetentionData(**item) for item in data]


@router.get("/revenue", response_model=List[RevenueData])
async def get_revenue(
    admin: int = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
    months: int = Query(12, ge=1, le=24),
):
    data = await get_monthly_revenue(session, months=months)
    return [
        RevenueData(
            month=item["month"], revenue=_quantize_money(item.get("revenue", 0))
        )
        for item in data
    ]


@router.get("/login-logs", response_model=LoginLogPage)
async def get_login_logs(
    admin: int = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str = Query("", max_length=100),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
):
    offset = (page - 1) * page_size
    start_ts = _parse_date_filter(date_from)
    end_ts = _parse_date_filter(date_to, end_of_day=True)

    filters = []
    if search:
        filters.append(func.coalesce(User.username, "").ilike(f"%{search.strip()}%"))
    if start_ts is not None:
        filters.append(UserLoginLog.created_at >= start_ts)
    if end_ts is not None:
        filters.append(UserLoginLog.created_at <= end_ts)

    stmt = (
        select(UserLoginLog, User.username)
        .select_from(UserLoginLog)
        .outerjoin(User, User.id == UserLoginLog.user_id)
        .where(and_(*filters) if filters else text("TRUE"))
        .order_by(UserLoginLog.created_at.desc())
        .limit(page_size)
        .offset(offset)
    )
    result = await session.execute(stmt)
    rows = result.all()

    count_stmt = (
        select(func.count())
        .select_from(UserLoginLog)
        .outerjoin(User, User.id == UserLoginLog.user_id)
        .where(and_(*filters) if filters else text("TRUE"))
    )
    total = await session.scalar(count_stmt) or 0

    items = [
        LoginLog(
            id=log.id,
            username=username or "",
            action="登录",
            ip=log.ip_address or "",
            time=_format_unix_timestamp(log.created_at or log.login_time),
            status="成功",
        )
        for log, username in rows
    ]
    return LoginLogPage(items=items, total=total, page=page, page_size=page_size)


@router.get("/admin-logs", response_model=AdminLogPage)
async def get_admin_logs(
    admin: int = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str = Query("", max_length=100),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
):
    offset = (page - 1) * page_size
    start_ts = _parse_date_filter(date_from)
    end_ts = _parse_date_filter(date_to, end_of_day=True)

    filters = []
    if search:
        keyword = f"%{search.strip()}%"
        filters.append(
            or_(
                func.coalesce(User.username, "").ilike(keyword),
                func.coalesce(AdminActionLog.action_type, "").ilike(keyword),
            )
        )
    if start_ts is not None:
        filters.append(AdminActionLog.created_at >= start_ts)
    if end_ts is not None:
        filters.append(AdminActionLog.created_at <= end_ts)

    stmt = (
        select(AdminActionLog, User.username)
        .select_from(AdminActionLog)
        .outerjoin(User, User.id == AdminActionLog.admin_id)
        .where(and_(*filters) if filters else text("TRUE"))
        .order_by(AdminActionLog.created_at.desc())
        .limit(page_size)
        .offset(offset)
    )
    result = await session.execute(stmt)
    rows = result.all()

    count_stmt = (
        select(func.count())
        .select_from(AdminActionLog)
        .outerjoin(User, User.id == AdminActionLog.admin_id)
        .where(and_(*filters) if filters else text("TRUE"))
    )
    total = await session.scalar(count_stmt) or 0

    items = [
        AdminLog(
            id=log.id,
            admin=username or "",
            action=log.action_type or "",
            time=_format_unix_timestamp(log.created_at),
        )
        for log, username in rows
    ]
    return AdminLogPage(items=items, total=total, page=page, page_size=page_size)


@router.get("/active-users", response_model=dict)
async def get_active_users(
    admin: int = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    try:
        daily = (
            await session.scalar(
                select(func.count(User.id)).where(
                    _last_login_expr() > func.now() - text("INTERVAL '1 day'"),
                )
            )
            or 0
        )
    except Exception as e:
        logger.exception(f"查询日活用户失败: {e}")
        daily = 0

    try:
        weekly = (
            await session.scalar(
                select(func.count(User.id)).where(
                    _last_login_expr() > func.now() - text("INTERVAL '7 days'"),
                )
            )
            or 0
        )
    except Exception as e:
        logger.exception(f"查询周活用户失败: {e}")
        weekly = 0

    try:
        yesterday_daily = (
            await session.scalar(
                select(func.count(User.id)).where(
                    _last_login_expr() <= func.now() - text("INTERVAL '1 day'"),
                    _last_login_expr() > func.now() - text("INTERVAL '2 days'"),
                )
            )
            or 0
        )
    except Exception as e:
        logger.exception(f"查询昨日日活失败: {e}")
        yesterday_daily = 0

    try:
        last_week_weekly = (
            await session.scalar(
                select(func.count(User.id)).where(
                    _last_login_expr() <= func.now() - text("INTERVAL '7 days'"),
                    _last_login_expr() > func.now() - text("INTERVAL '14 days'"),
                )
            )
            or 0
        )
    except Exception as e:
        logger.exception(f"查询上周周活失败: {e}")
        last_week_weekly = 0

    return {
        "daily": daily,
        "weekly": weekly,
        "trend_daily": _format_trend(daily, yesterday_daily),
        "trend_weekly": _format_trend(weekly, last_week_weekly),
    }


@router.get("/orders", response_model=OrderPage)
async def get_orders(
    admin: int = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str = Query("", max_length=100),
    status: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
):
    start_ts = _parse_date_filter(date_from)
    end_ts = _parse_date_filter(date_to, end_of_day=True)

    data = await get_all_orders(
        session,
        page=page,
        page_size=page_size,
        search=search,
        status=status,
        date_from=start_ts,
        date_to=end_ts,
    )

    items = [OrderItem(**row) for row in data["orders"]]
    return OrderPage(
        items=items,
        total=data["total"],
        page=page,
        page_size=page_size,
    )
