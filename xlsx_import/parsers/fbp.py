import re
from typing import cast

from xlsx_import.common import (
    as_int,
    create_row,
    finalize_source_file,
    infer_type,
    is_blank_row,
    is_transition_row,
    normalize_text,
    parse_days,
    parse_price_limit_cny,
    parse_rate,
    parse_size_limits,
    parse_volume_coeff,
    parse_yes_no,
    load_workbook_source,
)


DEST_MAP = {"russia": "RU", "kazakhstan": "KZ", "belarus": "BY"}
LEVEL_MAP = {
    "super express": "super_express",
    "smart": "smart",
    "express": "express",
    "standard": "standard",
    "economy": "economy",
}


def _service_level(text: object) -> str | None:
    lowered = normalize_text(text).lower()
    for needle, level in LEVEL_MAP.items():
        if needle in lowered:
            return level
    return None


def _merged_service_lookup(ws) -> dict[int, object]:
    lookup: dict[int, object] = {}
    if not hasattr(ws, "merged_cells"):
        return lookup
    for merged_range in ws.merged_cells.ranges:
        if merged_range.min_col != 3 or merged_range.max_col != 3:
            continue
        value = ws.cell(merged_range.min_row, merged_range.min_col).value
        for row_num in range(merged_range.min_row, merged_range.max_row + 1):
            lookup[row_num] = value
    return lookup


def parse(
    source: object,
    filepath: str | None = None,
    source_file: str | None = None,
    max_import_rows: int | None = None,
) -> dict:
    wb, should_close = load_workbook_source(source)
    try:
        actual_path = filepath or cast(str, source)
        ws = next(ws for ws in wb.worksheets if ws.title.lower() == "china fbp")
        source_name = finalize_source_file(actual_path, source_file)
        result = {"rows": [], "skipped": 0, "errors": []}
        carry: dict[int, object] = {1: "", 2: "", 3: ""}
        merged_service_lookup = _merged_service_lookup(ws)
        rows = ws.iter_rows(min_row=8, max_col=20, values_only=True)
        for row_num, row in enumerate(rows, start=8):
            if max_import_rows is not None and row_num - 7 > max_import_rows:
                raise ValueError(f"导入行数不能超过 {max_import_rows} 行")
            values: list[object] = [cast(object, value) for value in row]
            if is_blank_row(values):
                continue
            merged_service = merged_service_lookup.get(row_num)
            if merged_service is not None and not normalize_text(values[2]):
                values[2] = merged_service
            if is_transition_row(values):
                continue
            for idx in carry:
                if normalize_text(values[idx]):
                    carry[idx] = values[idx]
                else:
                    values[idx] = carry[idx]
            name = values[6]
            name_text = normalize_text(name)
            if not name_text:
                result["skipped"] += 1
                continue
            try:
                service = normalize_text(values[2])
                item = create_row(name_text, source_name)
                item["fulfillment_type"] = "fbp"
                item["type"] = infer_type(values[3], service, name_text)
                item["destination"] = DEST_MAP.get(
                    normalize_text(values[4]).lower(), "RU"
                )
                item["fbp_company"] = normalize_text(values[1]) or None
                item["is_smart"] = (
                    1
                    if "smart" in service.lower() or "smart" in name_text.lower()
                    else 0
                )
                item["fbp_service_level"] = _service_level(service) or _service_level(
                    values[3]
                )
                item["min_days"], item["max_days"] = parse_days(values[7])
                item["base_fee"], item["continue_fee"], item["continue_unit"] = (
                    parse_rate(values[8])
                )
                item["min_weight"] = as_int(values[12])
                item["max_weight"] = as_int(values[13])
                item["price_min_cny"], item["price_limit_cny"] = parse_price_limit_cny(
                    values[15]
                )
                item["max_sum_of_sides"], item["max_longest_side"], _ = (
                    parse_size_limits(values[11])
                )
                item["allow_battery"] = parse_yes_no(values[9])
                item["allow_liquid"] = parse_yes_no(values[10])
                raw_volume = normalize_text(values[18]) or "none"
                raw_lower = raw_volume.lower()
                sum_match = re.search(
                    r"sum\s+of\s+sides\s*(?:≤|<=)\s*(\d+)",
                    raw_lower,
                )
                if raw_lower == "physical weight":
                    item["volume_mode"] = "none"
                    item["volume_coefficient"] = 0.0
                    item["sum_of_sides_threshold"] = 0
                elif sum_match:
                    item["volume_mode"] = "sum_of_sides"
                    item["sum_of_sides_threshold"] = int(sum_match.group(1))
                    item["volume_coefficient"] = parse_volume_coeff(values[19])
                elif "max" in raw_lower and "volume" in raw_lower:
                    item["volume_mode"] = "max_actual_vs_volume"
                    item["volume_coefficient"] = parse_volume_coeff(values[19])
                    item["sum_of_sides_threshold"] = 0
                else:
                    item["volume_mode"] = raw_volume
                    item["volume_coefficient"] = parse_volume_coeff(values[19])
                    item["sum_of_sides_threshold"] = 0
                item["priority_group"] = normalize_text(values[5]) or "D"
                item["scoring_group"] = normalize_text(values[5]) or None
                result["rows"].append(item)
            except Exception as exc:
                result["skipped"] += 1
                result["errors"].append(f"row {row_num}: {exc}")
        return result
    finally:
        if should_close:
            wb.close()
