import logging


logger = logging.getLogger(__name__)

__all__ = ["_compute_billable_weight"]


def _compute_billable_weight(
    logistic: dict,
    sides: list,
    actual_weight: float,
) -> tuple[float, str, bool]:
    mode = logistic.get("volume_mode", "none")
    coefficient = logistic.get("volume_coefficient", 5000)

    if mode in ("max_actual_vs_volume", "longest_side", "sum_of_sides"):
        if coefficient <= 0:
            logistic_id = logistic.get("id") or logistic.get("logistic_id")
            logger.warning(
                "Invalid volume_coefficient=%s for logistic_id=%s",
                coefficient,
                logistic_id,
            )
            return float(actual_weight), "实重", False

    if mode == "max_actual_vs_volume":
        volume = _volume_weight_grams(sides, coefficient)
        if volume > actual_weight:
            return volume, "体积重", True
        return float(actual_weight), "实重", False

    if mode == "longest_side":
        threshold = logistic.get("longest_side_threshold", 0)
        if max(sides) > threshold:
            return _volume_weight_grams(sides, coefficient), "体积重", True
        return float(actual_weight), "实重", False

    if mode == "sum_of_sides":
        threshold = logistic.get("sum_of_sides_threshold", 0)
        if sum(sides) > threshold:
            return _volume_weight_grams(sides, coefficient), "体积重", True
        return float(actual_weight), "实重", False

    return float(actual_weight), "实重", False


def _volume_weight_grams(sides: list, coefficient: float) -> float:
    return (sides[0] * sides[1] * sides[2]) / coefficient * 1000
