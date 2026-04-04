from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional

from db_utils import get_db_connection, _safe_adapt_sql
from api.models.schemas import MessageResponse
from api.dependencies import get_current_user_id

router = APIRouter(prefix="/api/subscriptions", tags=["订阅"])


class PlanResponse(BaseModel):
    id: int
    code: str
    name: str
    display_price_month: float
    display_price_year: float
    actual_price_month: float
    actual_price_year: float
    test_price_month: float
    test_price_year: float
    calc_limit: int
    logistics_limit: int
    sort: int
    status: bool
    description: str
    features: List[str]


class SubscriptionResponse(BaseModel):
    plan_code: str
    calc_limit: int
    logistics_limit: int
    expired_at: Optional[str] = None


@router.get("/plans", response_model=List[PlanResponse])
async def get_plans():
    with get_db_connection() as (conn, c):
        sql_raw = "SELECT * FROM plans WHERE status = true ORDER BY sort"
        sql = _safe_adapt_sql(sql_raw, conn)
        try:
            c.execute(sql)
        except Exception:
            return []
        columns = [desc[0] for desc in c.description]
        plans = []
        for row in c.fetchall():
            plan = dict(zip(columns, row))
            features = plan.get("features", "")
            if isinstance(features, str):
                features = features.split(",") if features else []
            plans.append(
                PlanResponse(
                    id=plan["id"],
                    code=plan["code"],
                    name=plan["name"],
                    display_price_month=plan.get("display_price_month", 0),
                    display_price_year=plan.get("display_price_year", 0),
                    actual_price_month=plan.get("actual_price_month", 0),
                    actual_price_year=plan.get("actual_price_year", 0),
                    test_price_month=plan.get("test_price_month", 0),
                    test_price_year=plan.get("test_price_year", 0),
                    calc_limit=plan.get("calc_limit", -1),
                    logistics_limit=plan.get("logistics_limit", 1),
                    sort=plan.get("sort", 0),
                    status=plan.get("status", True),
                    description=plan.get("description", ""),
                    features=features,
                )
            )
        return plans


@router.get("/current", response_model=SubscriptionResponse)
async def get_current_subscription(user_id: int = Depends(get_current_user_id)):
    with get_db_connection() as (conn, c):
        sql_raw = """
            SELECT u.user_type, p.calc_limit, p.logistics_limit,
                   u.subscription_expires
            FROM users u
            LEFT JOIN plans p ON u.user_type = p.plan_code
            WHERE u.id = %s
        """
        sql = _safe_adapt_sql(sql_raw, conn)
        c.execute(sql, (user_id,))
        row = c.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="用户不存在")
        return SubscriptionResponse(
            plan_code=row[0] or "free",
            calc_limit=row[1] if row[1] is not None else -1,
            logistics_limit=row[2] if row[2] is not None else 1,
            expired_at=str(row[3]) if row[3] else None,
        )
