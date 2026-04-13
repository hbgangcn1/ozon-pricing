def _speed_key(candidate):
    log = candidate[0]
    cost = candidate[1]
    priority_group = log.get("priority_group", "D")
    candidate_min_days = log.get("min_days") or 0
    candidate_max_days = log.get("max_days") or 0
    candidate_avg_time = (candidate_min_days + candidate_max_days) / 2
    group_priority = {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4}.get(priority_group, 4)
    return group_priority, cost, candidate_avg_time


def _price_key(candidate):
    log = candidate[0]
    cost = candidate[1]
    priority_group = log.get("priority_group", "D")
    candidate_min_days = log.get("min_days") or 0
    candidate_max_days = log.get("max_days") or 0
    candidate_avg_time = (candidate_min_days + candidate_max_days) / 2
    group_priority = {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4}.get(priority_group, 4)
    return cost, group_priority, candidate_avg_time


def select_best_by_priority(candidates, priority_type):
    if not candidates:
        return None, None
    if priority_type == "速度优先":
        return min(candidates, key=_speed_key)
    return min(candidates, key=_price_key)


def add_unselected(
    candidates, filtered_list, global_best=None, priority_type="低价优先"
):
    if not candidates:
        return
    global_best_name = ""
    global_best_cost = 0.0
    best_min_days = 0
    best_max_days = 0
    if global_best and global_best[0]:
        global_best_name = global_best[0].get("name", "")
        global_best_cost = global_best[1]
        best_min_days = global_best[0].get("min_days") or 0
        best_max_days = global_best[0].get("max_days") or 0

    already_filtered = {item["name"] for item in filtered_list}
    for log_dict, cost in candidates:
        name = log_dict.get("name", "")
        if name == global_best_name:
            continue
        if name in already_filtered:
            continue
        if priority_type == "速度优先":
            min_d = log_dict.get("min_days") or 0
            max_d = log_dict.get("max_days") or 0
            reason = f"未被选中，时效 {min_d}-{max_d}天"
            if global_best_name:
                reason += (
                    f"（已选更快方案："
                    f"{global_best_name} {best_min_days}-{best_max_days}天）"
                )
        else:
            reason = f"未被选中，物流成本 ¥{cost:.2f}"
            if global_best_name:
                reason += (
                    f"（已选更优方案：{global_best_name} ¥{global_best_cost:.2f}）"
                )
        filtered_list.append({"name": name, "reason": reason})
