from collections import defaultdict

_ELIMINATED_REASON = "该物流无法覆盖更高成本"


def fbp_secondary_filter(logistics_list):
    """按 (company, service_level, priority_group) 分组，每组保留 base_fee 最高的1条。

    Returns:
        (kept, eliminated) — kept 参与定价计算，eliminated 显示为被淘汰物流。
    """
    if not logistics_list:
        return [], []

    groups = defaultdict(list)
    for log in logistics_list:
        key = (
            log.get("fbp_company") or "unknown",
            log.get("fbp_service_level") or "unknown",
            log.get("priority_group") or "unknown",
        )
        groups[key].append(log)

    kept = []
    eliminated = []
    for _key, group in groups.items():
        best = max(
            group,
            key=lambda x: float(x.get("base_fee", 0)),
        )
        kept.append(best)
        for log in group:
            if log is not best:
                eliminated.append(log)

    return kept, eliminated
