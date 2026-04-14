import decimal
import logging
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user_id
from api.models.schemas import (
    BreakdownItem,
    PricingComboResult,
    PricingDualPriorityGroupResult,
    PricingGroupedResponse,
    PricingGroupResult,
    PricingRequest,
    PricingResponse,
    PricingResultItem,
)
from database import get_db
from db.products import get_product_by_id
from models.logistics import Logistics
from models.user import User
from pricing.calculate_pricing import calculate_pricing, calculate_pricing_grouped
from pricing.commission import fetch_commission_category

logger = logging.getLogger(__name__)

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

    agency_cny = round(commission_rub * rate, 2) if commission_rub is not None else 0

    def to_rate(val):
        return (
            val / 100 if (val is not None and val >= 1) else (0 if val is None else val)
        )

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
    _unavailable = PricingResultItem(
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
    if not res:
        return _unavailable

    price = res.get("land_price") if is_land else res.get("air_price")
    if price is None:
        return _unavailable

    cost = res.get("land_cost") if is_land else res.get("air_cost")
    best_log = res.get("best_land") if is_land else res.get("best_air")
    expected_profit = res.get(
        "land_expected_profit" if is_land else "air_expected_profit", 0
    )
    profit_margin = res.get("land_profit_margin" if is_land else "air_profit_margin", 0)
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
        logistics_cost=round(cost, 4) if cost is not None else 0,
        days_min=best_log.get("min_days", 0) if best_log else 0,
        days_max=best_log.get("max_days", 0) if best_log else 0,
        priority_group=best_log.get("priority_group", "") if best_log else "",
        pricing_mode=pricing_mode,
        profit_cny=round(expected_profit, 2),
        profit_margin_pct=round(profit_margin, 2),
        avg_cost=round(avg_cost, 4) if avg_cost is not None else 0,
        saved_cost=round(saved_cost, 4) if saved_cost is not None else 0,
        avg_days=round(avg_days, 2) if avg_days is not None else 0,
        saved_days=round(saved_days, 2) if saved_days is not None else 0,
        breakdown=build_breakdown(
            product,
            0 if cost is None else cost,
            price,
            0 if commission_rub is None else commission_rub,
            0 if payment_rub is None else payment_rub,
            payment_fixed,
            expected_profit,
            profit_margin,
            rate,
        ),
    )


def format_combo(combo_results):
    return PricingComboResult(
        land=combo_results.get("land", PricingResultItem()),
        air=combo_results.get("air", PricingResultItem()),
    )


def calculate_combo_results(product, mode, land_rules, air_rules, rate):
    results = {}
    for priority in ["低价优先", "速度优先"]:
        res = calculate_pricing(
            product, land_rules, air_rules, mode=mode, priority=priority
        )
        combo_results = {
            "land": format_result(res, product, rate, is_land=True),
            "air": format_result(res, product, rate, is_land=False),
        }
        results[priority] = combo_results
    return results


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

    product = cast(dict[str, Any], convert_decimals(product))

    all_logistics = cast(
        list[dict[str, Any]],
        convert_decimals(await get_user_logistics(session, user_id)),
    )
    logger.info(
        "用户 %s 加载了 %d 条物流: %s",
        user_id,
        len(all_logistics),
        [r.get("name", "?") for r in all_logistics],
    )
    land_rules = [r for r in all_logistics if r.get("type") == "land"]
    air_rules = [r for r in all_logistics if r.get("type") == "air"]

    rate = get_fallback_exchange_rate()

    results = calculate_combo_results(
        product,
        mode,
        land_rules,
        air_rules,
        rate,
    )

    breakeven_results = None
    if mode == "precise":
        breakeven_product = dict(product)
        breakeven_product["target_profit_margin"] = 0
        breakeven_results = calculate_combo_results(
            breakeven_product,
            mode,
            land_rules,
            air_rules,
            rate,
        )

    all_res = calculate_pricing(
        product, land_rules, air_rules, mode=mode, priority="低价优先"
    )
    filtered_logistics = all_res.get("filtered_logistics", {"land": [], "air": []})

    return PricingResponse(
        calculation_mode=mode,
        price_priority=format_combo(results["低价优先"]),
        speed_priority=format_combo(results["速度优先"]),
        breakeven_price_priority=(
            format_combo(breakeven_results["低价优先"]) if breakeven_results else None
        ),
        breakeven_speed_priority=(
            format_combo(breakeven_results["速度优先"]) if breakeven_results else None
        ),
        exchange_rates={
            "rub_cny": rate,
            "usd_cny": get_fallback_usd_rate(),
        },
        filtered_logistics=filtered_logistics,
        product=product if mode != "fast" else None,
    )


@router.post("/calculate-grouped", response_model=PricingGroupedResponse)
async def calculate_grouped(
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

    product = cast(dict[str, Any], convert_decimals(product))
    all_logistics = cast(
        list[dict[str, Any]],
        convert_decimals(await get_user_logistics(session, user_id)),
    )
    logger.info(
        "用户 %s (grouped) 加载了 %d 条物流: %s",
        user_id,
        len(all_logistics),
        [r.get("name", "?") for r in all_logistics],
    )
    rate = get_fallback_exchange_rate()

    priority = getattr(request, "priority", "低价优先") or "低价优先"

    commission_category = None
    if mode == "precise":
        cat_id = product.get("commission_category_id")
        if cat_id:
            commission_category = await fetch_commission_category(
                int(cat_id),
                session,
            )

    grouped = cast(
        dict[str, Any],
        convert_decimals(
            calculate_pricing_grouped(
                product,
                all_logistics,
                mode=mode,
                priority=priority,
                commission_category=commission_category,
            )
        ),
    )

    breakeven_grouped: dict[str, Any] | None = None
    if mode == "precise":
        breakeven_product = dict(product)
        breakeven_product["target_profit_margin"] = 0
        breakeven_grouped = cast(
            dict[str, Any],
            convert_decimals(
                calculate_pricing_grouped(
                    breakeven_product,
                    all_logistics,
                    mode=mode,
                    priority=priority,
                    commission_category=commission_category,
                )
            ),
        )

    def _fmt_group(dual_res):
        return PricingDualPriorityGroupResult(
            price_priority=PricingGroupResult(
                land=format_result(
                    dual_res["price_priority"],
                    product,
                    rate,
                    is_land=True,
                ),
                air=format_result(
                    dual_res["price_priority"],
                    product,
                    rate,
                    is_land=False,
                ),
            ),
            speed_priority=PricingGroupResult(
                land=format_result(
                    dual_res["speed_priority"],
                    product,
                    rate,
                    is_land=True,
                ),
                air=format_result(
                    dual_res["speed_priority"],
                    product,
                    rate,
                    is_land=False,
                ),
            ),
            filtered_logistics=dual_res.get("filtered_logistics", {}),
        )

    _CIS_CODES = ["AZ", "BY", "GE", "KGZ", "KZ", "UZ"]

    all_group_keys = ["rfbs_ru", "fbp_ru", "fbp_cis"] + [
        f"rfbs_{c}" for c in _CIS_CODES
    ]
    top_filtered = {"land": [], "air": []}
    seen_names: set[str] = set()
    for gk in all_group_keys:
        gfl = grouped[gk].get("filtered_logistics", {})
        for kind in ("land", "air"):
            for item in gfl.get(kind, []):
                name = item.get("name", "")
                if name not in seen_names:
                    seen_names.add(name)
                    top_filtered[kind].append(item)

    resp_kwargs = {
        "calculation_mode": mode,
        "rfbs_ru": _fmt_group(grouped["rfbs_ru"]),
        "fbp_ru": _fmt_group(grouped["fbp_ru"]),
        "fbp_cis": _fmt_group(grouped["fbp_cis"]),
        "breakeven_rfbs_ru": (
            _fmt_group(breakeven_grouped["rfbs_ru"]) if breakeven_grouped else None
        ),
        "breakeven_fbp_ru": (
            _fmt_group(breakeven_grouped["fbp_ru"]) if breakeven_grouped else None
        ),
        "breakeven_fbp_cis": (
            _fmt_group(breakeven_grouped["fbp_cis"]) if breakeven_grouped else None
        ),
        "exchange_rates": {
            "rub_cny": rate,
            "usd_cny": get_fallback_usd_rate(),
        },
        "filtered_logistics": top_filtered,
        "product": product if mode != "fast" else None,
    }
    for code in _CIS_CODES:
        key = f"rfbs_{code}"
        resp_kwargs[key] = _fmt_group(grouped[key])
        resp_kwargs[f"breakeven_{key}"] = (
            _fmt_group(breakeven_grouped[key]) if breakeven_grouped else None
        )
    return PricingGroupedResponse(**resp_kwargs)


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
