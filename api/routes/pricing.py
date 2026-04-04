from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
import decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from logic import calculate_pricing
from models.logistics import Logistics
from models.user import User
from db.products import get_product_by_id
from api.models.schemas import (
    PricingRequest,
    PricingResponse,
    PricingComboResult,
    PricingResultItem,
    BreakdownItem,
)
from api.dependencies import get_current_user_id

router = APIRouter(prefix="/api/pricing", tags=["定价"])


def convert_decimals(obj):
    if isinstance(obj, dict):
        return {k: convert_decimals(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_decimals(v) for v in obj]
    elif isinstance(obj, decimal.Decimal):
        return float(obj)
    return obj


async def get_user_logistics(session: AsyncSession, user_id, logistics_type=None):
    stmt = select(Logistics).where(
        Logistics.user_id == user_id,
        Logistics.is_active == 1,
    )
    if logistics_type:
        stmt = stmt.where(Logistics.type == logistics_type)
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [{c.key: getattr(row, c.key) for c in row.__table__.columns} for row in rows]


def get_fallback_exchange_rate():
    try:
        from exchange_service import get_fallback_exchange_rate as _get_rate

        return round(_get_rate(), 4)
    except ImportError:
        return round(0.0904, 4)


def get_fallback_usd_rate():
    try:
        from exchange_service import get_fallback_usd_rate as _get_rate

        return round(_get_rate(), 4)
    except ImportError:
        return round(7.2, 4)


def build_breakdown(
    product,
    logistics_cost_cny,
    price_cny,
    commission_rub,
    payment_rub,
    payment_fixed,
    expected_profit,
    profit_margin_pct,
    rate,
):
    unit_price_cny = product.get("unit_price", 0)
    labeling_fee_cny = product.get("labeling_fee", 0)
    shipping_fee_cny = product.get("shipping_fee", 0)

    agency_cny = round(commission_rub * rate, 2) if commission_rub else 0

    def to_rate(val):
        return val / 100 if (val is not None and val >= 1) else (val or 0)

    promotion_rate = to_rate(product.get("promotion_cost_rate", 0))
    commission_rate = to_rate(product.get("commission_rate", 0))
    withdrawal_rate = to_rate(product.get("withdrawal_fee_rate", 0))
    payment_rate = to_rate(product.get("payment_processing_fee", 0))
    return_rate = to_rate(product.get("return_rate", 0))
    vat_rate = to_rate(product.get("vat_rate", 0))

    promotion_cny = (
        round(price_cny * promotion_rate, 2) if promotion_rate is not None else 0
    )
    commission_cny = (
        round(price_cny * commission_rate, 2) if commission_rate is not None else 0
    )
    withdrawal_cny = (
        round(price_cny * withdrawal_rate, 2) if withdrawal_rate is not None else 0
    )
    if payment_fixed:
        payment_cny = round(10 * rate, 2)
    else:
        payment_cny = (
            round(price_cny * payment_rate, 2) if payment_rate is not None else 0
        )
    return_loss_cny = (
        round(price_cny * return_rate, 2) if return_rate is not None else 0
    )
    vat_cny = round(price_cny * vat_rate, 2) if vat_rate is not None else 0

    items = [
        ("进货单价", unit_price_cny, "#FF6B6B"),
        ("贴标费用", labeling_fee_cny, "#4ECDC4"),
        ("供货运费", shipping_fee_cny, "#45B7D1"),
        ("物流运费", logistics_cost_cny, "#FFA07A"),
        ("代理费", agency_cny, "#98D8C8"),
        ("推广费", promotion_cny, "#F7DC6F"),
        ("佣金", commission_cny, "#BB8FCE"),
        ("提现费", withdrawal_cny, "#85C1E9"),
        ("收单费", payment_cny, "#F8B739"),
        ("退货损失", return_loss_cny, "#EB984E"),
        ("增值税", vat_cny, "#A569BD"),
        ("运营利润", round(expected_profit, 2), "#52BE80"),
    ]
    return [
        BreakdownItem(label=label, value=round(val, 2), color=col)
        for label, val, col in items
        if abs(val) > 0.01 or label == "运营利润"
    ]


def format_result(res, product, rate, is_land=True):
    if not res or not res.get("suggested_price"):
        return PricingResultItem(
            is_available=False,
            price_cny=0,
            price_rub=0,
            logistics_name="",
            logistics_cost=0,
            days_min=0,
            days_max=0,
            profit_cny=0,
            profit_margin_pct=0,
            priority_group="",
            pricing_mode="",
            avg_cost=0,
            saved_cost=0,
            avg_days=0,
            saved_days=0,
            breakdown=[],
        )

    cost = res.get("land_cost") if is_land else res.get("air_cost")
    best_log = res.get("best_land") if is_land else res.get("best_air")
    price = res.get("suggested_price", 0)
    expected_profit = res.get(
        "land_expected_profit" if is_land else "air_expected_profit", 0
    )
    profit_margin = res.get("profit_margin", 0)
    pricing_mode = res.get("land_pricing_mode" if is_land else "air_pricing_mode", "")
    commission_rub = res.get(
        "land_commission_info" if is_land else "air_commission_info", 0
    )
    payment_rub = res.get("land_payment_info" if is_land else "air_payment_info", 0)
    payment_fixed = res.get(
        "land_payment_fixed" if is_land else "air_payment_fixed", False
    )
    avg_cost = res.get("avg_land_cost" if is_land else "avg_air_cost", 0)
    avg_days = res.get("avg_land_days" if is_land else "avg_air_days", 0)
    saved_cost = res.get("saved_land_cost" if is_land else "saved_air_cost", 0)
    saved_days = res.get("saved_land_days" if is_land else "saved_air_days", 0)

    return PricingResultItem(
        is_available=True,
        price_cny=price,
        price_rub=round(price / rate, 2) if rate else 0,
        logistics_name=best_log.get("name", "") if best_log else "",
        logistics_cost=round(cost, 4) if cost else 0,
        days_min=best_log.get("min_days", 0) if best_log else 0,
        days_max=best_log.get("max_days", 0) if best_log else 0,
        priority_group=best_log.get("priority_group", "") if best_log else "",
        pricing_mode=pricing_mode,
        profit_cny=round(expected_profit, 2),
        profit_margin_pct=round(profit_margin, 2),
        avg_cost=round(avg_cost, 4) if avg_cost else 0,
        saved_cost=round(saved_cost, 4) if saved_cost else 0,
        avg_days=round(avg_days, 2) if avg_days else 0,
        saved_days=round(saved_days, 2) if saved_days else 0,
        breakdown=build_breakdown(
            product,
            cost or 0,
            price,
            commission_rub or 0,
            payment_rub or 0,
            payment_fixed,
            expected_profit,
            profit_margin,
            rate,
        ),
    )


def format_combo(combo_results):
    return PricingComboResult(
        land_pickup=combo_results.get("land_pickup", PricingResultItem()),
        land_home=combo_results.get("land_home", PricingResultItem()),
        air_pickup=combo_results.get("air_pickup", PricingResultItem()),
        air_home=combo_results.get("air_home", PricingResultItem()),
    )


@router.post("/calculate", response_model=PricingResponse)
async def calculate(
    request: PricingRequest,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    mode = request.mode

    if mode == "precise":
        user = await session.get(User, user_id)
        if user and user.user_type in ("free", "efficiency"):
            raise HTTPException(
                status_code=403, detail="免费版和效率版用户不能使用精准模式"
            )

    if mode == "fast":
        product = request.product_data or {}
    else:
        if request.product_data:
            product = request.product_data
        elif request.product_id:
            product = await get_product_by_id(session, request.product_id, user_id)
            if not product:
                raise HTTPException(status_code=404, detail="产品不存在")
        else:
            raise HTTPException(
                status_code=400,
                detail="请提供产品数据或选择已有产品",
            )

    product = convert_decimals(product)

    all_logistics = convert_decimals(await get_user_logistics(session, user_id))
    land_rules = [r for r in all_logistics if r.get("type") == "land"]
    air_rules = [r for r in all_logistics if r.get("type") == "air"]

    def is_pickup(r):
        return r.get("delivery_method") in ("pickup", "pickup_point")

    def is_home(r):
        return r.get("delivery_method") == "door"

    land_pickup = [r for r in land_rules if is_pickup(r)]
    land_home = [r for r in land_rules if is_home(r)]
    air_pickup = [r for r in air_rules if is_pickup(r)]
    air_home = [r for r in air_rules if is_home(r)]

    rate = get_fallback_exchange_rate()

    results = {}
    for priority in ["低价优先", "速度优先"]:
        combos = {
            "land_pickup": (land_pickup, []),
            "land_home": (land_home, []),
            "air_pickup": ([], air_pickup),
            "air_home": ([], air_home),
        }
        combo_results = {}
        for combo_key, (land_list, air_list) in combos.items():
            res = calculate_pricing(
                product, land_list, air_list, mode=mode, priority=priority
            )
            combo_results[combo_key] = format_result(
                res, product, rate, is_land=bool(land_list)
            )
        results[priority] = combo_results

    all_res = calculate_pricing(
        product, land_rules, air_rules, mode=mode, priority="低价优先"
    )
    filtered_logistics = all_res.get("filtered_logistics", {"land": [], "air": []})

    return PricingResponse(
        calculation_mode=mode,
        price_priority=format_combo(results["低价优先"]),
        speed_priority=format_combo(results["速度优先"]),
        exchange_rates={
            "rub_cny": rate,
            "usd_cny": get_fallback_usd_rate(),
        },
        filtered_logistics=filtered_logistics,
        product=product if mode == "detailed" else None,
    )


@router.get("/progress")
async def pricing_progress(user_id: int = Depends(get_current_user_id)):
    async def event_generator():
        import asyncio
        import json

        progress_data = [
            {"progress": 0, "message": "开始计算"},
            {"progress": 20, "message": "正在筛选可用物流"},
            {"progress": 50, "message": "计算陆运组合"},
            {"progress": 80, "message": "计算空运组合"},
            {"progress": 100, "message": "计算完成"},
        ]

        for data in progress_data:
            yield f"data: {json.dumps(data)}\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
