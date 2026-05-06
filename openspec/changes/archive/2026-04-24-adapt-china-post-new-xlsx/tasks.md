## 1. Detector update

- [x] 1.1 In `xlsx_import/detector.py`, add `("china to russia by cp", "china_post")` and `("china to cis by cp", "china_post")` to the `KEYWORDS` tuple
- [x] 1.2 Remove the `("russia-china cp", "china_post")` entry from `KEYWORDS`
- [x] 1.3 Add a module-level `DEPRECATED_CHINA_POST_SHEETS = {"russia-china cp"}` set
- [x] 1.4 In `detect_format()`, before the existing `_detect_by_sheet_names` call, scan the lowercased titles against `DEPRECATED_CHINA_POST_SHEETS`; if any match, `raise ValueError("无法识别xlsx格式: 检测到旧版 China Post (Russia-China CP) 工作表，已不再支持。请联系供应商获取新版 ePacket 文件。工作表: " + str(titles))`
- [x] 1.5 In `_detect_by_headers()`, change the China Post block from `"delivery method" in r5c2 and "pudo" in r5c3` to require `"delivery method" in r5c2 and "price" in r5c3 and "tarification" in _cell_text(ws, 5, 18)`

## 2. China Post parser rewrite

- [x] 2.1 At the top of `xlsx_import/parsers/china_post.py`, define column constants per design Decision 1 (NEW file layout, post column-shift): `HEADER_ROW = 5`, `COL_METHOD = 1`, `COL_PRICE = 2`, `COL_DAYS = 3`, `COL_BATTERIES = 4`, `COL_LIQUIDS = 5`, `COL_MEASUREMENTS = 6`, `COL_WEIGHT_MIN = 7`, `COL_WEIGHT_MAX = 8`, `COL_CNY_MIN = 11`, `COL_CNY_MAX = 12`, `COL_TARIFICATION = 17`, `COL_VOLUME_CALC = 18`, `MAX_COL = 19`
- [x] 2.2 Replace every numeric `values[i]` index in the existing per-row block with the named constant. NOTE the existing parser indices match the OLD file and are OFF-BY-ONE for the new file at fields from Batteries onward. Specifically swap: `values[3]`→`values[COL_DAYS]` (unchanged), `values[2]`→`values[COL_PRICE]` (unchanged), `values[5]`→`values[COL_BATTERIES]` (was 5, now 4), `values[6]`→`values[COL_LIQUIDS]` (was 6, now 5), `values[7]`→`values[COL_MEASUREMENTS]` (was 7, now 6), `values[8]`→`values[COL_WEIGHT_MIN]` (was 8, now 7), `values[9]`→`values[COL_WEIGHT_MAX]` (was 9, now 8), `values[12]`→`values[COL_CNY_MIN]` (was 12, now 11), `values[13]`→`values[COL_CNY_MAX]` (was 13, now 12), `values[18]`→`values[COL_TARIFICATION]` (was 18, now 17), `values[19]`→`values[COL_VOLUME_CALC]` (was 19, now 18)
- [x] 2.3 Update the values-list comprehension to `range(1, MAX_COL + 1)` so we read 19 cells (indices 0..18 covering columns A..S); cells from spreadsheet column T (index 19+) are not loaded into memory
- [x] 2.4 Define `TARGET_SHEETS = {"china to russia by cp": "RU", "china to cis by cp": None}` and `CIS_COUNTRY_KEYWORDS = [("kazakhstan", "KZ"), ("belarus", "BY"), (" am ", "AM"), (" uz ", "UZ"), (" az ", "AZ")]` per design Decisions 2 and 3
- [x] 2.5 Implement `_resolve_cis_destination(name_text: str) -> str | None` that lowercases, replaces `/` with space, brackets with leading and trailing space, then scans `CIS_COUNTRY_KEYWORDS` returning the first match or `None`
- [x] 2.6 Extract the per-row body into a new helper `_parse_sheet(ws, default_dest, result, source_name) -> None` that loops `range(HEADER_ROW + 1, ws.max_row + 1)`, reads `values = [ws.cell(row_num, col).value for col in range(1, MAX_COL + 1)]`, skips blank rows, derives `name_text`, resolves `destination` (use `default_dest` if not None, else `_resolve_cis_destination(name_text)`; if both yield None increment `result["skipped"]`, append a structured error to `result["errors"]`, and continue), then runs the existing field-extraction block and sets `item["destination"] = destination` before appending
- [x] 2.7 Refactor `parse(source, filepath, source_file)` to iterate `wb.sheetnames`, normalize via `sheet_name.strip().lower()`, look up in `TARGET_SHEETS`, dispatch to `_parse_sheet` per matched sheet, accumulate into one shared `result` dict
- [x] 2.8 Remove the obsolete `next(ws for ws in wb.worksheets if "russia-china cp" in ws.title.lower())` lookup
- [x] 2.9 Verify the air/land classification block is unchanged (`"air" if "eems" in name_text.lower() or "air delivery" in name_text.lower() else "land"`); verified correct for all 14 rows in design Decision 5

## 3. Test updates

- [x] 3.1 In `tests/test_xlsx_import.py`, update the `test_detect_format_matches_reference_workbooks` parametrize entry from `"China_post_10_2_26_ENG_CN_1770625401.xlsx"` to `"China_post_HELP_ePacket_AM_AZ_UZ_1776238342.xlsx"` (still expects `"china_post"`)
- [x] 3.2 Replace `test_parse_file_china_post_returns_expected_core_fields` with a version that loads the new fixture, asserts `len(result["rows"]) == 14`, asserts every row has a populated `destination`, and re-asserts the `China Post to PUDO Standard` row's core fields (base_fee=1.9, continue_fee=0.067, continue_unit="1g", min_days=10, max_days=15, allow_battery=0, destination="RU") — these values are unchanged between old and new files
- [x] 3.3 Add `test_parse_file_china_post_assigns_cis_destinations` that loads the new fixture and asserts the destination distribution: 7 rows with `destination == "RU"`, 2 with `"KZ"`, 2 with `"BY"`, 1 each with `"AM"`, `"UZ"`, `"AZ"`
- [x] 3.4 Add `test_parse_file_china_post_handles_comma_decimals` that finds the Kazakhstan air row and asserts `base_fee == 1.7` and `continue_fee == 0.04675` (proves comma-decimal parsing works)
- [x] 3.5 Add `test_parse_file_china_post_eems_is_air_with_volume_mode` that finds the eEMS row and asserts `type == "air"`, `volume_mode == "longest_side"`, `longest_side_threshold == 40`, `volume_coefficient == 6000.0`
- [x] 3.6 Add `test_parse_file_china_post_belarus_ground_is_land` that finds the Belarus ground row and asserts `type == "land"`, `destination == "BY"`
- [x] 3.7 Add `test_detect_format_rejects_legacy_china_post` that calls `detect_format` on the legacy fixture path and asserts `pytest.raises(ValueError, match="检测到旧版 China Post")`

## 4. End-to-end verification

- [x] 4.1 Run `python -m pytest tests/test_xlsx_import.py -q` and confirm green
- [x] 4.2 Run `python -m pytest --tb=short -q` (full suite) and confirm green (or pre-existing failures only — document any)
- [x] 4.3 Run `python -m flake8 xlsx_import/parsers/china_post.py xlsx_import/detector.py xlsx_import/common.py tests/test_xlsx_import.py` and confirm clean
- [x] 4.4 Start backend locally (per AGENTS.md backend startup template), upload `xlsx/China_post_HELP_ePacket_AM_AZ_UZ_1776238342.xlsx` via `Invoke-RestMethod` against the import endpoint — POST /api/logistics-pool/import 返回 `{"imported":14,"skipped":0,"errors":[]}`
- [x] 4.5 Query `LogisticsPool` (via API or DB) to confirm 14 rows with the expected `destination` distribution (RU ×7, KZ ×2, BY ×2, AM ×1, UZ ×1, AZ ×1) — GET /api/logistics-pool 返回正确分布；type 分布 air=9 land=5 也符合预期
- [x] 4.6 Spot-check one Russia row and one CIS row against the source spreadsheet for correct rate, weight limits, CNY price limits, transport type, and `volume_mode`/`volume_coefficient` — RU eEMS: type=air, volume_mode=longest_side, threshold=40, coef=6000, first_fee=102, continue_fee=2.55, max_weight=31000, days 9-20 ✓；AZ ePacket air: type=air, dest=AZ, max_weight=2000, days 25-35, continue_fee=0.128 ✓
- [x] 4.7 Upload the legacy `xlsx/China_post_10_2_26_ENG_CN_1770625401.xlsx` and confirm the API returns the deprecation `ValueError` message without inserting rows — HTTP 400 `{"detail":"上传文件格式有误，请检查后重试"}`，0 行写入；解析层 ValueError 已被 endpoint 转换为用户友好的中文提示

## 5. Wrap-up

- [x] 5.1 Delete the temporary inspection scripts — 已删除 `scripts/_inspect_cols.py`、`_inspect_new_cp.py`、`_inspect_old_cols.py`、`_smoke_china_post.py`
- [x] 5.2 Run `openspec status --change adapt-china-post-new-xlsx` and confirm all artifacts done and `applyRequires` satisfied — `Progress: 4/4 artifacts complete` + `openspec validate --strict` 通过
- [ ] 5.3 Hand off to `/opsx-archive` once the user has accepted the implementation in production — 待用户确认后由 `/opsx-archive` 执行
