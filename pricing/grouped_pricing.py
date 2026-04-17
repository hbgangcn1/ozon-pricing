from .cost_filter import cost_and_filter
from ._pricing_helpers import (
    _get_exchange_rates,
    _make_cached_cost,
    _FBP_ELIMINATED_REASON,
)


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
    """Stage 1: 仅做物理约束筛选，不调用 add_unselected。"""
    unit_price = float(group_product.get("unit_price", 0))
    labeling_fee = float(group_product.get("labeling_fee", 0))
    shipping_fee = float(group_product.get("shipping_fee", 0))
    rate, _ = _get_exchange_rates()
    stage1_filtered = {"land": [], "air": []}
    is_fast_mode = mode == "fast"
    cached_cost = _make_cached_cost(is_fast_mode)
    all_costs_debug = []
    land_cands = cost_and_filter(
        land_all,
        group_product,
        land_all,
        cached_cost,
        unit_price,
        labeling_fee,
        shipping_fee,
        rate,
        stage1_filtered,
        all_costs_debug,
    )
    air_cands = cost_and_filter(
        air_all,
        group_product,
        land_all,
        cached_cost,
        unit_price,
        labeling_fee,
        shipping_fee,
        rate,
        stage1_filtered,
        all_costs_debug,
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
    from .calculate_pricing import calculate_pricing

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
    is_fast_mode = mode == "fast"
    cached_cost = _make_cached_cost(is_fast_mode)
    _discard = []
    land_cands = cost_and_filter(
        kept_land,
        group_product,
        kept_land,
        cached_cost,
        unit_price,
        labeling_fee,
        shipping_fee,
        rate,
        {"land": [], "air": []},
        _discard,
    )
    air_cands = cost_and_filter(
        kept_air,
        group_product,
        kept_land,
        cached_cost,
        unit_price,
        labeling_fee,
        shipping_fee,
        rate,
        {"land": [], "air": []},
        _discard,
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
    from .calculate_pricing import calculate_pricing

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
            res = _group_fbp_cis(subset, group_product, mode, _split)
            res["group_product"] = group_product
            return res
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
            "group_product": group_product,
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
