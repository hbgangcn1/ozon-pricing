from typing import cast

from xlsx_import.common import (
    as_int,
    create_row,
    finalize_source_file,
    infer_type,
    is_blank_row,
    parse_days,
    parse_price_limit_cny,
    parse_rate,
    parse_size_limits,
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
        ws = next(ws for ws in wb.worksheets if "russia-china cp" in ws.title.lower())
        source_name = finalize_source_file(actual_path, source_file)
        result = {"rows": [], "skipped": 0, "errors": []}
        for row_num in range(HEADER_ROW + 1, ws.max_row + 1):
            values: list[object] = [
                cast(object, ws.cell(row_num, col).value) for col in range(1, 17)
            ]
            if is_blank_row(values):
                continue
            name = values[1]
            name_text = str(name).strip() if name is not None else ""
            if not name_text:
                result["skipped"] += 1
                continue
            try:
                item = create_row(name_text, source_name)
                item["type"] = infer_type(name_text)
                item["min_days"], item["max_days"] = parse_days(values[3])
                item["base_fee"], item["continue_fee"], item["continue_unit"] = (
                    parse_rate(values[2])
                )
                item["min_weight"] = as_int(values[8])
                item["max_weight"] = as_int(values[9])
                min_cny, max_cny = parse_price_limit_cny(f"{values[11]}-{values[12]}")
                item["price_min_cny"] = min(min_cny, max_cny)
                item["price_limit_cny"] = max(min_cny, max_cny)
                item["max_sum_of_sides"], item["max_longest_side"], _ = (
                    parse_size_limits(values[7])
                )
                item["allow_battery"] = parse_yes_no(values[5])
                item["allow_liquid"] = parse_yes_no(values[6])
                result["rows"].append(item)
            except Exception as exc:
                result["skipped"] += 1
                result["errors"].append(f"row {row_num}: {exc}")
        return result
    finally:
        if should_close:
            wb.close()
