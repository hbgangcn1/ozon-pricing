from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer

from logic import calculate_pricing
from db_utils import get_product_by_id, get_db_connection, _safe_adapt_sql
from api.models.schemas import PricingRequest, PricingResponse

router = APIRouter(prefix="/api/pricing", tags=["定价"])
security = HTTPBearer()


def get_current_user_id(api_key: str = Depends(security)) -> int:
    return 1


def get_user_logistics(user_id, logistics_type=None):
    with get_db_connection() as (conn, c):
        if logistics_type:
            sql_raw = "SELECT * FROM logistics WHERE user_id = %s AND type = %s"
            sql = _safe_adapt_sql(sql_raw, conn)
            c.execute(sql, (user_id, logistics_type))
        else:
            sql_raw = "SELECT * FROM logistics WHERE user_id = %s"
            sql = _safe_adapt_sql(sql_raw, conn)
            c.execute(sql, (user_id,))
        columns = [desc[0] for desc in c.description]
        return [dict(zip(columns, row)) for row in c.fetchall()]


@router.post("/calculate", response_model=PricingResponse)
async def calculate(product_id: int, logistics_id: int, mode: str = "fast"):
    user_id = get_current_user_id()

    product = get_product_by_id(product_id, user_id)
    if not product:
        raise HTTPException(status_code=404, detail="产品不存在")

    with get_db_connection() as (conn, c):
        sql_raw = "SELECT id FROM logistics WHERE id = %s AND user_id = %s"
        sql = _safe_adapt_sql(sql_raw, conn)
        c.execute(sql, (logistics_id, user_id))
        if not c.fetchone():
            raise HTTPException(status_code=404, detail="物流规则不存在")

    land_logistics = get_user_logistics(user_id, "land")
    air_logistics = get_user_logistics(user_id, "air")

    result = calculate_pricing(product, land_logistics, air_logistics)

    return PricingResponse(
        final_price=result.get("suggested_price", 0),
        currency="RUB",
        logistics_cost=result.get("land_cost", 0) or result.get("air_cost", 0),
        storage_cost=0,
        packaging_cost=0,
        other_costs=0,
        exchange_rate=1.0,
        calculation_mode=mode,
    )
