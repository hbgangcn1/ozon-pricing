from functools import lru_cache
from .logistic_cost import calculate_logistic_cost
from .cost_filter import cost_and_filter
from .select_best import select_best_by_priority, add_unselected
from ._result_helpers import _compute_prices, _compute_profits, _build_result


def _empty_result(filtered_logistics=None):
    base = {
        "best_land": None,
        "best_air": None,
        "land_price": None,
        "air_price": None,
        "land_cost": None,
        "air_cost": None,
        "suggested_price": None,
        "expected_profit": 0,
        "profit_margin": 0,
        "land_stats": None,
        "air_stats": None,
        "all_costs_debug": [],
        "land_debug": [],
        "air_debug": [],
        "avg_land_cost": 0,
        "avg_land_days": 0,
        "avg_air_cost": 0,
        "avg_air_days": 0,
        "saved_land_cost": 0,
        "saved_land_days": 0,
        "saved_air_cost": 0,
        "saved_air_days": 0,
    }
    if filtered_logistics is not None:
        base["filtered_logistics"] = filtered_logistics
    return base


def _is_empty(logistics):
    if hasattr(logistics, "empty"):
        return logistics.empty
    return not logistics


def _get_exchange_rates():
    try:
        from exchange_service import (
            get_fallback_exchange_rate,
            get_fallback_usd_rate,
        )
    except ImportError:

        def get_fallback_exchange_rate():
            return 0.0904

        def get_fallback_usd_rate():
            return 7.2

    return get_fallback_exchange_rate(), get_fallback_usd_rate()


def _make_cached_cost(is_fast_mode):
    @lru_cache(maxsize=256)
    def cached_cost(log_tuple, prod_tuple):
        return calculate_logistic_cost(dict(log_tuple), dict(prod_tuple), is_fast_mode)

    return cached_cost


def _calc_stats(candidates, best_log, best_cost):
    if not candidates:
        return None
    costs = [c for _, c in candidates]
    times = []
    for log_dict, _ in candidates:
        mn = log_dict.get("min_days", 0)
        mx = log_dict.get("max_days", 0)
        times.append((mn + mx) / 2)
    avg_cost = sum(costs) / len(costs)
    avg_time = sum(times) / len(times)
    cost_saving = (
        ((avg_cost - best_cost) / avg_cost * 100) if best_cost and avg_cost > 0 else 0
    )
    best_avg_time = (
        ((best_log.get("min_days", 0) + best_log.get("max_days", 0)) / 2)
        if best_log
        else 0
    )
    return {
        "avg_cost": avg_cost,
        "cost_saving": cost_saving,
        "avg_time": avg_time,
        "time_saving": avg_time - best_avg_time,
    }


def _extract_savings(stats, best_log, best_cost):
    if not stats:
        return 0, 0, 0, 0
    avg_cost = stats["avg_cost"]
    avg_days = stats["avg_time"]
    saved_cost = avg_cost - best_cost if best_cost else 0
    saved_days = avg_days - (
        (best_log.get("min_days", 0) + best_log.get("max_days", 0)) / 2
        if best_log
        else 0
    )
    return avg_cost, avg_days, saved_cost, saved_days


def _error_result(product):
    return {
        "best_land": None,
        "best_air": None,
        "land_price": None,
        "air_price": None,
        "land_cost": None,
        "air_cost": None,
        "suggested_price": None,
        "expected_profit": 0,
        "land_expected_profit": 0,
        "air_expected_profit": 0,
        "profit_margin": 0,
        "land_stats": None,
        "air_stats": None,
        "all_costs_debug": [],
        "land_debug": [],
        "air_debug": [],
        "land_pricing_mode": None,
        "air_pricing_mode": None,
        "land_commission_info": None,
        "air_commission_info": None,
        "land_payment_info": None,
        "air_payment_info": None,
        "land_payment_fixed": False,
        "air_payment_fixed": False,
        "product_info": product,
        "avg_land_cost": 0,
        "avg_land_days": 0,
        "avg_air_cost": 0,
        "avg_air_days": 0,
        "saved_land_cost": 0,
        "saved_land_days": 0,
        "saved_air_cost": 0,
        "saved_air_days": 0,
    }


def _run_filters(
    product,
    land_logistics,
    air_logistics,
    unit_price,
    labeling_fee,
    shipping_fee,
    rate,
    usd_rate,
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
        usd_rate,
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
        usd_rate,
        filtered_logistics,
        all_costs_debug,
    )
    land_best = select_best_by_priority(land_candidates, priority)
    air_best = select_best_by_priority(air_candidates, priority)
    add_unselected(land_candidates, filtered_logistics["land"])
    add_unselected(air_candidates, filtered_logistics["air"])
    return land_candidates, air_candidates, land_best, air_best, all_costs_debug


def _compute_stats_savings(
    land_candidates, land_log, land_cost, air_candidates, air_log, air_cost
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
    usd_rate,
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
        *fees,
        rate,
        usd_rate,
        filtered_logistics,
        priority,
        mode,
    )
    prices_tuple = _compute_prices(land_best, air_best, product, *fees, rate)
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
        _,
    ) = _compute_profits(
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
        *fees,
        rate,
        product,
    )
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
        land_candidates, land_log, land_cost, air_candidates, air_log, air_cost
    )
    return _build_result(
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


def _run_calculation(
    product, land_logistics, air_logistics, mode, priority, filtered_logistics
):
    unit_price = float(product.get("unit_price", 0))
    labeling_fee = float(product.get("labeling_fee", 0))
    shipping_fee = float(product.get("shipping_fee", 0))
    fees = (unit_price, labeling_fee, shipping_fee)
    rate, usd_rate = _get_exchange_rates()
    phase1 = _phase1_filter_price(
        product,
        land_logistics,
        air_logistics,
        mode,
        priority,
        filtered_logistics,
        fees,
        rate,
        usd_rate,
    )
    return _phase2_profit_build(*phase1, fees, rate, product, filtered_logistics)


def calculate_pricing(
    product, land_logistics, air_logistics, mode="fast", priority="低价优先"
):
    filtered_logistics = {"land": [], "air": []}
    try:
        if product is None or land_logistics is None or air_logistics is None:
            return _empty_result(filtered_logistics)
        if not hasattr(product, "get"):
            product.get("test")
        if _is_empty(land_logistics) and _is_empty(air_logistics):
            return _empty_result()
        return _run_calculation(
            product, land_logistics, air_logistics, mode, priority, filtered_logistics
        )
    except ZeroDivisionError:
        raise
    except AttributeError:
        raise
    except (ValueError, TypeError, KeyError) as e:
        print(f"计算定价时发生错误: {e}")
        return _error_result(product)
