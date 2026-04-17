from decimal import Decimal
import logging
from functools import lru_cache
from .logistic_cost import calculate_logistic_cost

logger = logging.getLogger(__name__)

_RESULT_HELPERS = __import__(f"{__package__}._result_helpers", fromlist=["*"])
_FBP_ELIMINATED_REASON = "该物流无法覆盖更高成本"


def _to_decimal(value):
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


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


def _collect_input_names(logistics):
    if hasattr(logistics, "to_dict"):
        logistics = logistics.to_dict("records")
    names = set()
    for item in logistics or []:
        if hasattr(item, "to_dict"):
            item = item.to_dict()
        elif hasattr(item, "items"):
            item = dict(item)
        name = item.get("name") if hasattr(item, "get") else None
        if name:
            names.add(name)
    return names


def _sanitize_filtered_logistics(filtered_logistics, land_logistics, air_logistics):
    allowed_names = {
        "land": _collect_input_names(land_logistics),
        "air": _collect_input_names(air_logistics),
    }
    sanitized = {"land": [], "air": []}
    for kind in ("land", "air"):
        for item in filtered_logistics.get(kind, []):
            name = item.get("name") if hasattr(item, "get") else None
            if name in allowed_names[kind]:
                sanitized[kind].append(item)
    return sanitized


def _get_exchange_rates():
    try:
        from exchange_service import (
            get_fallback_exchange_rate,
            get_fallback_usd_rate,
        )
    except ImportError:

        def get_fallback_exchange_rate():
            return Decimal("0.0904")

        def get_fallback_usd_rate():
            return Decimal("7.2")

    return _to_decimal(get_fallback_exchange_rate()), _to_decimal(
        get_fallback_usd_rate()
    )


def _make_cached_cost(is_fast_mode):
    @lru_cache(maxsize=256)
    def cached_cost(log_tuple, prod_tuple):
        return calculate_logistic_cost(dict(log_tuple), dict(prod_tuple), is_fast_mode)

    return cached_cost


def _calc_stats(candidates, best_log, best_cost):
    if not candidates:
        return None
    all_costs = (
        [best_cost] + [c for _, c in candidates]
        if best_cost
        else [c for _, c in candidates]
    )
    best_avg_time = (
        ((best_log.get("min_days", 0) + best_log.get("max_days", 0)) / 2)
        if best_log
        else 0
    )
    all_times = [best_avg_time] if best_log else []
    for log_dict, _cost in candidates:
        mn = log_dict.get("min_days", 0)
        mx = log_dict.get("max_days", 0)
        all_times.append((mn + mx) / 2)
    avg_cost = sum(all_costs) / len(all_costs) if all_costs else 0
    avg_time = sum(all_times) / len(all_times) if all_times else 0
    cost_saving = (
        ((avg_cost - best_cost) / avg_cost * 100) if best_cost and avg_cost > 0 else 0
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
