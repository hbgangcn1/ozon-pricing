import re
import time
from pathlib import Path
from typing import Any

import openpyxl


DEFAULTS = {
    "type": "land",
    "base_fee": 0.0,
    "price_limit_cny": 0.0,
    "price_min_cny": 0.0,
    "first_fee": 0.0,
    "first_weight_g": 0,
    "continue_fee": 0.0,
    "continue_unit": "100g",
    "fee_mode": "base_plus_continue",
    "min_weight": 0,
    "max_weight": 0,
    "volume_coefficient": 5000.0,
    "volume_mode": "none",
    "max_sum_of_sides": 0,
    "max_longest_side": 0,
    "allow_battery": 0,
    "allow_liquid": 0,
    "delivery_method": "unknown",
    "priority_group": "D",
    "fulfillment_type": "rfbs",
    "destination": "RU",
    "fbp_service_level": None,
    "fbp_company": None,
    "is_smart": 0,
}


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("\u00a0", " ").strip()


def strip_thousands_sep(text: str) -> str:
    return re.sub(r"(\d)\s+(\d)", r"\1\2", text)


def as_int(value: Any) -> int:
    text = strip_thousands_sep(normalize_text(value))
    if not text or text == "-":
        return 0
    match = re.search(r"-?\d+", text)
    return int(match.group(0)) if match else 0


def parse_days(value: Any) -> tuple[int | None, int | None]:
    text = normalize_text(value)
    if not text or text == "-":
        return (None, None)
    nums = [int(item) for item in re.findall(r"\d+", text)]
    if len(nums) >= 2:
        return (nums[-2], nums[-1])
    if len(nums) == 1:
        return (nums[0], nums[0])
    return (None, None)


def parse_rate(value: Any) -> tuple[float, float, str]:
    text = normalize_text(value)
    if not text or text == "-":
        return (0.0, 0.0, "100g")
    compact = text.replace(" ", "").replace(",", ".")
    match = re.search(
        r"([0-9]+(?:\.[0-9]+)?)\+[^0-9]*([0-9]+(?:\.[0-9]+)?)/([0-9]*)(?:g|г|克)",
        compact,
        re.IGNORECASE,
    )
    if not match:
        return (0.0, 0.0, "100g")
    unit_num = match.group(3)
    unit = f"{unit_num}g" if unit_num else "1g"
    return (float(match.group(1)), float(match.group(2)), unit)


def parse_volume_coeff(value: Any) -> float:
    text = strip_thousands_sep(normalize_text(value))
    if not text or text == "-":
        return 0.0
    match = re.search(r"÷\s*(\d+(?:\.\d+)?)", text)
    if match:
        return float(match.group(1))
    return 5000.0


def parse_price_limit_cny(value: Any) -> tuple[float, float]:
    text = strip_thousands_sep(normalize_text(value)).replace(",", ".")
    match = re.search(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)", text)
    if not match:
        return (0.0, 0.0)
    return (float(match.group(1)), float(match.group(2)))


def parse_size_limits(value: Any) -> tuple[int, int, int]:
    text = strip_thousands_sep(normalize_text(value)).lower().replace("，", ",")
    sum_match = re.search(r"sum of sides[^\d]*(\d+)", text)
    len_match = re.search(r"length[^\d]*(\d+)", text)
    if not sum_match and "x" in text:
        nums = [int(item) for item in re.findall(r"\d+", text)]
        if len(nums) >= 3:
            sorted_nums = sorted(nums[:3], reverse=True)
            return (0, sorted_nums[0], sorted_nums[2])
    return (
        int(sum_match.group(1)) if sum_match else 0,
        int(len_match.group(1)) if len_match else 0,
        0,
    )


def parse_yes_no(value: Any) -> int:
    text = normalize_text(value).lower()
    if any(word in text for word in ("allowed", "yes", "允许", "разреш")):
        return 1
    return 0


def infer_type(*values: Any) -> str:
    text = " ".join(normalize_text(value).lower() for value in values)
    if any(word in text for word in ("air", "空运")):
        return "air"
    return "land"


def create_row(
    name: Any,
    source_file: str,
    imported_at: int | None = None,
) -> dict:
    row = dict(DEFAULTS)
    row.update(
        {
            "name": normalize_text(name),
            "delivery_method": normalize_text(name),
            "source_file": source_file,
            "imported_at": imported_at or int(time.time()),
        }
    )
    return row


def finalize_source_file(filepath: str, source_file: str | None) -> str:
    return source_file or Path(filepath).name


def is_blank_row(values: list[Any]) -> bool:
    return not any(normalize_text(value) for value in values)


def load_workbook_source(source: Any):
    if isinstance(source, str):
        return openpyxl.load_workbook(source, data_only=True), True
    return source, False
