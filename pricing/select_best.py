from collections import defaultdict


def _speed_key(candidate):
    log = candidate[0]
    cost = candidate[1]
    priority_group = log.get("priority_group", "D")
    candidate_min_days = log.get("min_days", 0)
    candidate_max_days = log.get("max_days", 0)
    candidate_avg_time = (candidate_min_days + candidate_max_days) / 2
    group_priority = {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4}.get(priority_group, 4)
    return group_priority, cost, candidate_avg_time


def _price_key(candidate):
    log = candidate[0]
    cost = candidate[1]
    priority_group = log.get("priority_group", "D")
    candidate_min_days = log.get("min_days", 0)
    candidate_max_days = log.get("max_days", 0)
    candidate_avg_time = (candidate_min_days + candidate_max_days) / 2
    group_priority = {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4}.get(priority_group, 4)
    return cost, group_priority, candidate_avg_time


def select_best_by_priority(candidates, priority_type):
    if not candidates:
        return None, None
    if priority_type == "速度优先":
        return min(candidates, key=_speed_key)
    return min(candidates, key=_price_key)


def add_unselected(candidates, filtered_list):
    groups = defaultdict(list)
    for log_dict, cost in candidates:
        groups[log_dict.get("delivery_method", "unknown")].append((log_dict, cost))
    for delivery, group in groups.items():
        already_filtered = {item["name"] for item in filtered_list}
        group.sort(key=lambda x: x[1])
        best_name = group[0][0].get("name", "")
        for log_dict, cost in group[1:]:
            name = log_dict.get("name", "")
            if name in already_filtered:
                continue
            filtered_list.append(
                {
                    "name": name,
                    "reason": (
                        f"未被选中，物流成本较高（¥{cost:.2f}，"
                        f"同类型最优：{best_name} ¥{group[0][1]:.2f}）"
                    ),
                }
            )
