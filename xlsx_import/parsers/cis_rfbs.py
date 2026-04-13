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


DEST_MAP = {
    "belarus": "BY",
    "kazakhstan": "KZ",
    "az": "AZ",
    "ge": "GE",
    "uz": "UZ",
    "kgz": "KGZ",
}


def _destination(sheet_name: str, delivery_name: str) -> str:
    text = f"{sheet_name} {delivery_name}".lower()
    for needle, code in DEST_MAP.items():
        if needle in text:
            return code
    return "KZ"


def _apply_volume_mode(item: dict, values: list[object], is_kz_by: bool) -> None:
    vol_mode_idx = 15 if is_kz_by else 17
    vol_coeff_idx = 16 if is_kz_by else 18
    raw_volume = normalize_text(values[vol_mode_idx]) or "none"
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
        item["volume_coefficient"] = parse_volume_coeff(values[vol_coeff_idx])
    elif "max" in raw_lower and ("volume" in raw_lower or "volumetric" in raw_lower):
        item["volume_mode"] = "max_actual_vs_volume"
        item["volume_coefficient"] = parse_volume_coeff(values[vol_coeff_idx])
        item["sum_of_sides_threshold"] = 0
    else:
        item["volume_mode"] = raw_volume
        item["volume_coefficient"] = parse_volume_coeff(values[vol_coeff_idx])
        item["sum_of_sides_threshold"] = 0


def parse(
    source: object, filepath: str | None = None, source_file: str | None = None
) -> dict:
    wb, should_close = load_workbook_source(source)
    try:
        actual_path = filepath or cast(str, source)
        source_name = finalize_source_file(actual_path, source_file)
        result = {"rows": [], "skipped": 0, "errors": []}
        sheets = [
            ws
            for ws in wb.worksheets
            if ("kz & by" in ws.title.lower() or "other cis" in ws.title.lower())
            and "中文" not in ws.title
        ]
        for ws in sheets:
            is_kz_by = "kz & by" in ws.title.lower()
            for row_num in range(6, ws.max_row + 1):
                values: list[object] = [
                    cast(object, ws.cell(row_num, col).value) for col in range(1, 21)
                ]
                if is_blank_row(values):
                    continue
                if is_transition_row(values):
                    continue
                name = values[3]
                name_text = normalize_text(name)
                if not name_text:
                    result["skipped"] += 1
                    continue
                try:
                    item = create_row(name_text, source_name)
                    item["type"] = infer_type(values[1], name_text)
                    item["destination"] = _destination(ws.title, name_text)
                    item["min_days"], item["max_days"] = parse_days(values[4])
                    rate_value = values[5] if is_kz_by else values[6]
                    item["base_fee"], item["continue_fee"], item["continue_unit"] = (
                        parse_rate(rate_value)
                    )
                    item["min_weight"] = as_int(values[9] if is_kz_by else values[11])
                    item["max_weight"] = as_int(values[10] if is_kz_by else values[12])
                    limit_value = values[12] if is_kz_by else values[14]
                    item["price_min_cny"], item["price_limit_cny"] = (
                        parse_price_limit_cny(limit_value)
                    )
                    size_idx = 8 if is_kz_by else 10
                    bat_idx = 6 if is_kz_by else 8
                    liq_idx = 7 if is_kz_by else 9
                    size_sum, size_longest, size_third = cast(
                        tuple[int, int, int],
                        parse_size_limits(values[size_idx]),
                    )
                    item["max_sum_of_sides"] = size_sum
                    item["max_longest_side"] = size_longest
                    item["max_third_side"] = size_third
                    if size_sum == 0 and size_longest > 0 and size_third > 0:
                        nums = [
                            int(n)
                            for n in re.findall(
                                r"\d+",
                                normalize_text(values[size_idx]).lower(),
                            )
                            if int(n) > 0
                        ]
                        if len(nums) >= 3:
                            sorted_nums = sorted(nums[:3], reverse=True)
                            item["max_second_side"] = sorted_nums[1]
                    item["allow_battery"] = parse_yes_no(values[bat_idx])
                    item["allow_liquid"] = parse_yes_no(values[liq_idx])
                    _apply_volume_mode(item, values, is_kz_by)
                    item["priority_group"] = normalize_text(values[0]) or "D"
                    result["rows"].append(item)
                except Exception as exc:
                    result["skipped"] += 1
                    result["errors"].append(f"{ws.title} row {row_num}: {exc}")
        return result
    finally:
        if should_close:
            wb.close()
