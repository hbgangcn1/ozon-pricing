# pyright: reportPrivateUsage=false, reportUnusedImport=false
from decimal import Decimal
import logging
from collections.abc import Callable
from .vat_utils import normalize_vat_to_fraction
from .cost_filter import cost_and_filter
from .select_best import select_best_by_priority, add_unselected
from ._pricing_helpers import (
    _empty_result,
    _is_empty,
    _sanitize_filtered_logistics,
    _get_exchange_rates,
    _make_cached_cost,
    _calc_stats,
    _extract_savings,
    _error_result,
    _RESULT_HELPERS,
    _to_decimal,
)  # pyright: ignore[reportPrivateUsage]

logger = logging.getLogger(__name__)


def _notify_progress(progress_callback: Callable[[], None] | None) -> None:
    if progress_callback is None:
        return
    try:
        progress_callback()
    except Exception:
        logger.warning("SSE progress callback failed", exc_info=True)


def _run_filters(
    product,
    land_logistics,
    air_logistics,
    unit_price,
    labeling_fee,
    shipping_fee,
    rate,
    filtered_logistics,
    priority,
    mode="fast",
):
    is_fast_mode = mode == "fast"
    cached_cost = _make_cached_cost(is_fast_mode)
    all_costs_debug = []
    land_candidates = cost_and_filter(
        land_logistics,
        product,
        land_logistics,
        cached_cost,
        unit_price,
        labeling_fee,
        shipping_fee,
        rate,
        filtered_logistics,
        all_costs_debug,
    )
    air_candidates = cost_and_filter(
        air_logistics,
        product,
        land_logistics,
        cached_cost,
        unit_price,
        labeling_fee,
        shipping_fee,
        rate,
        filtered_logistics,
        all_costs_debug,
    )
    land_best = select_best_by_priority(land_candidates, priority)
    air_best = select_best_by_priority(air_candidates, priority)
    add_unselected(land_candidates, filtered_logistics["land"], land_best, priority)
    add_unselected(air_candidates, filtered_logistics["air"], air_best, priority)
    if land_best is None and air_best is None:
        logger.warning(
            "所有物流方案被淘汰: 陆运输入 %d 条, 候选 %d 条; "
            "空运输入 %d 条, 候选 %d 条; "
            "被淘汰物流: 陆运 %s, 空运 %s",
            len(land_logistics),
            len(land_candidates),
            len(air_logistics),
            len(air_candidates),
            [r.get("name", "?") for r in filtered_logistics["land"]],
            [r.get("name", "?") for r in filtered_logistics["air"]],
        )
    return (
        land_candidates,
        air_candidates,
        land_best,
        air_best,
        all_costs_debug,
    )


def _compute_stats_savings(
    land_candidates,
    land_log,
    land_cost,
    air_candidates,
    air_log,
    air_cost,
):
    land_stats = _calc_stats(land_candidates, land_log, land_cost)
    air_stats = _calc_stats(air_candidates, air_log, air_cost)
    avg_land_cost, avg_land_days, saved_land_cost, saved_land_days = _extract_savings(
        land_stats, land_log, land_cost
    )
    avg_air_cost, avg_air_days, saved_air_cost, saved_air_days = _extract_savings(
        air_stats, air_log, air_cost
    )
    return (
        land_stats,
        air_stats,
        avg_land_cost,
        avg_land_days,
        saved_land_cost,
        saved_land_days,
        avg_air_cost,
        avg_air_days,
        saved_air_cost,
        saved_air_days,
    )


def _phase1_filter_price(
    product,
    land_logistics,
    air_logistics,
    mode,
    priority,
    filtered_logistics,
    fees,
    rate,
):
    (
        land_candidates,
        air_candidates,
        land_best,
        air_best,
        all_costs_debug,
    ) = _run_filters(
        product,
        land_logistics,
        air_logistics,
        fees[0],
        fees[1],
        fees[2],
        rate,
        filtered_logistics,
        priority,
        mode,
    )
    prices_tuple = getattr(_RESULT_HELPERS, "_compute_prices")(
        land_best, air_best, product, fees[0], fees[1], fees[2], rate
    )
    (
        land_log,
        land_cost,
        land_price,
        land_commission_info,
        land_pricing_mode,
        land_payment_info,
        land_payment_fixed,
        land_debug,
        air_log,
        air_cost,
        air_price,
        air_commission_info,
        air_pricing_mode,
        air_payment_info,
        air_payment_fixed,
        air_debug,
    ) = prices_tuple
    return (
        land_candidates,
        air_candidates,
        all_costs_debug,
        land_log,
        land_cost,
        land_price,
        land_commission_info,
        land_pricing_mode,
        land_payment_info,
        land_payment_fixed,
        land_debug,
        air_log,
        air_cost,
        air_price,
        air_commission_info,
        air_pricing_mode,
        air_payment_info,
        air_payment_fixed,
        air_debug,
    )


def _apply_stats_and_build(
    land_candidates,
    land_log,
    land_cost,
    air_candidates,
    air_log,
    air_cost,
    land_price,
    land_commission_info,
    land_pricing_mode,
    land_payment_info,
    land_payment_fixed,
    land_debug,
    air_price,
    air_commission_info,
    air_pricing_mode,
    air_payment_info,
    air_payment_fixed,
    air_debug,
    land_expected_profit,
    land_profit_margin,
    air_expected_profit,
    air_profit_margin,
    product,
    all_costs_debug,
    filtered_logistics,
):
    (
        land_stats,
        air_stats,
        avg_land_cost,
        avg_land_days,
        saved_land_cost,
        saved_land_days,
        avg_air_cost,
        avg_air_days,
        saved_air_cost,
        saved_air_days,
    ) = _compute_stats_savings(
        land_candidates,
        land_log,
        land_cost,
        air_candidates,
        air_log,
        air_cost,
    )
    return getattr(_RESULT_HELPERS, "_build_result")(
        land_log,
        land_cost,
        land_price,
        land_commission_info,
        land_pricing_mode,
        land_payment_info,
        land_payment_fixed,
        land_debug,
        land_stats,
        air_log,
        air_cost,
        air_price,
        air_commission_info,
        air_pricing_mode,
        air_payment_info,
        air_payment_fixed,
        air_debug,
        air_stats,
        land_expected_profit,
        land_profit_margin,
        air_expected_profit,
        air_profit_margin,
        product,
        all_costs_debug,
        filtered_logistics,
        avg_land_cost,
        avg_land_days,
        saved_land_cost,
        saved_land_days,
        avg_air_cost,
        avg_air_days,
        saved_air_cost,
        saved_air_days,
    )


def _phase2_profit_build(
    land_candidates,
    air_candidates,
    all_costs_debug,
    land_log,
    land_cost,
    land_price,
    land_commission_info,
    land_pricing_mode,
    land_payment_info,
    land_payment_fixed,
    land_debug,
    air_log,
    air_cost,
    air_price,
    air_commission_info,
    air_pricing_mode,
    air_payment_info,
    air_payment_fixed,
    air_debug,
    fees,
    rate,
    product,
    filtered_logistics,
):
    (
        land_expected_profit,
        land_profit_margin,
        air_expected_profit,
        air_profit_margin,
    ) = getattr(_RESULT_HELPERS, "_compute_profits")(
        land_price,
        land_cost,
        land_commission_info,
        land_payment_info,
        land_payment_fixed,
        land_pricing_mode,
        land_debug,
        air_price,
        air_cost,
        air_commission_info,
        air_payment_info,
        air_payment_fixed,
        air_pricing_mode,
        air_debug,
        fees[0],
        fees[1],
        fees[2],
        rate,
        product,
    )
    return _apply_stats_and_build(
        land_candidates,
        land_log,
        land_cost,
        air_candidates,
        air_log,
        air_cost,
        land_price,
        land_commission_info,
        land_pricing_mode,
        land_payment_info,
        land_payment_fixed,
        land_debug,
        air_price,
        air_commission_info,
        air_pricing_mode,
        air_payment_info,
        air_payment_fixed,
        air_debug,
        land_expected_profit,
        land_profit_margin,
        air_expected_profit,
        air_profit_margin,
        product,
        all_costs_debug,
        filtered_logistics,
    )


def _run_calculation(
    product,
    land_logistics,
    air_logistics,
    mode,
    priority,
    filtered_logistics,
):
    product = dict(product.items()) if hasattr(product, "items") else product
    # [PRC-W12R2-01] Normalize VAT once at the pricing pipeline boundary.
    product["vat_rate"] = normalize_vat_to_fraction(product.get("vat_rate", Decimal("0")))
    unit_price = _to_decimal(product.get("unit_price") or Decimal("0"))
    labeling_fee = _to_decimal(product.get("labeling_fee") or Decimal("0"))
    shipping_fee = _to_decimal(product.get("shipping_fee") or Decimal("0"))
    fees = (unit_price, labeling_fee, shipping_fee)
    rate, _ = _get_exchange_rates()
    phase1 = _phase1_filter_price(
        product,
        land_logistics,
        air_logistics,
        mode,
        priority,
        filtered_logistics,
        fees,
        rate,
    )
    return _phase2_profit_build(*phase1, fees, rate, product, filtered_logistics)


def calculate_pricing(
    product: dict,
    land_logistics: list,
    air_logistics: list,
    mode: str = "fast",
    priority: str = "低价优先",
    progress_callback: Callable[[], None] | None = None,
) -> dict:
    filtered_logistics = {"land": [], "air": []}
    try:
        _notify_progress(progress_callback)
        if product is None or land_logistics is None or air_logistics is None:
            return _empty_result(filtered_logistics)
        if not hasattr(product, "get"):
            product.get("test")
        if _is_empty(land_logistics) and _is_empty(air_logistics):
            return _empty_result(filtered_logistics)
        _notify_progress(progress_callback)
        result = _run_calculation(
            product,
            land_logistics,
            air_logistics,
            mode,
            priority,
            filtered_logistics,
        )
        result["filtered_logistics"] = _sanitize_filtered_logistics(
            result.get("filtered_logistics", filtered_logistics),
            land_logistics,
            air_logistics,
        )
        _notify_progress(progress_callback)
        return result
    except ZeroDivisionError:
        raise
    except AttributeError:
        raise
    except (ValueError, TypeError, KeyError) as exc:
        logger.warning("计算定价时发生可恢复错误: %s", exc, exc_info=True)
        return _error_result(product)


# Re-export for backward compatibility with existing imports
from .grouped_pricing import (  # noqa: E402,F401
    calculate_pricing_grouped,
    _estimate_and_select_rate,
    _estimate_price_rub,
)  # pyright: ignore[reportPrivateUsage,reportUnusedImport]
