from decimal import Decimal
import logging


logger = logging.getLogger(__name__)

__all__ = ["_compute_billable_weight"]


def _compute_billable_weight(
    logistic: dict,
    sides: list,
    actual_weight: float | Decimal,
) -> tuple[Decimal, str, bool]:
    mode = logistic.get("volume_mode", "none")
    coefficient = _to_decimal(logistic.get("volume_coefficient", 5000))
    actual_weight_decimal = _to_decimal(actual_weight)
    decimal_sides = [_to_decimal(side) for side in sides]

    if mode in ("max_actual_vs_volume", "longest_side", "sum_of_sides"):
        if coefficient <= 0:
            logistic_id = logistic.get("id") or logistic.get("logistic_id")
            logger.warning(
                "Invalid volume_coefficient=%s for logistic_id=%s",
                coefficient,
                logistic_id,
            )
            return _billable_decimal(actual_weight_decimal), "实重", False

    if mode == "max_actual_vs_volume":
        volume = _volume_weight_grams(decimal_sides, coefficient)
        if volume > actual_weight_decimal:
            return _billable_decimal(volume), "体积重", True
        return _billable_decimal(actual_weight_decimal), "实重", False

    if mode == "longest_side":
        threshold = _to_decimal(logistic.get("longest_side_threshold", 0))
        if max(decimal_sides) > threshold:
            volume = _volume_weight_grams(decimal_sides, coefficient)
            return _billable_decimal(volume), "体积重", True
        return _billable_decimal(actual_weight_decimal), "实重", False

    if mode == "sum_of_sides":
        threshold = _to_decimal(logistic.get("sum_of_sides_threshold", 0))
        if sum(decimal_sides) > threshold:
            volume = _volume_weight_grams(decimal_sides, coefficient)
            return _billable_decimal(volume), "体积重", True
        return _billable_decimal(actual_weight_decimal), "实重", False

    return _billable_decimal(actual_weight_decimal), "实重", False


def _volume_weight_grams(sides: list, coefficient: float | Decimal) -> Decimal:
    volume = Decimal("1")
    for side in sides:
        volume *= _to_decimal(side)
    return volume / _to_decimal(coefficient) * Decimal("1000")


def _to_decimal(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _billable_decimal(value: Decimal) -> Decimal:
    return value
