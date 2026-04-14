def _avg_time(log):
    min_days = log.get("min_days") or 0
    max_days = log.get("max_days") or 0
    return (min_days + max_days) / 2


def _is_valid_log(log):
    min_days = log.get("min_days")
    max_days = log.get("max_days")
    return bool(min_days) and bool(max_days)


def compute_temp_abcde_groups(logistics_list):
    result = {}
    valid_logs = [log for log in logistics_list if _is_valid_log(log)]
    for log in logistics_list:
        if not _is_valid_log(log):
            result[log["name"]] = "E"
    if not valid_logs:
        return result

    count = len(valid_logs)
    avg_min = sum(log["min_days"] for log in valid_logs) / count
    avg_max = sum(log["max_days"] for log in valid_logs) / count
    avg_avg = sum(_avg_time(log) for log in valid_logs) / count

    for log in valid_logs:
        score = 0
        if log["min_days"] <= avg_min:
            score += 1
        if log["max_days"] <= avg_max:
            score += 1
        if _avg_time(log) <= avg_avg:
            score += 1
        result[log["name"]] = {3: "A", 2: "B", 1: "C"}.get(score, "D")
    return result


def select_best_speed_stage3(candidates, temp_groups):
    if not candidates:
        return None, None

    def key(candidate):
        log, cost = candidate
        group = temp_groups.get(log.get("name"), "E")
        return {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4}.get(group, 4), cost, _avg_time(log)

    return min(candidates, key=key)


def select_best_price_stage3(candidates):
    if not candidates:
        return None, None

    def key(candidate):
        log, cost = candidate
        return cost, _avg_time(log)

    return min(candidates, key=key)
