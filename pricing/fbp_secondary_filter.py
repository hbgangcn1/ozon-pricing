"""FBP二次筛选模块。

按(fbp_company, fbp_service_level)分组，
每组保留基础费率最高的物流规则，避免同公司同等级的
多条低价规则淹没其他候选方案。
"""

from collections import defaultdict


def fbp_secondary_filter(logistics_list):
    """FBP二次筛选：按公司+服务等级分组，每组取最高费率。

    Args:
        logistics_list: 物流规则字典列表，每条包含
            fbp_company / fbp_service_level / base_rate 等字段。

    Returns:
        筛选后的物流规则列表（每组保留一条）。
    """
    if not logistics_list:
        return []

    groups = defaultdict(list)
    for log in logistics_list:
        company = log.get("fbp_company", "unknown")
        sl = log.get("fbp_service_level", "unknown")
        key = (company, sl)
        groups[key].append(log)

    filtered = []
    for _key, group in groups.items():
        best = max(
            group,
            key=lambda x: float(x.get("base_rate", 0)),
        )
        filtered.append(best)

    if len(logistics_list) != len(filtered):
        print(
            f"FBP二次筛选: {len(logistics_list)} -> "
            f"{len(filtered)} (groups: {len(groups)})"
        )

    return filtered
