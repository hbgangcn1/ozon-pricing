from collections import defaultdict

_ELIMINATED_REASON = "该物流无法覆盖更高成本"


def _is_smart(log):
    return log.get("is_smart") == 1 or log.get("fbp_service_level") == "smart"


def fbp_secondary_filter(logistics_list):
    if not logistics_list:
        return [], []

    non_smart = []
    smart_groups = defaultdict(list)
    for log in logistics_list:
        if _is_smart(log):
            company = log.get("fbp_company", "unknown")
            smart_groups[company].append(log)
        else:
            non_smart.append(log)

    kept = list(non_smart)
    eliminated = []
    for _company, group in smart_groups.items():
        best = max(
            group,
            key=lambda x: float(x.get("base_rate", 0)),
        )
        kept.append(best)
        for log in group:
            if log is not best:
                eliminated.append(log)

    return kept, eliminated
