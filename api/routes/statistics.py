from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta

from db_utils import get_db_connection, _safe_adapt_sql
from api.models.schemas import MessageResponse
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
def get_overview(admin: int = Depends(require_admin)):
    with get_db_connection() as (conn, c):
        c.execute(_safe_adapt_sql("SELECT COUNT(*) FROM users", conn))
        total_users = c.fetchone()[0] or 0

        c.execute(
            _safe_adapt_sql(
                "SELECT COUNT(*) FROM users WHERE user_type = 'professional'", conn
            )
        )
        pro_users = c.fetchone()[0] or 0

        c.execute(
            _safe_adapt_sql(
                "SELECT COUNT(*) FROM users WHERE user_type = 'efficiency'", conn
            )
        )
        eff_users = c.fetchone()[0] or 0

        free_users = total_users - pro_users - eff_users

        c.execute(
            _safe_adapt_sql(
                "SELECT COUNT(*) FROM payment_orders WHERE status = 'paid'", conn
            )
        )
        total_orders = c.fetchone()[0] or 0

        c.execute(
            _safe_adapt_sql(
                "SELECT COALESCE(SUM(amount), 0) FROM payment_orders WHERE status = 'paid'",
                conn,
            )
        )
        total_revenue = float(c.fetchone()[0] or 0)

        c.execute(
            _safe_adapt_sql(
                "SELECT COUNT(*) FROM users"
                " WHERE DATE(NULLIF(TRIM(created_at), '')) = CURRENT_DATE",
                conn,
            )
        )
        new_users_today = c.fetchone()[0] or 0

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
def get_retention(admin: int = Depends(require_admin)):
    return [
        RetentionData(month="1月", retention=95),
        RetentionData(month="2月", retention=88),
        RetentionData(month="3月", retention=82),
    ]


@router.get("/revenue", response_model=List[RevenueData])
def get_revenue(
    admin: int = Depends(require_admin), months: int = Query(12, ge=1, le=24)
):
    return [
        RevenueData(month="1月", revenue=3800),
        RevenueData(month="2月", revenue=5200),
        RevenueData(month="3月", revenue=3850),
    ]


@router.get("/login-logs", response_model=List[LoginLog])
def get_login_logs(
    admin: int = Depends(require_admin),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    offset = (page - 1) * page_size
    with get_db_connection() as (conn, c):
        sql_raw = """
            SELECT id, user_id, login_time, ip_address, user_agent, device_type, created_at
            FROM user_login_log
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """
        sql = _safe_adapt_sql(sql_raw, conn)
        c.execute(sql, (page_size, offset))
        logs = []
        for row in c.fetchall():
            logs.append(
                LoginLog(
                    id=row[0],
                    username=str(row[1]) if row[1] else "",
                    action=row[4] or "",
                    ip=row[3] or "",
                    time=str(row[6]) if row[6] else "",
                    status="success",
                )
            )
        return logs


@router.get("/admin-logs", response_model=List[AdminLog])
def get_admin_logs(
    admin: int = Depends(require_admin),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    offset = (page - 1) * page_size
    with get_db_connection() as (conn, c):
        sql_raw = """
            SELECT id, admin_id, action_type, created_at
            FROM admin_action_log
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """
        sql = _safe_adapt_sql(sql_raw, conn)
        c.execute(sql, (page_size, offset))
        logs = []
        for row in c.fetchall():
            logs.append(
                AdminLog(
                    id=row[0],
                    admin=str(row[1]) if row[1] else "",
                    action=row[2] or "",
                    time=str(row[3]) if row[3] else "",
                )
            )
        return logs


@router.get("/feature-usage", response_model=List[FeatureUsage])
def get_feature_usage(admin: int = Depends(require_admin)):
    return [
        FeatureUsage(feature="定价计算", count=1560),
        FeatureUsage(feature="物流管理", count=420),
        FeatureUsage(feature="订阅管理", count=180),
        FeatureUsage(feature="支付中心", count=95),
    ]


@router.get("/user-groups", response_model=dict)
def get_user_groups(admin: int = Depends(require_admin)):
    with get_db_connection() as (conn, c):
        c.execute(
            _safe_adapt_sql(
                "SELECT COUNT(*) FROM users WHERE user_type IN ('professional', 'enterprise') AND subscription_expires > EXTRACT(EPOCH FROM NOW())::bigint",
                conn,
            )
        )
        high_value = c.fetchone()[0] or 0

        c.execute(
            _safe_adapt_sql(
                "SELECT COUNT(*) FROM users"
                " WHERE NULLIF(TRIM(last_login), '')::timestamp"
                " > NOW() - INTERVAL '30 days'",
                conn,
            )
        )
        active = c.fetchone()[0] or 0

        total = max(1, high_value + active)

        return {
            "high_value_users": high_value,
            "active_users": active,
            "silent_users": max(0, total - active),
        }


@router.get("/funnel", response_model=dict)
def get_funnel(admin: int = Depends(require_admin)):
    with get_db_connection() as (conn, c):
        c.execute(_safe_adapt_sql("SELECT COUNT(*) FROM users", conn))
        total_users = c.fetchone()[0] or 0

        c.execute(
            _safe_adapt_sql(
                "SELECT COUNT(*) FROM users WHERE user_type != 'free'",
                conn,
            )
        )
        paid_users = c.fetchone()[0] or 0

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
def get_plan_analysis(admin: int = Depends(require_admin)):
    with get_db_connection() as (conn, c):
        result = {}
        for plan in ["free", "efficiency", "professional", "enterprise"]:
            c.execute(
                _safe_adapt_sql(
                    "SELECT COUNT(*) FROM users WHERE user_type = %s", conn
                ),
                (plan,),
            )
            result[f"{plan}_users"] = c.fetchone()[0] or 0
        return result


@router.get("/active-users", response_model=dict)
def get_active_users(admin: int = Depends(require_admin)):
    with get_db_connection() as (conn, c):
        c.execute(
            _safe_adapt_sql(
                "SELECT COUNT(*) FROM users"
                " WHERE NULLIF(TRIM(last_login), '')::timestamp"
                " > NOW() - INTERVAL '1 day'",
                conn,
            )
        )
        daily = c.fetchone()[0] or 0

        c.execute(
            _safe_adapt_sql(
                "SELECT COUNT(*) FROM users"
                " WHERE NULLIF(TRIM(last_login), '')::timestamp"
                " > NOW() - INTERVAL '7 days'",
                conn,
            )
        )
        weekly = c.fetchone()[0] or 0

        return {
            "daily": daily,
            "weekly": weekly,
            "trend_daily": "+5",
            "trend_weekly": "+3",
        }


@router.get("/growth", response_model=dict)
def get_growth(admin: int = Depends(require_admin)):
    return {"current_month": 3850, "average": 4275, "predicted": 4500, "trend": "-26%"}
