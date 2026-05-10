from pathlib import Path

import pytest
from openpyxl import Workbook

from xlsx_import import parse_file
from xlsx_import.common import (
    infer_type,
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


def test_parse_rate_precision_5_decimals():
    """parse_rate returns continue_fee rounded to 5 decimal places."""
    _, cont, _ = parse_rate("¥1.90 + ¥0.067/1 г")
    assert cont == 0.067
    assert cont == round(cont, 5)
    _, cont2, _ = parse_rate("¥3 + ¥0,035/1g")
    assert cont2 == 0.035
    assert cont2 == round(cont2, 5)


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


def test_parse_price_limit_cny_precision_2_decimals():
    mn, mx = parse_price_limit_cny("0,01 - 1 135")
    assert mn == round(mn, 2)
    assert mx == round(mx, 2)


def test_parse_price_limit_cny_returns_zeroes_for_invalid_value():
    assert parse_price_limit_cny("-") == (0.0, 0.0)
    assert parse_price_limit_cny(None) == (0.0, 0.0)


# --------------- infer_type unit tests ---------------


def test_infer_type_air_keyword():
    assert infer_type("air freight") == "air"
    assert infer_type("空运专线") == "air"


def test_infer_type_express_keyword():
    """Express（含 Super Express）应推断为空运。"""
    assert infer_type("UNI Express KZ") == "air"
    assert infer_type("Ural FBP Super Express") == "air"
    assert infer_type("CEL Express Extra Small") == "air"


def test_infer_type_non_express_returns_land():
    assert infer_type("Standard delivery") == "land"
    assert infer_type("UNI FBP Standard Extra Small") == "land"
    assert infer_type("China Post eParcel Economy") == "land"


def test_infer_type_express_in_category_column():
    """分类列包含 express 时也应识别为空运。"""
    assert infer_type("Express", "Ural Standard") == "air"
    assert infer_type("Standard", "some name") == "land"


@pytest.mark.parametrize(
    ("filename", "expected_format"),
    [
        ("China_post_30_04_26_1777887104.xlsx", "china_post"),
        ("China_scoring_ENG_CN_21_04_26_1776754052.xlsx", "scoring_rfbs"),
        ("CIS_Delivery_methods_7_04_26_1775544004.xlsx", "cis_rfbs"),
        ("FBP_List_of_services_21_04_26_1776754056.xlsx", "fbp"),
    ],
)
def test_detect_format_matches_reference_workbooks(filename: str, expected_format: str):
    assert detect_format(_file(filename)) == expected_format


def test_detect_format_rejects_legacy_china_post_workbook(tmp_path: Path):
    """Legacy 'Russia-China CP' sheet detection path (detector.py:89-97).

    Original fixture China_post_10_2_26_ENG_CN_1770625401.xlsx no longer exists.
    Synthesize a minimal workbook containing the deprecated sheet name to keep
    coverage of the rejection branch.
    """
    workbook = Workbook()
    worksheet = workbook.active
    assert worksheet is not None
    worksheet.title = "Russia-China CP"
    filepath = tmp_path / "legacy_china_post.xlsx"
    workbook.save(filepath)

    with pytest.raises(ValueError, match="旧版 China Post"):
        detect_format(str(filepath))


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
        _file("China_post_30_04_26_1777887104.xlsx"),
        source_file="china_post_source.xlsx",
    )

    assert result["format"] == "china_post"
    assert result["skipped"] >= 0
    assert isinstance(result["errors"], list)
    row = _find_row(result["rows"], "China Post to OZON Standard")
    assert row["fulfillment_type"] == "rfbs"
    assert row["destination"] == "RU"
    assert row["source_file"] == "china_post_source.xlsx"
    assert row["min_days"] == 10
    assert row["max_days"] == 15
    assert row["base_fee"] == 1.9
    assert row["continue_fee"] == 0.067
    assert row["continue_unit"] == "1g"
    assert row["allow_battery"] == 0
    assert row["price_min_cny"] == 0.01
    assert row["price_limit_cny"] == 135.0


def test_parse_file_china_post_parses_dual_sheet_destinations():
    result = parse_file(
        _file("China_post_30_04_26_1777887104.xlsx"),
    )

    assert result["format"] == "china_post"
    rows = result["rows"]
    assert len(rows) == 9
    assert result["skipped"] == 0
    assert result["errors"] == []

    counts: dict[str, int] = {}
    for r in rows:
        counts[r["destination"]] = counts.get(r["destination"], 0) + 1
    assert counts == {"RU": 2, "KZ": 2, "BY": 2, "AM": 1, "UZ": 1, "AZ": 1}


def test_parse_file_scoring_rfbs_skips_transition_rows_and_parses_rates():
    result = parse_file(_file("China_scoring_ENG_CN_21_04_26_1776754052.xlsx"))

    assert result["format"] == "scoring_rfbs"
    # переход rows are fully skipped by is_transition_row()
    assert all("переход" not in (r.get("name") or "") for r in result["rows"])
    row = _find_row(result["rows"], "Ural Standard Extra Small")
    assert row["fulfillment_type"] == "rfbs"
    assert row["destination"] == "RU"
    assert row["base_fee"] == 2.92
    assert row["continue_fee"] == 0.0364
    assert row["continue_unit"] == "1g"
    assert row["allow_battery"] == 1
    assert row["price_min_cny"] > 0
    assert row["price_limit_cny"] >= row["price_min_cny"]


def test_parse_file_cis_rfbs_assigns_all_expected_destinations():
    result = parse_file(_file("CIS_Delivery_methods_7_04_26_1775544004.xlsx"))

    assert result["format"] == "cis_rfbs"
    destinations = {row["destination"] for row in result["rows"]}
    assert {"BY", "KZ", "KGZ"}.issubset(destinations)
    by_row = _find_row(result["rows"], "CEL Belarus Standard Extra Small")
    assert by_row["destination"] == "BY"
    assert by_row["price_min_cny"] > 0
    assert by_row["price_limit_cny"] >= by_row["price_min_cny"]
    kz_row = _find_row(result["rows"], "CEL Kazakhstan Standard Extra Small")
    assert kz_row["destination"] == "KZ"
    assert kz_row["price_min_cny"] > 0
    assert kz_row["price_limit_cny"] >= kz_row["price_min_cny"]


def test_parse_file_fbp_extracts_smart_company_and_service_level():
    result = parse_file(_file("FBP_List_of_services_21_04_26_1776754056.xlsx"))

    assert result["format"] == "fbp"
    smart_row = _find_row(result["rows"], "CEL FBP Standard Extra Small")
    assert smart_row["fulfillment_type"] == "fbp"
    assert smart_row["destination"] == "RU"
    assert smart_row["is_smart"] == 1
    assert smart_row["fbp_company"] == "CEL"
    assert smart_row["fbp_service_level"] == "smart"
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
    result = parse_file(_file("FBP_List_of_services_21_04_26_1776754056.xlsx"))

    sum_rows = [r for r in result["rows"] if r.get("volume_mode") == "sum_of_sides"]
    assert len(sum_rows) > 0, "Should find at least one sum_of_sides row"
    for row in sum_rows:
        assert row["sum_of_sides_threshold"] in (75, 90), (
            f"Threshold should be 75 or 90, got {row['sum_of_sides_threshold']}"
        )
        assert row["volume_coefficient"] == 6000.0


def test_parse_file_fbp_physical_weight_is_none_mode():
    """FBP parser converts 'Physical weight' to volume_mode='none'."""
    result = parse_file(_file("FBP_List_of_services_21_04_26_1776754056.xlsx"))

    none_rows = [r for r in result["rows"] if r.get("volume_mode") == "none"]
    assert len(none_rows) > 0, "Should find 'none' volume mode rows"
    for row in none_rows:
        assert row["volume_coefficient"] == 0.0
        assert row["sum_of_sides_threshold"] == 0


def test_parse_file_fbp_max_actual_vs_volume_mode():
    """FBP parser converts 'Max weight between...' to 'max_actual_vs_volume'."""
    result = parse_file(_file("FBP_List_of_services_21_04_26_1776754056.xlsx"))

    max_rows = [
        r for r in result["rows"] if r.get("volume_mode") == "max_actual_vs_volume"
    ]
    assert len(max_rows) > 0, "Should find 'max_actual_vs_volume' rows"
    for row in max_rows:
        assert row["volume_coefficient"] > 0


# --------------- type inference integration tests ---------------


def test_china_post_air_delivery_rows_are_air_and_ground_delivery_rows_are_land():
    result = parse_file(
        _file("China_post_30_04_26_1777887104.xlsx")
    )

    ozon_standard = _find_row(result["rows"], "China Post to OZON Standard")
    assert ozon_standard["type"] == "air"
    ozon_economy = _find_row(result["rows"], "China Post to OZON Economy")
    assert ozon_economy["type"] == "land"
    epacket_kz_air = _find_row(result["rows"], "ePacket Kazakhstan")
    assert epacket_kz_air["type"] == "air"
    epacket_economy_track = _find_row(result["rows"], "ePacket Economy Track")
    assert epacket_economy_track["type"] == "land"


def test_scoring_express_rows_are_air():
    result = parse_file(_file("China_scoring_ENG_CN_21_04_26_1776754052.xlsx"))

    express_row = _find_row(result["rows"], "Ural Express Extra Small")
    assert express_row["type"] == "air"
    standard_row = _find_row(result["rows"], "Ural Standard Extra Small")
    assert standard_row["type"] == "land"


def test_cis_express_rows_are_air():
    result = parse_file(_file("CIS_Delivery_methods_7_04_26_1775544004.xlsx"))

    standard_row = _find_row(
        result["rows"],
        "CEL Belarus Standard Extra Small",
    )
    assert standard_row["type"] == "land"
    economy_row = _find_row(
        result["rows"],
        "CEL Kazakhstan Economy Extra Small",
    )
    assert economy_row["type"] == "land"


def test_fbp_express_rows_are_air():
    result = parse_file(_file("FBP_List_of_services_21_04_26_1776754056.xlsx"))

    express_row = _find_row(result["rows"], "Ural FBP Super Express Extra Small")
    assert express_row["type"] == "air"
    standard_row = _find_row(result["rows"], "CEL FBP Standard Extra Small")
    assert standard_row["type"] == "land"


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
    result = parse_file(_file("CIS_Delivery_methods_7_04_26_1775544004.xlsx"))
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
    result = parse_file(_file("CIS_Delivery_methods_7_04_26_1775544004.xlsx"))
    third_rows = [r for r in result["rows"] if r.get("max_third_side", 0) > 0]
    assert len(third_rows) > 0, "Should find rows with max_third_side > 0"
    for row in third_rows:
        assert row["max_longest_side"] > 0
        assert row["max_second_side"] > 0
        assert row["max_third_side"] > 0
        assert row["max_sum_of_sides"] == 0


def test_cis_rfbs_physical_weight_volume_mode():
    """CIS 'Physical weight' tarification → volume_mode='none', coeff=0."""
    result = parse_file(_file("CIS_Delivery_methods_7_04_26_1775544004.xlsx"))
    phys_rows = [r for r in result["rows"] if r.get("volume_mode") == "none"]
    assert len(phys_rows) > 0, "Should find 'Physical weight' rows"
    for row in phys_rows:
        assert row["volume_coefficient"] == 0.0


def test_cis_rfbs_kz_by_cny_from_column_m():
    """KZ & BY parser reads CNY prices from column M (idx 12)."""
    result = parse_file(_file("CIS_Delivery_methods_7_04_26_1775544004.xlsx"))
    by_row = _find_row(result["rows"], "Ural Belarus Standard Extra Small")
    assert by_row["price_min_cny"] == 0.01
    assert by_row["price_limit_cny"] == 135.0
    assert round(by_row["price_min_cny"], 2) == by_row["price_min_cny"]
    assert round(by_row["price_limit_cny"], 2) == by_row["price_limit_cny"]


def test_cis_rfbs_kz_by_volume_mode():
    """KZ & BY parser reads volume mode from P col and coeff from Q col."""
    result = parse_file(_file("CIS_Delivery_methods_7_04_26_1775544004.xlsx"))
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


# --------------- Scoring RFBS specific tests ---------------


def test_scoring_rfbs_continue_fee_precision():
    result = parse_file(_file("China_scoring_ENG_CN_21_04_26_1776754052.xlsx"))
    for row in result["rows"]:
        cf = row["continue_fee"]
        assert cf == round(cf, 5), (
            f"{row['name']}: continue_fee {cf} not 5-decimal precise"
        )


def test_scoring_rfbs_cny_from_column_n():
    result = parse_file(_file("China_scoring_ENG_CN_21_04_26_1776754052.xlsx"))
    row = _find_row(result["rows"], "Ural Standard Extra Small")
    assert row["price_min_cny"] > 0
    assert row["price_limit_cny"] >= row["price_min_cny"]
    assert row["price_min_cny"] == round(row["price_min_cny"], 2)
    assert row["price_limit_cny"] == round(row["price_limit_cny"], 2)


def test_scoring_rfbs_volume_mode_physical_weight():
    result = parse_file(_file("China_scoring_ENG_CN_21_04_26_1776754052.xlsx"))
    phys_rows = [r for r in result["rows"] if r.get("volume_mode") == "none"]
    assert len(phys_rows) > 0
    for row in phys_rows:
        assert row["volume_coefficient"] == 0.0


def test_scoring_rfbs_volume_mode_exists():
    result = parse_file(_file("China_scoring_ENG_CN_21_04_26_1776754052.xlsx"))
    for row in result["rows"]:
        assert "volume_mode" in row, f"{row['name']}: missing volume_mode"
        assert "volume_coefficient" in row, f"{row['name']}: missing volume_coefficient"


# --------------- China Post specific tests ---------------


CHINA_POST_FILE = _file("China_post_30_04_26_1777887104.xlsx")


def _china_post_rows():
    result = parse_file(CHINA_POST_FILE)
    assert result["rows"], f"No rows parsed. Errors: {result['errors']}"
    return result["rows"]


def test_china_post_cny_min_from_l_column():
    """price_min_cny comes from L column (index 11) in NEW two-sheet layout."""
    rows = _china_post_rows()
    row = _find_row(rows, "China Post to OZON Standard")
    assert row["price_min_cny"] == 0.01


def test_china_post_cny_max_from_m_column():
    """price_limit_cny comes from M column (index 12) in NEW two-sheet layout."""
    rows = _china_post_rows()
    row = _find_row(rows, "China Post to OZON Standard")
    assert row["price_limit_cny"] == 135.0


def test_china_post_cny_dash_means_zero():
    """'-' in CNY column → 0.0."""
    rows = _china_post_rows()
    epacket_rows = [r for r in rows if "epacket" in r["name"].lower()]
    assert epacket_rows, "Should find ePacket rows"
    for row in epacket_rows:
        assert row["price_limit_cny"] == 0.0, (
            f"{row['name']}: price_limit_cny should be 0.0 for '-', got {row['price_limit_cny']}"
        )


def test_china_post_physical_weight_rows():
    """Rows with 'Physical weight' S column → volume_mode='none', coeff=0."""
    rows = _china_post_rows()
    for row in rows:
        if "ems" not in row["name"].lower():
            assert row["volume_mode"] == "none", (
                f"{row['name']}: expected volume_mode='none', got {row['volume_mode']!r}"
            )
            assert row["volume_coefficient"] == 0.0, (
                f"{row['name']}: expected volume_coefficient=0.0, got {row['volume_coefficient']}"
            )


def test_china_post_simple_size_limits():
    """Simple format H column rows parse max_sum_of_sides and max_longest_side."""
    rows = _china_post_rows()
    row = _find_row(rows, "China Post to OZON Standard")
    assert row["max_sum_of_sides"] == 90, (
        f"max_sum_of_sides: expected 90, got {row['max_sum_of_sides']}"
    )
    assert row["max_longest_side"] == 60, (
        f"max_longest_side: expected 60, got {row['max_longest_side']}"
    )


def test_china_post_epacket_cylinder_limits():
    """ePacket H column rows parse all 8 cylinder+min size fields."""
    rows = _china_post_rows()
    row = _find_row(rows, "ePacket Kazakhstan")
    assert row["max_sum_of_sides"] == 90
    assert row["max_longest_side"] == 60
    assert row["max_cylinder_sum"] == 104
    assert row["max_cylinder_length"] == 90
    assert row["min_length"] == 14
    assert row["min_second_side"] == 11
    assert row["min_cylinder_sum"] == 17
    assert row["min_cylinder_length"] == 11


def test_parse_size_fields_unit_epacket():
    """Unit test for _parse_size_fields with hardcoded ePacket text."""
    from xlsx_import.parsers import china_post

    text = (
        "Max parcel size:\n"
        "Sum of sides<90, Length≤60;\n"
        "for cylindrical packages: the sum of the double diameter and the length"
        " of the package— up to 104 cm, Length — up to 90 cm\n"
        "\n"
        "Min parcel size:\n"
        "Length — 14 cm, width — 11 cm;\n"
        "for cylindrical packages: the sum of the double diameter and the length"
        " of the package— 17 cm, Length — 11 cm"
    )
    item: dict = {}
    getattr(china_post, "_parse_size_fields")(item, text)
    assert item["max_sum_of_sides"] == 90
    assert item["max_longest_side"] == 60
    assert item["max_cylinder_sum"] == 104
    assert item["max_cylinder_length"] == 90
    assert item["min_length"] == 14
    assert item["min_second_side"] == 11
    assert item["min_cylinder_sum"] == 17
    assert item["min_cylinder_length"] == 11


def test_parse_size_fields_unit_eems():
    """Unit test for _parse_size_fields with hardcoded eEMS text."""
    from xlsx_import.parsers import china_post

    text = (
        "Standard 1:Any size: no more than1,5 m, sum of two longest sides — up to 3 m.\n"
        "Standard 2:Any size: no more than1,05 m, sum of two longest sides — up to 2 m."
    )
    item: dict = {}
    getattr(china_post, "_parse_size_fields")(item, text)
    assert item["max_longest_side"] == 150
    assert item.get("max_cylinder_sum", 0) == 0
    assert item.get("min_length", 0) == 0


def test_china_post_base_mode_when_i_column_zero():
    """Standard (I=0) → fee_mode stays base_plus_continue."""
    rows = _china_post_rows()
    row = _find_row(rows, "China Post to OZON Standard")
    assert row["fee_mode"] == "base_plus_continue"
    assert row["base_fee"] == 1.9
    assert row["first_fee"] == 0.0
    assert row["first_weight_g"] == 0
    assert row["min_weight"] == 0
