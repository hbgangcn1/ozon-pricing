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


HEADER_ROW = 5


def parse(
    source: object, filepath: str | None = None, source_file: str | None = None
) -> dict:
    wb, should_close = load_workbook_source(source)
    try:
        actual_path = filepath or cast(str, source)
        ws = next(ws for ws in wb.worksheets if "china rfbs" in ws.title.lower())
        source_name = finalize_source_file(actual_path, source_file)
        result = {"rows": [], "skipped": 0, "errors": []}
        carry: dict[int, object] = {0: "", 1: "", 2: "", 3: ""}
        for row_num in range(HEADER_ROW + 1, ws.max_row + 1):
            values: list[object] = [
                cast(object, ws.cell(row_num, col).value) for col in range(1, 19)
            ]
            if is_blank_row(values):
                continue
            if is_transition_row(values):
                continue
            for idx in carry:
                if normalize_text(values[idx]):
                    carry[idx] = values[idx]
                else:
                    values[idx] = carry[idx]
            name = values[3]
            name_text = normalize_text(name)
            if not name_text:
                result["skipped"] += 1
                continue
            try:
                item = create_row(name_text, source_name)
                item["type"] = infer_type(values[1], name_text)
                item["min_days"], item["max_days"] = parse_days(values[5])
                item["base_fee"], item["continue_fee"], item["continue_unit"] = (
                    parse_rate(values[6])
                )
                item["min_weight"] = as_int(values[10])
                item["max_weight"] = as_int(values[11])
                item["price_min_cny"], item["price_limit_cny"] = parse_price_limit_cny(
                    values[13]
                )
                item["max_sum_of_sides"], item["max_longest_side"], _ = (
                    parse_size_limits(values[9])
                )
                item["allow_battery"] = parse_yes_no(values[7])
                item["allow_liquid"] = parse_yes_no(values[8])
                raw_volume = normalize_text(values[16]) or "none"
                raw_lower = raw_volume.lower()
                sum_vol_match = re.search(
                    r"sum\s+of\s+sides\s*(?:≤|<=)\s*(\d+)",
                    raw_lower,
                )
                if raw_lower == "physical weight":
                    item["volume_mode"] = "none"
                    item["volume_coefficient"] = 0.0
                    item["sum_of_sides_threshold"] = 0
                elif sum_vol_match:
                    item["volume_mode"] = "sum_of_sides"
                    item["sum_of_sides_threshold"] = int(sum_vol_match.group(1))
                    item["volume_coefficient"] = parse_volume_coeff(values[17])
                elif "max" in raw_lower and (
                    "volume" in raw_lower or "volumetric" in raw_lower
                ):
                    item["volume_mode"] = "max_actual_vs_volume"
                    item["volume_coefficient"] = parse_volume_coeff(values[17])
                    item["sum_of_sides_threshold"] = 0
                else:
                    item["volume_mode"] = raw_volume
                    item["volume_coefficient"] = parse_volume_coeff(values[17])
                    item["sum_of_sides_threshold"] = 0
                item["priority_group"] = normalize_text(values[0]) or "D"
                result["rows"].append(item)
            except Exception as exc:
                result["skipped"] += 1
                result["errors"].append(f"row {row_num}: {exc}")
        return result
    finally:
        if should_close:
            wb.close()
