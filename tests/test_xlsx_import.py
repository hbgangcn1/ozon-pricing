from pathlib import Path

import pytest
from openpyxl import Workbook

from xlsx_import import parse_file
from xlsx_import.common import (
    parse_days,
    parse_price_limit_cny,
    parse_rate,
    parse_size_limits,
    parse_volume_coeff,
)
from xlsx_import.detector import detect_format


BASE_DIR = Path(__file__).resolve().parents[1]
XLSX_DIR = BASE_DIR / "xlsx"


def _file(name: str) -> str:
    return str(XLSX_DIR / name)


def _find_row(rows: list[dict], keyword: str) -> dict:
    for row in rows:
        if keyword.lower() in (row.get("name") or "").lower():
            return row
    raise AssertionError(f"未找到包含 {keyword!r} 的行")


def test_parse_days_supports_common_formats():
    assert parse_days("11-15") == (11, 15)
    assert parse_days("11–15") == (11, 15)
    assert parse_days("7") == (7, 7)
    assert parse_days("8-13 days") == (8, 13)


def test_parse_days_invalid_returns_none_tuple():
    assert parse_days("not available") == (None, None)


def test_parse_rate_parses_base_continue_and_unit():
    assert parse_rate("¥1.0 + ¥0.003/1 g") == (1.0, 0.003, "1g")
    assert parse_rate("¥8 + ¥4,8/100g") == (8.0, 4.8, "100g")


def test_parse_rate_invalid_returns_default_tuple():
    assert parse_rate("-") == (0.0, 0.0, "100g")


def test_parse_volume_coeff_parses_divisors_and_defaults():
    assert parse_volume_coeff("L×W×H÷6000") == 6000.0
    assert parse_volume_coeff("Volume ÷5000") == 5000.0
    assert parse_volume_coeff("Physical weight") == 5000.0
    assert parse_volume_coeff("-") == 0.0
    assert parse_volume_coeff("") == 0.0
    assert parse_volume_coeff(None) == 0.0


def test_parse_price_limit_cny_parses_range_text():
    assert parse_price_limit_cny("12 - 34") == (12.0, 34.0)
    assert parse_price_limit_cny("12.5-34.6") == (12.5, 34.6)


def test_parse_price_limit_cny_returns_zeroes_for_invalid_value():
    assert parse_price_limit_cny("-") == (0.0, 0.0)
    assert parse_price_limit_cny(None) == (0.0, 0.0)


@pytest.mark.parametrize(
    ("filename", "expected_format"),
    [
        ("China_post_10_2_26_ENG_CN_1770625401.xlsx", "china_post"),
        ("China_scoring_ENG_CN_25_03_2026_1773650328.xlsx", "scoring_rfbs"),
        ("CIS_Delivery_methods_20_01_2026_1768818333.xlsx", "cis_rfbs"),
        ("FBP_List_of_services_5_03_26_1772704547.xlsx", "fbp"),
    ],
)
def test_detect_format_matches_reference_workbooks(filename: str, expected_format: str):
    assert detect_format(_file(filename)) == expected_format


def test_detect_format_raises_for_unknown_workbook(tmp_path: Path):
    workbook = Workbook()
    worksheet = workbook.active
    assert worksheet is not None
    worksheet.title = "Unknown Sheet"
    filepath = tmp_path / "unknown.xlsx"
    workbook.save(filepath)

    with pytest.raises(ValueError, match="无法识别xlsx格式"):
        detect_format(str(filepath))


def test_parse_file_china_post_returns_expected_core_fields():
    result = parse_file(
        _file("China_post_10_2_26_ENG_CN_1770625401.xlsx"),
        source_file="china_post_source.xlsx",
    )

    assert result["format"] == "china_post"
    assert result["skipped"] >= 0
    assert isinstance(result["errors"], list)
    row = _find_row(result["rows"], "China Post to PUDO Standard")
    assert row["fulfillment_type"] == "rfbs"
    assert row["destination"] == "RU"
    assert row["source_file"] == "china_post_source.xlsx"
    assert row["min_days"] == 10
    assert row["max_days"] == 15
    assert row["base_fee"] == 1.9
    assert row["continue_fee"] == 0.067
    assert row["continue_unit"] == "1g"
    assert row["allow_battery"] == 0
    assert row["price_min_cny"] > 0
    assert row["price_limit_cny"] >= row["price_min_cny"]


def test_parse_file_scoring_rfbs_skips_transition_rows_and_parses_rates():
    result = parse_file(_file("China_scoring_ENG_CN_25_03_2026_1773650328.xlsx"))

    assert result["format"] == "scoring_rfbs"
    assert all("переход" not in (row.get("name") or "") for row in result["rows"])
    row = _find_row(result["rows"], "Ural Standard Extra Small")
    assert row["fulfillment_type"] == "rfbs"
    assert row["destination"] == "RU"
    assert row["base_fee"] == 2.8
    assert row["continue_fee"] == 0.035
    assert row["continue_unit"] == "1g"
    assert row["allow_battery"] == 1
    assert row["price_min_cny"] > 0
    assert row["price_limit_cny"] >= row["price_min_cny"]


def test_parse_file_cis_rfbs_assigns_all_expected_destinations():
    result = parse_file(_file("CIS_Delivery_methods_20_01_2026_1768818333.xlsx"))

    assert result["format"] == "cis_rfbs"
    destinations = {row["destination"] for row in result["rows"]}
    assert {"BY", "KZ", "AZ", "GE", "UZ", "KGZ"}.issubset(destinations)
    by_row = _find_row(result["rows"], "Belarus Standard Extra Small")
    assert by_row["destination"] == "BY"
    assert by_row["price_min_cny"] > 0
    assert by_row["price_limit_cny"] >= by_row["price_min_cny"]
    uz_row = _find_row(result["rows"], "UNI Express UZ")
    assert uz_row["destination"] == "UZ"
    assert uz_row["price_min_cny"] > 0
    assert uz_row["price_limit_cny"] >= uz_row["price_min_cny"]


def test_parse_file_fbp_extracts_smart_company_and_service_level():
    result = parse_file(_file("FBP_List_of_services_5_03_26_1772704547.xlsx"))

    assert result["format"] == "fbp"
    smart_row = _find_row(result["rows"], "CEL FBP Standard Extra Small")
    assert smart_row["fulfillment_type"] == "fbp"
    assert smart_row["destination"] == "RU"
    assert smart_row["is_smart"] == 1
    assert smart_row["fbp_company"] == "CEL"
    assert smart_row["fbp_service_level"] == "standard"
    assert smart_row["price_min_cny"] > 0
    assert smart_row["price_limit_cny"] >= smart_row["price_min_cny"]
    express_row = _find_row(result["rows"], "Ural FBP Super Express Extra Small")
    assert express_row["fbp_service_level"] == "super_express"
    assert express_row["price_min_cny"] > 0
    assert express_row["price_limit_cny"] >= express_row["price_min_cny"]
    assert express_row["volume_mode"] == "none"
    assert express_row["volume_coefficient"] == 0.0
    vol_rows = [r for r in result["rows"] if r["name"] == "Ural FBP Super Express"]
    assert len(vol_rows) >= 1
    assert vol_rows[0]["volume_mode"] == "sum_of_sides"
    assert vol_rows[0]["sum_of_sides_threshold"] == 90
    assert vol_rows[0]["volume_coefficient"] == 6000.0


def test_parse_file_fbp_sum_of_sides_volume_mode():
    """FBP parser correctly identifies 'Sum of sides' volume mode."""
    result = parse_file(_file("FBP_List_of_services_5_03_26_1772704547.xlsx"))

    sum_rows = [r for r in result["rows"] if r.get("volume_mode") == "sum_of_sides"]
    assert len(sum_rows) > 0, "Should find at least one sum_of_sides row"
    for row in sum_rows:
        assert row["sum_of_sides_threshold"] in (75, 90), (
            f"Threshold should be 75 or 90, got {row['sum_of_sides_threshold']}"
        )
        assert row["volume_coefficient"] == 6000.0


def test_parse_file_fbp_physical_weight_is_none_mode():
    """FBP parser converts 'Physical weight' to volume_mode='none'."""
    result = parse_file(_file("FBP_List_of_services_5_03_26_1772704547.xlsx"))

    none_rows = [r for r in result["rows"] if r.get("volume_mode") == "none"]
    assert len(none_rows) > 0, "Should find 'none' volume mode rows"
    for row in none_rows:
        assert row["volume_coefficient"] == 0.0
        assert row["sum_of_sides_threshold"] == 0


def test_parse_file_fbp_max_actual_vs_volume_mode():
    """FBP parser converts 'Max weight between...' to 'max_actual_vs_volume'."""
    result = parse_file(_file("FBP_List_of_services_5_03_26_1772704547.xlsx"))

    max_rows = [
        r for r in result["rows"] if r.get("volume_mode") == "max_actual_vs_volume"
    ]
    assert len(max_rows) > 0, "Should find 'max_actual_vs_volume' rows"
    for row in max_rows:
        assert row["volume_coefficient"] > 0


# --------------- parse_size_limits unit tests ---------------


def test_parse_size_limits_sum_of_sides():
    """'Sum of sides ≤ 90cm, Length ≤ 60 cm' → (90, 60, 0)."""
    result = parse_size_limits("Sum of sides ≤ 90cm, Length ≤ 60 cm")
    assert result == (90, 60, 0)


def test_parse_size_limits_individual_sides():
    """'150 x 80 x 80 cm' → (0, 150, 80)."""
    result = parse_size_limits("150 x 80 x 80 cm")
    assert result == (0, 150, 80)


def test_parse_size_limits_empty():
    """Empty/None returns (0, 0, 0)."""
    assert parse_size_limits(None) == (0, 0, 0)
    assert parse_size_limits("") == (0, 0, 0)


# --------------- CIS RFBS specific tests ---------------


def test_cis_rfbs_price_from_column_o():
    """CIS parser reads CNY prices from column O (index 14)."""
    result = parse_file(_file("CIS_Delivery_methods_20_01_2026_1768818333.xlsx"))
    for row in result["rows"]:
        if row.get("price_min_cny") and row.get("price_limit_cny"):
            price_min = row["price_min_cny"]
            price_limit = row["price_limit_cny"]
            assert round(price_min, 2) == price_min, (
                f"price_min_cny not 2 decimals: {price_min}"
            )
            assert round(price_limit, 2) == price_limit, (
                f"price_limit_cny not 2 decimals: {price_limit}"
            )
            break
    else:
        pytest.fail("No CIS row with both price_min_cny and price_limit_cny")


def test_cis_rfbs_individual_side_limits():
    """CIS rows with 'NxNxN cm' format get max_third_side set."""
    result = parse_file(_file("CIS_Delivery_methods_20_01_2026_1768818333.xlsx"))
    third_rows = [r for r in result["rows"] if r.get("max_third_side", 0) > 0]
    assert len(third_rows) > 0, "Should find rows with max_third_side > 0"
    for row in third_rows:
        assert row["max_longest_side"] > 0
        assert row["max_second_side"] > 0
        assert row["max_third_side"] > 0
        assert row["max_sum_of_sides"] == 0


def test_cis_rfbs_physical_weight_volume_mode():
    """CIS 'Physical weight' tarification → volume_mode='none', coeff=0."""
    result = parse_file(_file("CIS_Delivery_methods_20_01_2026_1768818333.xlsx"))
    phys_rows = [r for r in result["rows"] if r.get("volume_mode") == "none"]
    assert len(phys_rows) > 0, "Should find 'Physical weight' rows"
    for row in phys_rows:
        assert row["volume_coefficient"] == 0.0


def test_cis_rfbs_kz_by_cny_from_column_m():
    """KZ & BY parser reads CNY prices from column M (idx 12)."""
    result = parse_file(_file("CIS_Delivery_methods_20_01_2026_1768818333.xlsx"))
    by_row = _find_row(result["rows"], "Ural Belarus Standard Extra Small")
    assert by_row["price_min_cny"] == 0.01
    assert by_row["price_limit_cny"] == 135.0
    assert round(by_row["price_min_cny"], 2) == by_row["price_min_cny"]
    assert round(by_row["price_limit_cny"], 2) == by_row["price_limit_cny"]


def test_cis_rfbs_kz_by_volume_mode():
    """KZ & BY parser reads volume mode from P col and coeff from Q col."""
    result = parse_file(_file("CIS_Delivery_methods_20_01_2026_1768818333.xlsx"))
    by_row = _find_row(result["rows"], "Ural Belarus Standard Extra Small")
    # Physical weight → none / 0
    assert by_row["volume_mode"] == "none"
    assert by_row["volume_coefficient"] == 0.0
    assert by_row["sum_of_sides_threshold"] == 0
    # Big size rows use volumetric weight
    big_row = _find_row(result["rows"], "Ural Belarus Standard Big")
    assert big_row["volume_mode"] == "max_actual_vs_volume"
    assert big_row["volume_coefficient"] == 12000.0
    assert big_row["sum_of_sides_threshold"] == 0
