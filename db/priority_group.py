"""Dynamic priority group calculation for user logistics.

Groups are computed per transport type (land/air) independently:
- E: invalid (min_days or max_days missing/zero)
- A: all 3 metrics <= corresponding averages
- B: exactly 2 metrics <= averages
- C: exactly 1 metric <= average
- D: 0 metrics <= averages
"""

from collections import defaultdict


def _is_valid(item: dict) -> bool:
    min_d = item.get("min_days")
    max_d = item.get("max_days")
    return bool(min_d and max_d)


def _score_group(count: int) -> str:
    return {3: "A", 2: "B", 1: "C"}.get(count, "D")


def _compute_for_type(items: list[dict]) -> dict[int, str]:
    """Compute priority groups for a single transport type."""
    valid = [it for it in items if _is_valid(it)]
    result: dict[int, str] = {}

    for it in items:
        if not _is_valid(it):
            result[it["id"]] = "E"

    if not valid:
        return result

    n = len(valid)
    avg_min = sum(it["min_days"] for it in valid) / n
    avg_max = sum(it["max_days"] for it in valid) / n
    avg_avg = sum(
        (it["min_days"] + it["max_days"]) / 2 for it in valid
    ) / n

    for it in valid:
        count = 0
        if it["min_days"] <= avg_min:
            count += 1
        if it["max_days"] <= avg_max:
            count += 1
        if (it["min_days"] + it["max_days"]) / 2 <= avg_avg:
            count += 1
        result[it["id"]] = _score_group(count)

    return result


def compute_priority_groups(items: list[dict]) -> dict[int, str]:
    """Compute priority groups for all items, split by type.

    Args:
        items: List of dicts with keys: id, type, min_days, max_days

    Returns:
        Dict mapping logistics id to group letter (A/B/C/D/E)
    """
    if not items:
        return {}

    by_type: dict[str, list[dict]] = defaultdict(list)
    for it in items:
        transport = it.get("type") or "land"
        by_type[transport].append(it)

    result: dict[int, str] = {}
    for _transport, group in by_type.items():
        result.update(_compute_for_type(group))
    return result
