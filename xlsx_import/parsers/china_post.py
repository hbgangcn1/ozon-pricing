import re
from typing import cast

from xlsx_import.common import (
    as_int,
    create_row,
    finalize_source_file,
    is_blank_row,
    load_workbook_source,
    normalize_text,
    parse_days,
    parse_rate,
    parse_size_limits,
    parse_volume_coeff,
    parse_yes_no,
)

HEADER_ROW = 5

COL_METHOD = 1
COL_PRICE = 2
COL_DAYS = 3
COL_BATTERIES = 4
COL_LIQUIDS = 5
COL_MEASUREMENTS = 6
COL_WEIGHT_MIN = 7
COL_WEIGHT_MAX = 8
COL_CNY_MIN = 11
COL_CNY_MAX = 12
COL_TARIFICATION = 17
COL_VOLUME_CALC = 18
MAX_COL = 19

TARGET_SHEETS: dict[str, str | None] = {
    "china to russia by cp": "RU",
    "china to cis by cp": None,
}

_CIS_DESTINATION_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("kazakhstan", "KZ"),
    ("kz", "KZ"),
    ("belarus", "BY"),
    ("by", "BY"),
    ("armenia", "AM"),
    ("am", "AM"),
    ("uzbekistan", "UZ"),
    ("uz", "UZ"),
    ("azerbaijan", "AZ"),
    ("az", "AZ"),
    ("kyrgyzstan", "KGZ"),
    ("kgz", "KGZ"),
    ("georgia", "GE"),
    ("ge", "GE"),
)


def _parse_cny_value(value: object) -> float:
    if isinstance(value, (int, float)):
        return round(float(value), 2)
    text = str(value).strip() if value is not None else ""
    if not text or text == "-":
        return 0.0
    text = text.replace(",", ".").replace(" ", "")
    try:
        return round(float(text), 2)
    except ValueError:
        return 0.0


def _apply_volume_mode(item: dict, values: list[object]) -> None:
    raw = normalize_text(values[COL_TARIFICATION]).lower()
    item["longest_side_threshold"] = 0
    item["sum_of_sides_threshold"] = 0
    if "no side" in raw and "physical weight" in raw and "one side" in raw:
        match = re.search(r"no side\s*[<>≤≥]\s*(\d+)", raw)
        item["volume_mode"] = "longest_side"
        item["longest_side_threshold"] = int(match.group(1)) if match else 40
        item["volume_coefficient"] = parse_volume_coeff(values[COL_VOLUME_CALC])
    elif not raw or raw == "-" or "physical weight" in raw:
        item["volume_mode"] = "none"
        item["volume_coefficient"] = 0.0
    else:
        item["volume_mode"] = "max_actual_vs_volume"
        item["volume_coefficient"] = parse_volume_coeff(values[COL_VOLUME_CALC])


def _parse_size_fields(item: dict, value: object) -> None:
    for field in (
        "max_sum_of_sides",
        "max_longest_side",
        "max_second_side",
        "max_cylinder_sum",
        "max_cylinder_length",
        "min_length",
        "min_second_side",
        "min_cylinder_sum",
        "min_cylinder_length",
    ):
        item[field] = 0
    if value is None:
        return
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    lower = text.lower()
    if "cylindrical" in lower or "cylinder" in lower:
        item["max_sum_of_sides"], item["max_longest_side"], _ = parse_size_limits(text)
        cyl_lines = [
            line
            for line in text.split("\n")
            if "cylindrical" in line.lower() or "cylinder" in line.lower()
        ]
        if cyl_lines:
            max_nums = re.findall(r"up to\s+(\d+)\s*cm", cyl_lines[0], re.I)
            if max_nums:
                item["max_cylinder_sum"] = int(max_nums[0])
            if len(max_nums) > 1:
                item["max_cylinder_length"] = int(max_nums[1])
        min_idx = lower.find("min parcel size")
        if min_idx >= 0:
            min_text = text[min_idx:]
            length = re.search(r"length[^\d\n-—–]*[-—–\s]+(\d+)\s*cm", min_text, re.I)
            width = re.search(r"width[^\d\n-—–]*[-—–\s]+(\d+)\s*cm", min_text, re.I)
            if length:
                item["min_length"] = int(length.group(1))
            if width:
                item["min_second_side"] = int(width.group(1))
            if len(cyl_lines) > 1:
                min_nums = re.findall(r"(\d+)\s*cm", cyl_lines[1], re.I)
                if min_nums:
                    item["min_cylinder_sum"] = int(min_nums[0])
                if len(min_nums) > 1:
                    item["min_cylinder_length"] = int(min_nums[1])
    elif "standard" in lower and "no more than" in lower:
        match = re.search(
            r"standard\s*1[:\s]+.*?no more than\s*([\d,]+)\s*m",
            lower,
            re.S,
        )
        if match:
            item["max_longest_side"] = int(
                round(float(match.group(1).replace(",", ".")) * 100)
            )
    else:
        item["max_sum_of_sides"], item["max_longest_side"], _ = parse_size_limits(value)


def _resolve_cis_destination(method_name: str) -> str | None:
    lowered = method_name.lower()
    tokens = re.findall(r"[a-z]+", lowered)
    token_set = set(tokens)
    for keyword, code in _CIS_DESTINATION_KEYWORDS:
        if len(keyword) <= 3:
            if keyword in token_set:
                return code
        else:
            if keyword in lowered:
                return code
    return None


def _parse_sheet(ws, source_name: str, fixed_destination: str | None) -> dict:
    result: dict = {"rows": [], "skipped": 0, "errors": []}
    for row_num in range(HEADER_ROW + 1, ws.max_row + 1):
        values: list[object] = [
            cast(object, ws.cell(row_num, col).value)
            for col in range(1, MAX_COL + 1)
        ]
        if is_blank_row(values):
            continue
        name_text = normalize_text(values[COL_METHOD])
        if not name_text:
            result["skipped"] += 1
            continue
        try:
            if fixed_destination is not None:
                destination = fixed_destination
            else:
                destination = _resolve_cis_destination(name_text)
                if not destination:
                    result["skipped"] += 1
                    result["errors"].append(
                        f"row {row_num}: 无法识别 CIS 目的国: {name_text!r}"
                    )
                    continue

            item = create_row(name_text, source_name)
            item["destination"] = destination
            lowered = name_text.lower()
            item["type"] = (
                "air"
                if "eems" in lowered or "air delivery" in lowered
                else "land"
            )
            item["min_days"], item["max_days"] = parse_days(values[COL_DAYS])
            item["base_fee"], item["continue_fee"], item["continue_unit"] = (
                parse_rate(values[COL_PRICE])
            )
            min_weight_val = as_int(values[COL_WEIGHT_MIN])
            if min_weight_val != 0:
                item["fee_mode"] = "first_weight"
                item["first_fee"] = item["base_fee"]
                item["first_weight_g"] = min_weight_val
                item["base_fee"] = 0.0
                item["min_weight"] = 0
            else:
                item["min_weight"] = min_weight_val
            item["max_weight"] = as_int(values[COL_WEIGHT_MAX])
            item["price_min_cny"] = _parse_cny_value(values[COL_CNY_MIN])
            item["price_limit_cny"] = _parse_cny_value(values[COL_CNY_MAX])
            _parse_size_fields(item, values[COL_MEASUREMENTS])
            item["allow_battery"] = parse_yes_no(values[COL_BATTERIES])
            item["allow_liquid"] = parse_yes_no(values[COL_LIQUIDS])
            _apply_volume_mode(item, values)
            result["rows"].append(item)
        except Exception as exc:
            result["skipped"] += 1
            result["errors"].append(f"row {row_num}: {exc}")
    return result


def _select_target_sheets(wb) -> list[tuple[object, str | None]]:
    selected: list[tuple[object, str | None]] = []
    for ws in wb.worksheets:
        title_norm = (ws.title or "").strip().lower()
        if title_norm in TARGET_SHEETS:
            selected.append((ws, TARGET_SHEETS[title_norm]))
    return selected


def parse(
    source: object, filepath: str | None = None, source_file: str | None = None
) -> dict:
    wb, should_close = load_workbook_source(source)
    try:
        actual_path = filepath or cast(str, source)
        source_name = finalize_source_file(actual_path, source_file)
        sheets = _select_target_sheets(wb)
        if not sheets:
            titles = [ws.title for ws in wb.worksheets]
            raise ValueError(
                "China Post xlsx 中未找到目标工作表 "
                f"({list(TARGET_SHEETS.keys())})；实际工作表: {titles}"
            )

        merged: dict = {"rows": [], "skipped": 0, "errors": []}
        for ws, fixed_destination in sheets:
            sub = _parse_sheet(ws, source_name, fixed_destination)
            merged["rows"].extend(sub["rows"])
            merged["skipped"] += sub["skipped"]
            merged["errors"].extend(sub["errors"])

        if not merged["rows"]:
            raise ValueError(
                "China Post xlsx 解析后无任何有效行 "
                f"(skipped={merged['skipped']}, errors={merged['errors']})"
            )

        return merged
    finally:
        if should_close:
            wb.close()
