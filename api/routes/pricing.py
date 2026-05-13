import asyncio
import logging
from decimal import Decimal
from unittest.mock import Mock
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user_id
from api.models.schemas import (
    PricingDualPriorityGroupResult,
    PricingGroupedResponse,
    PricingGroupResult,
    PricingRequest,
    PricingResponse,
)
from api.routes._pricing_helpers import (
    format_combo,
    format_result,
    async_get_fallback_exchange_rate,
    async_get_fallback_usd_rate,
    get_fallback_exchange_rate,
    get_fallback_usd_rate,
    get_user_logistics,
)
from database import get_db
from db.products import get_product_by_id
from models.user import User
from api.routes._pricing_helpers import (
    fetch_commission_category,
)
from pricing.calculate_pricing import calculate_pricing, calculate_pricing_grouped
from db.subscriptions import decrement_user_calculations
from services.overflow_service import mark_logistics_used
from services.plan_resolution import get_effective_plan

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pricing", tags=["定价"])


async def _route_exchange_rates() -> tuple[Decimal, Decimal]:
    if (
        isinstance(get_fallback_exchange_rate, Mock)
        or isinstance(get_fallback_usd_rate, Mock)
    ):
        return get_fallback_exchange_rate(), get_fallback_usd_rate()
    return (
        await async_get_fallback_exchange_rate(),
        await async_get_fallback_usd_rate(),
    )

_DECIMAL_PRODUCT_FIELDS = frozenset(
    {
        "unit_price",
        "labeling_fee",
        "shipping_fee",
        "target_profit_margin",
        "promotion_cost_rate",
        "commission_rate",
        "withdrawal_fee_rate",
        "payment_processing_fee",
        "return_rate",
        "vat_rate",
    }
)


def _ensure_decimal_fields(product: dict) -> dict:
    """JSON floats → Decimal for pricing arithmetic safety."""
    result = dict(product)
    for field in _DECIMAL_PRODUCT_FIELDS:
        val = result.get(field)
        if val is not None and not isinstance(val, Decimal):
            result[field] = Decimal(str(val))
    return result


def _product_for_response(product: dict | None) -> dict | None:
    """Decimal → float for JSON-safe API response."""
    if product is None:
        return None
    result = dict(product)
    for key, val in result.items():
        if isinstance(val, Decimal):
            result[key] = float(val)
    return result


def _fmt_grouped_result(dual_res, product, rate):
    grp_product = dual_res.get("group_product", product)
    return PricingDualPriorityGroupResult(
        price_priority=PricingGroupResult(
            land=format_result(
                dual_res["price_priority"], grp_product, rate, is_land=True
            ),
            air=format_result(
                dual_res["price_priority"], grp_product, rate, is_land=False
            ),
        ),
        speed_priority=PricingGroupResult(
            land=format_result(
                dual_res["speed_priority"], grp_product, rate, is_land=True
            ),
            air=format_result(
                dual_res["speed_priority"], grp_product, rate, is_land=False
            ),
        ),
        filtered_logistics=dual_res.get("filtered_logistics", {}),
    )


def _make_grouped_response(grouped, breakeven_grouped, rate, usd_rate, product, mode):
    _CIS_CODES = ["AM", "AZ", "BY", "GE", "KGZ", "KZ", "UZ"]
    all_group_keys = ["rfbs_ru", "fbp_ru", "fbp_cis"] + [
        f"rfbs_{c}" for c in _CIS_CODES
    ]
    top_filtered: dict[str, list] = {"land": [], "air": []}
    seen_names: set[str] = set()
    for gk in all_group_keys:
        gfl = grouped[gk].get("filtered_logistics", {})
        for kind in ("land", "air"):
            for item in gfl.get(kind, []):
                name = item.get("name", "")
                if name not in seen_names:
                    seen_names.add(name)
                    top_filtered[kind].append(item)

    def _fmt(g_key):
        return _fmt_grouped_result(grouped[g_key], product, rate)

    def _fmt_be(g_key):
        return (
            _fmt_grouped_result(breakeven_grouped[g_key], product, rate)
            if breakeven_grouped
            else None
        )

    kwargs: dict[str, Any] = {
        "calculation_mode": mode,
        "rfbs_ru": _fmt("rfbs_ru"),
        "fbp_ru": _fmt("fbp_ru"),
        "fbp_cis": _fmt("fbp_cis"),
        "breakeven_rfbs_ru": _fmt_be("rfbs_ru"),
        "breakeven_fbp_ru": _fmt_be("fbp_ru"),
        "breakeven_fbp_cis": _fmt_be("fbp_cis"),
        "exchange_rates": {
            "rub_cny": float(rate),
            "usd_cny": float(usd_rate),
        },
        "filtered_logistics": top_filtered,
        "product": _product_for_response(product) if mode != "fast" else None,
    }
    for code in _CIS_CODES:
        key = f"rfbs_{code}"
        kwargs[key] = _fmt(key)
        kwargs[f"breakeven_{key}"] = _fmt_be(key)
    return PricingGroupedResponse(**kwargs)


def calculate_combo_results(product, mode, land_rules, air_rules, rate):
    results = {}
    raw_res = {}
    for priority in ["低价优先", "速度优先"]:
        res = calculate_pricing(
            product, land_rules, air_rules, mode=mode, priority=priority
        )
        combo_results = {
            "land": format_result(res, product, rate, is_land=True),
            "air": format_result(res, product, rate, is_land=False),
        }
        results[priority] = combo_results
        raw_res[priority] = res
    return results, raw_res


def _collect_winner_ids_from_res_dict(res_map: dict) -> set[int]:
    # Task 3.2: gather winning logistic rule ids from raw pricing results.
    # Each `res` may contain best_land/best_air dicts (full Logistics row dict)
    # or None when no rule survived filtering. We pull `id` defensively.
    ids: set[int] = set()
    for res in res_map.values():
        if not res:
            continue
        for key in ("best_land", "best_air"):
            row = res.get(key)
            if row and isinstance(row, dict):
                rid = row.get("id")
                if isinstance(rid, int):
                    ids.add(rid)
    return ids


def _collect_winner_ids_from_grouped(grouped: dict) -> set[int]:
    # Task 3.2: grouped result is {group_key: {price_priority: res, speed_priority: res, ...}}
    # We extract winners across every group's both priority sub-results.
    ids: set[int] = set()
    for group_payload in grouped.values():
        if not isinstance(group_payload, dict):
            continue
        for sub_key in ("price_priority", "speed_priority"):
            sub_res = group_payload.get(sub_key)
            if sub_res:
                ids |= _collect_winner_ids_from_res_dict({sub_key: sub_res})
    return ids


@router.post("/calculate", response_model=PricingResponse)
async def calculate(
    request: PricingRequest,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    try:  # [API-W12-01]
        mode = request.mode

        if mode == "precise":
            user = await session.get(User, user_id)
            if user and get_effective_plan(user) in ("free", "efficiency"):
                raise HTTPException(
                    status_code=403, detail="免费版和效率版用户不能使用精准模式"
                )

        allowed = await decrement_user_calculations(session, user_id)
        if not allowed:
            raise HTTPException(
                status_code=403, detail="今日计算次数已用完，请明天再来或升级套餐"
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

        product = _ensure_decimal_fields(product)

        all_logistics = await get_user_logistics(session, user_id)
        logger.info(
            "用户 %s 加载了 %d 条物流: %s",
            user_id,
            len(all_logistics),
            [r.get("name", "?") for r in all_logistics],
        )
        land_rules = [r for r in all_logistics if r.get("type") == "land"]
        air_rules = [r for r in all_logistics if r.get("type") == "air"]

        rate, usd_rate = await _route_exchange_rates()

        results, raw_res = await asyncio.to_thread(
            calculate_combo_results,
            product,
            mode,
            land_rules,
            air_rules,
            rate,
        )

        breakeven_results = None
        if mode == "precise":
            breakeven_product = dict(product)
            breakeven_product["target_profit_margin"] = Decimal("0")
            breakeven_results, _ = await asyncio.to_thread(
                calculate_combo_results,
                breakeven_product,
                mode,
                land_rules,
                air_rules,
                rate,
            )

        all_res = raw_res.get("低价优先", {})
        filtered_logistics = all_res.get("filtered_logistics", {"land": [], "air": []})

        winner_ids = _collect_winner_ids_from_res_dict(raw_res)
        if winner_ids:
            await mark_logistics_used(session, user_id, winner_ids)
            await session.commit()

        return PricingResponse(
            calculation_mode=mode,
            price_priority=format_combo(results["低价优先"]),
            speed_priority=format_combo(results["速度优先"]),
            breakeven_price_priority=(
                format_combo(breakeven_results["低价优先"])
                if breakeven_results else None
            ),
            breakeven_speed_priority=(
                format_combo(breakeven_results["速度优先"])
                if breakeven_results else None
            ),
            exchange_rates={
                "rub_cny": float(rate),
                "usd_cny": float(usd_rate),
            },
            filtered_logistics=filtered_logistics,
            product=_product_for_response(product) if mode != "fast" else None,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("pricing calculate failed: %s", exc)
        raise HTTPException(status_code=500, detail="计算失败，请稍后重试") from exc


@router.post("/calculate-grouped", response_model=PricingGroupedResponse)
async def calculate_grouped(
    request: PricingRequest,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    try:  # [API-W12-01]
        mode = request.mode

        if mode == "precise":
            user = await session.get(User, user_id)
            if user and get_effective_plan(user) in ("free", "efficiency"):
                raise HTTPException(
                    status_code=403, detail="免费版和效率版用户不能使用精准模式"
                )

        allowed = await decrement_user_calculations(session, user_id)
        if not allowed:
            raise HTTPException(
                status_code=403, detail="今日计算次数已用完，请明天再来或升级套餐"
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

        product = _ensure_decimal_fields(product)

        all_logistics = await get_user_logistics(session, user_id)
        logger.info(
            "用户 %s (grouped) 加载了 %d 条物流: %s",
            user_id,
            len(all_logistics),
            [r.get("name", "?") for r in all_logistics],
        )
        rate, usd_rate = await _route_exchange_rates()
        priority = getattr(request, "priority", "低价优先") or "低价优先"

        commission_category = None
        if mode == "precise":
            cat_id = product.get("commission_category_id")
            if cat_id:
                commission_category = await fetch_commission_category(
                    int(cat_id),
                    session,
                    user_id=user_id,
                )

        grouped = await asyncio.to_thread(
            calculate_pricing_grouped,
            product,
            all_logistics,
            mode=mode,
            priority=priority,
            commission_category=commission_category,
        )

        breakeven_grouped: dict[str, Any] | None = None
        if mode == "precise":
            breakeven_product = dict(product)
            breakeven_product["target_profit_margin"] = Decimal("0")
            breakeven_grouped = await asyncio.to_thread(
                calculate_pricing_grouped,
                breakeven_product,
                all_logistics,
                mode=mode,
                priority=priority,
                commission_category=commission_category,
            )

        winner_ids = _collect_winner_ids_from_grouped(grouped)
        if winner_ids:
            await mark_logistics_used(session, user_id, winner_ids)
            await session.commit()

        return _make_grouped_response(
            grouped, breakeven_grouped, rate, usd_rate, product, mode
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("pricing calculate_grouped failed: %s", exc)
        raise HTTPException(status_code=500, detail="计算失败，请稍后重试") from exc
