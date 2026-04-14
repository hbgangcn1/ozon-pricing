import logging
from functools import lru_cache
from .logistic_cost import calculate_logistic_cost
from .cost_filter import cost_and_filter
from .select_best import select_best_by_priority, add_unselected

logger = logging.getLogger(__name__)

_RESULT_HELPERS = __import__(f"{__package__}._result_helpers", fromlist=["*"])
_FBP_ELIMINATED_REASON = "该物流无法覆盖更高成本"


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
    # 将selected也纳入平均值计算: avg = (selected + all candidates) / (1 + N)
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


def _run_calculation(
    product, land_logistics, air_logistics, mode, priority, filtered_logistics
):
    unit_price = float(product.get("unit_price", 0))
    labeling_fee = float(product.get("labeling_fee", 0))
    shipping_fee = float(product.get("shipping_fee", 0))
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
    product, land_logistics, air_logistics, mode="fast", priority="低价优先"
):
    filtered_logistics = {"land": [], "air": []}
    try:
        if product is None or land_logistics is None or air_logistics is None:
            return _empty_result(filtered_logistics)
        if not hasattr(product, "get"):
            product.get("test")
        if _is_empty(land_logistics) and _is_empty(air_logistics):
            return _empty_result(filtered_logistics)
        result = _run_calculation(
            product, land_logistics, air_logistics, mode, priority, filtered_logistics
        )
        result["filtered_logistics"] = _sanitize_filtered_logistics(
            result.get("filtered_logistics", filtered_logistics),
            land_logistics,
            air_logistics,
        )
        return result
    except ZeroDivisionError:
        raise
    except AttributeError:
        raise
    except (ValueError, TypeError, KeyError) as e:
        print(f"计算定价时发生错误: {e}")
        return _error_result(product)


def _estimate_price_rub(product):
    rate, _ = _get_exchange_rates()
    unit_price = float(product.get("unit_price", 0) or 0)
    labeling_fee = float(product.get("labeling_fee", 0) or 0)
    shipping_fee = float(product.get("shipping_fee", 0) or 0)
    margin = float(product.get("target_profit_margin", 0.2) or 0)
    if margin >= 1:
        margin /= 100
    total_cost = unit_price + labeling_fee + shipping_fee
    denom = max(1 - margin - 0.1, 0.3)
    price_cny = total_cost / denom if denom > 0 else total_cost * 2
    return price_cny / rate if rate > 0 else 0


def _estimate_and_select_rate(
    product,
    commission_category,
    fulfillment_type,
    select_fn,
):
    price_rub = _estimate_price_rub(product)
    return select_fn(commission_category, fulfillment_type, price_rub)


def _collect_selected_names(pp, sp):
    """从两个定价结果中收集被选中物流的名称集合。"""
    names = set()
    for res in (pp, sp):
        for bkey in ("best_land", "best_air"):
            best = res.get(bkey)
            if isinstance(best, dict):
                n = best.get("name")
                if n:
                    names.add(n)
            elif isinstance(best, str) and best:
                names.add(best)
    return names


def _merge_filtered(pp_fl, sp_fl, selected_names, seen, merged):
    """合并两个定价结果的被淘汰物流（非 FBP 二次筛选场景）。"""
    for kind in ("land", "air"):
        for item in pp_fl.get(kind, []) + sp_fl.get(kind, []):
            key = item.get("name", "")
            if key in selected_names:
                continue
            if key not in seen:
                seen.add(key)
                merged[kind].append(item)


def _add_stage3_price_filtered(
    candidates,
    price_best,
    filtered_list,
    skip_names=None,
):
    """低价优先路径：未被选中物流标注更优方案信息。"""
    best_name = price_best[0].get("name", "") if price_best and price_best[0] else ""
    best_cost = price_best[1] if price_best and price_best[1] is not None else 0.0
    existing = {item["name"] for item in filtered_list}
    skip = skip_names or set()
    for log_dict, _cost in candidates:
        name = log_dict.get("name", "")
        if not name or name == best_name or name in existing or name in skip:
            continue
        reason = (
            f"未被选中，物流成本 ¥{_cost:.2f}"
            f"（已选更优方案：{best_name} ¥{best_cost:.2f}）"
        )
        filtered_list.append({"name": name, "reason": reason})
        existing.add(name)


def _add_stage3_speed_filtered(
    candidates,
    speed_best,
    filtered_list,
    skip_names=None,
):
    """速度优先路径：未被选中物流标注更快方案信息。"""
    best_log = speed_best[0] if speed_best and speed_best[0] else None
    best_name = best_log.get("name", "") if best_log else ""
    best_min = best_log.get("min_days", 0) if best_log else 0
    best_max = best_log.get("max_days", 0) if best_log else 0
    existing = {item["name"] for item in filtered_list}
    skip = skip_names or set()
    for log_dict, _cost in candidates:
        name = log_dict.get("name", "")
        if not name or name == best_name or name in existing or name in skip:
            continue
        min_d = log_dict.get("min_days", 0) or 0
        max_d = log_dict.get("max_days", 0) or 0
        reason = (
            f"未被选中，时效 {min_d}-{max_d}天（已选更快方案：{best_name} "
            f"{best_min}-{best_max}天）"
        )
        filtered_list.append({"name": name, "reason": reason})
        existing.add(name)


def _merge_stage1_filtered(stage1_filtered, merged, seen, selected_names=None):
    skip = selected_names or set()
    for kind in ("land", "air"):
        for item in stage1_filtered.get(kind, []):
            name = item.get("name", "")
            if name and name not in seen and name not in skip:
                seen.add(name)
                merged[kind].append(item)


def _merge_stage2_eliminated(eliminated, merged, seen):
    for log in eliminated:
        name = log.get("name", "")
        if not name or name in seen:
            continue
        seen.add(name)
        kind = "air" if log.get("type") == "air" else "land"
        merged[kind].append({"name": name, "reason": _FBP_ELIMINATED_REASON})


def _override_stage3_best(result, land_best, air_best):
    if land_best and land_best[0]:
        result["best_land"] = land_best[0]
        result["land_cost"] = land_best[1]
    if air_best and air_best[0]:
        result["best_air"] = air_best[0]
        result["air_cost"] = air_best[1]


def _stage1_filter(group_product, land_all, air_all, mode):
    unit_price = float(group_product.get("unit_price", 0))
    labeling_fee = float(group_product.get("labeling_fee", 0))
    shipping_fee = float(group_product.get("shipping_fee", 0))
    rate, _ = _get_exchange_rates()
    stage1_filtered = {"land": [], "air": []}
    land_cands, air_cands, _, _, _ = _run_filters(
        group_product,
        land_all,
        air_all,
        unit_price,
        labeling_fee,
        shipping_fee,
        rate,
        stage1_filtered,
        "低价优先",
        mode,
    )
    survivors = [ld for ld, _c in land_cands] + [ld for ld, _c in air_cands]
    return survivors, stage1_filtered


def _stage3_select(land_candidates, air_candidates):
    from pricing.fbp_stage3_select import (
        compute_temp_abcde_groups,
        select_best_price_stage3,
        select_best_speed_stage3,
    )

    price_best_land = select_best_price_stage3(land_candidates)
    price_best_air = select_best_price_stage3(air_candidates)
    speed_best_land = select_best_speed_stage3(
        land_candidates,
        compute_temp_abcde_groups([c[0] for c in land_candidates]),
    )
    speed_best_air = select_best_speed_stage3(
        air_candidates,
        compute_temp_abcde_groups([c[0] for c in air_candidates]),
    )
    return price_best_land, price_best_air, speed_best_land, speed_best_air


def _group_fbp_cis(subset, group_product, mode, split_fn):
    from pricing.fbp_secondary_filter import fbp_secondary_filter

    land_all, air_all = split_fn(subset)

    survivors, stage1_filtered = _stage1_filter(
        group_product,
        land_all,
        air_all,
        mode,
    )

    kept, eliminated = fbp_secondary_filter(survivors)

    kept_land, kept_air = split_fn(kept)
    pp = calculate_pricing(
        group_product,
        kept_land,
        kept_air,
        mode=mode,
        priority="低价优先",
    )
    sp = calculate_pricing(
        group_product,
        kept_land,
        kept_air,
        mode=mode,
        priority="速度优先",
    )

    unit_price = float(group_product.get("unit_price", 0))
    labeling_fee = float(group_product.get("labeling_fee", 0))
    shipping_fee = float(group_product.get("shipping_fee", 0))
    rate, _ = _get_exchange_rates()
    land_cands, air_cands, _, _, _ = _run_filters(
        group_product,
        kept_land,
        kept_air,
        unit_price,
        labeling_fee,
        shipping_fee,
        rate,
        {"land": [], "air": []},
        "低价优先",
        mode,
    )

    pb_land, pb_air, sb_land, sb_air = _stage3_select(land_cands, air_cands)
    _override_stage3_best(pp, pb_land, pb_air)
    _override_stage3_best(sp, sb_land, sb_air)

    selected_names = _collect_selected_names(pp, sp)
    pp_fl = pp.get("filtered_logistics", {"land": [], "air": []})
    sp_fl = sp.get("filtered_logistics", {"land": [], "air": []})
    merged = {"land": [], "air": []}
    seen = set()
    _merge_filtered(pp_fl, sp_fl, selected_names, seen, merged)
    _merge_stage1_filtered(stage1_filtered, merged, seen, selected_names)
    _merge_stage2_eliminated(eliminated, merged, seen)
    _add_stage3_price_filtered(
        land_cands,
        pb_land,
        merged["land"],
        skip_names=selected_names,
    )
    _add_stage3_price_filtered(
        air_cands,
        pb_air,
        merged["air"],
        skip_names=selected_names,
    )
    _add_stage3_speed_filtered(
        land_cands,
        sb_land,
        merged["land"],
        skip_names=selected_names,
    )
    _add_stage3_speed_filtered(
        air_cands,
        sb_air,
        merged["air"],
        skip_names=selected_names,
    )
    return {
        "price_priority": pp,
        "speed_priority": sp,
        "filtered_logistics": merged,
    }


def calculate_pricing_grouped(
    product,
    all_logistics,
    mode="fast",
    priority="低价优先",
    commission_category=None,
):
    from pricing.commission import select_commission_rate_from_category

    _CIS_DESTS = {"KZ", "BY", "KGZ", "UZ", "GE", "AZ"}

    def _split(logistics_list):
        land = [r for r in logistics_list if r.get("type") == "land"]
        air = [r for r in logistics_list if r.get("type") == "air"]
        return land, air

    def _apply_commission(ft):
        if commission_category is None or mode == "fast":
            return product
        prod_copy = dict(product)
        rate_val = _estimate_and_select_rate(
            prod_copy,
            commission_category,
            ft,
            select_commission_rate_from_category,
        )
        if rate_val is not None:
            prod_copy["commission_rate"] = rate_val
        return prod_copy

    def _group(ft, dest_filter, apply_fbp_filter=False):
        subset = [
            r
            for r in all_logistics
            if r.get("fulfillment_type", "rfbs") == ft and dest_filter(r)
        ]
        group_product = _apply_commission(ft)
        if apply_fbp_filter:
            return _group_fbp_cis(subset, group_product, mode, _split)
        land, air = _split(subset)
        pp = calculate_pricing(
            group_product,
            land,
            air,
            mode=mode,
            priority="低价优先",
        )
        sp = calculate_pricing(
            group_product,
            land,
            air,
            mode=mode,
            priority="速度优先",
        )
        selected_names = _collect_selected_names(pp, sp)
        pp_fl = pp.get("filtered_logistics", {"land": [], "air": []})
        sp_fl = sp.get("filtered_logistics", {"land": [], "air": []})
        seen = set()
        merged = {"land": [], "air": []}
        _merge_filtered(
            pp_fl,
            sp_fl,
            selected_names,
            seen,
            merged,
        )
        return {
            "price_priority": pp,
            "speed_priority": sp,
            "filtered_logistics": merged,
        }

    fbp_all = [r for r in all_logistics if r.get("fulfillment_type", "rfbs") == "fbp"]
    cis_service_groups = set()
    for r in fbp_all:
        if r.get("destination", "RU") in {"KZ", "BY"}:
            cis_service_groups.add(
                (
                    r.get("fbp_company") or "unknown",
                    r.get("fbp_service_level") or "unknown",
                )
            )

    result = {
        "rfbs_ru": _group(
            "rfbs",
            lambda r: r.get("destination", "RU") == "RU",
        ),
        "fbp_ru": _group(
            "fbp",
            lambda r: (
                (
                    r.get("fbp_company") or "unknown",
                    r.get("fbp_service_level") or "unknown",
                )
                not in cis_service_groups
            ),
        ),
        "fbp_cis": _group(
            "fbp",
            lambda r: (
                (
                    r.get("fbp_company") or "unknown",
                    r.get("fbp_service_level") or "unknown",
                )
                in cis_service_groups
            ),
            apply_fbp_filter=True,
        ),
    }
    for dest in sorted(_CIS_DESTS):
        result[f"rfbs_{dest}"] = _group(
            "rfbs",
            lambda r, _d=dest: r.get("destination", "RU") == _d,
        )
    return result
