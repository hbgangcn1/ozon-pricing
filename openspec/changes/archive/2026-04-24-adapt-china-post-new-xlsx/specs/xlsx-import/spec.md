## ADDED Requirements

### Requirement: China Post importer SHALL accept the new two-sheet workbook format

The China Post xlsx importer SHALL parse supplier files that contain the worksheets `China to Russia by CP` and `China to CIS by CP ` (trailing space preserved as supplied). Both worksheets SHALL be processed in a single upload, and Chinese mirror sheets (e.g. `中国至俄罗斯-邮政`, `中国至独联体-邮政`) SHALL be ignored.

#### Scenario: Both target sheets are processed
- **WHEN** a workbook containing `China to Russia by CP`, `中国至俄罗斯-邮政`, `China to CIS by CP `, and `中国至独联体-邮政` is uploaded
- **THEN** the importer reads rows from the two English sheets and skips the two Chinese mirror sheets
- **AND** the result contains 7 rows from the Russia sheet and 7 rows from the CIS sheet (14 total)

#### Scenario: Sheet name with trailing space is matched
- **WHEN** the importer encounters a sheet literally named `China to CIS by CP ` (with one trailing space)
- **THEN** the sheet is recognised as the CIS target sheet and its rows are parsed

#### Scenario: Workbook missing both target sheets is rejected
- **WHEN** an uploaded workbook contains neither `China to Russia by CP` nor `China to CIS by CP `
- **THEN** the importer returns an error indicating the file is not a supported China Post format
- **AND** no rows are written to `LogisticsPool`

### Requirement: Legacy single-sheet China Post format SHALL be rejected with a clear error

The importer SHALL fail fast when an uploaded workbook contains the legacy `Russia-China CP` sheet name. It SHALL NOT silently import zero rows or partial data. The error SHALL be raised as a `ValueError` whose message is distinguishable from the generic "unknown format" error and references the new ePacket file as the required input.

#### Scenario: Legacy file upload is rejected
- **WHEN** a user uploads a workbook whose only English sheet is `Russia-China CP`
- **THEN** `detect_format` raises `ValueError` whose message contains the substring `检测到旧版 China Post`
- **AND** no rows are written to `LogisticsPool`

### Requirement: Column mapping SHALL be defined by named constants

For each row in either target sheet, the importer SHALL read fields from the following columns. The new file's column layout differs from the legacy file by a left-shift of one column starting at column E (the legacy file's column E "Courier" was removed by the supplier; everything from Batteries onward shifted left by one column position).

`values` is built as `[ws.cell(row, col).value for col in range(1, MAX_COL + 1)]`, so `values[i]` corresponds to spreadsheet column `i + 1` (e.g. `values[1]` = column B, `values[17]` = column R).

| Field | Spreadsheet column (NEW file) | `values[i]` | Constant |
|---|---|---|---|
| Delivery method (name) | B | `values[1]` | `COL_METHOD = 1` |
| Price (rate string) | C | `values[2]` | `COL_PRICE = 2` |
| Time-limits (delivery days) | D | `values[3]` | `COL_DAYS = 3` |
| Batteries policy | E | `values[4]` | `COL_BATTERIES = 4` |
| Liquids policy | F | `values[5]` | `COL_LIQUIDS = 5` |
| Measurements (size limits text) | G | `values[6]` | `COL_MEASUREMENTS = 6` |
| Weight min (grams) | H | `values[7]` | `COL_WEIGHT_MIN = 7` |
| Weight max (grams) | I | `values[8]` | `COL_WEIGHT_MAX = 8` |
| CNY price min | L | `values[11]` | `COL_CNY_MIN = 11` |
| CNY price max | M | `values[12]` | `COL_CNY_MAX = 12` |
| Tarification type (drives volume_mode) | R | `values[17]` | `COL_TARIFICATION = 17` |
| Volume weight calculation (drives volume_coefficient) | S | `values[18]` | `COL_VOLUME_CALC = 18` |

`MAX_COL = 19`. The values list is built by `[ws.cell(row, col).value for col in range(1, MAX_COL + 1)]`, producing 19 cells at indices 0..18 (spreadsheet columns A..S). Spreadsheet columns from T (cell index 19 / `cell(row, 20)` and beyond) — including the cancellation policies and return-flow text appended by the supplier — SHALL NOT be read or persisted. EUR price-limit columns at P/Q (`values[15]`/`values[16]`) are inside the read range but SHALL NOT be persisted.

#### Scenario: Russia sheet row maps every supported field correctly
- **WHEN** the importer reads row 6 of `China to Russia by CP` (`China Post to PUDO Standard (air delivery)`)
- **THEN** the resulting `LogisticsPool` row has `name` containing `'China Post to PUDO Standard'`, `min_days = 10`, `max_days = 15`, `base_fee = 1.9`, `continue_fee = 0.067`, `continue_unit = '1g'`, `min_weight = 0`, `max_weight = 500`, `price_min_cny = 0.01`, `price_limit_cny = 135.0`, `volume_mode = 'none'` (from `'Physical weight'`), `volume_coefficient = 0.0` (from `'-'`)
- **AND** EUR limits and cancellation/return text are not present anywhere on the row

#### Scenario: Columns from T onward are ignored even if non-empty
- **WHEN** the importer reads any row whose columns T/U/V contain text such as `Disposal without additional payment`
- **THEN** that text is not stored in `LogisticsPool` and does not affect any other field

### Requirement: Destination country SHALL be resolved per row

Every imported row SHALL have a `destination` field populated with an ISO 3166-1 alpha-2 code. Rows from the Russia sheet SHALL set `destination = 'RU'`. Rows from the CIS sheet SHALL derive `destination` from keywords in the delivery method name:

- `Kazakhstan` → `KZ`
- `Belarus` → `BY`
- standalone token `AM` → `AM`
- standalone token `UZ` → `UZ`
- standalone token `AZ` → `AZ`

If a CIS row's name matches none of these keywords, the row SHALL be counted in `result['skipped']`, an error SHALL be appended to `result['errors']`, and the row SHALL NOT be written to `LogisticsPool`.

#### Scenario: Russia sheet rows get RU
- **WHEN** any row from `China to Russia by CP` is imported
- **THEN** its `destination` equals `'RU'`

#### Scenario: CIS row with country name is mapped to ISO code
- **WHEN** the importer reads a CIS row named `China Post ePacket Kazakhstan (air delivery)`
- **THEN** the row's `destination` equals `'KZ'`

#### Scenario: CIS row with short code token is mapped
- **WHEN** the importer reads a CIS row named `China Post ePacket AM (air delivery)`
- **THEN** the row's `destination` equals `'AM'`

#### Scenario: CIS row with unknown country is skipped
- **WHEN** the importer reads a CIS row whose name contains none of the recognised country keywords
- **THEN** the row is added to `result['skipped']`, an error message is appended to `result['errors']`, and the row is not persisted

### Requirement: Air vs land classification SHALL be preserved

The importer SHALL classify each row as `air` or `land` using the existing rule: a method name containing the substring `eems` (case-insensitive) or the phrase `air delivery` is classified as `air`; all other names are classified as `land`. This rule SHALL apply uniformly to both the Russia and CIS sheets.

#### Scenario: eEMS without parenthetical is air
- **WHEN** the importer reads `China Post eEMS`
- **THEN** the row's transport type is `air`

#### Scenario: eParcel Economy without parenthetical is land
- **WHEN** the importer reads `China Post eParcel Economy`
- **THEN** the row's transport type is `land`

#### Scenario: Ground delivery row is land
- **WHEN** the importer reads `China Post ePacket Economy Track (ground delivery)` or `China Post ePacket Economy Belarus (ground delivery)`
- **THEN** the row's transport type is `land`

### Requirement: Russian comma-decimal rate strings SHALL parse correctly

`parse_rate` in `xlsx_import/common.py` SHALL parse rate strings whose numeric tokens use a comma as the decimal separator (e.g. `¥1,70+¥0,04675/1g`) equivalently to dot-decimal strings (`¥1.70+¥0.04675/1g`). The current implementation already satisfies this requirement via its `text.replace(",", ".")` step prior to the numeric regex; this requirement codifies that behaviour so it is not regressed when the function is later refactored. No code change is needed in this OpenSpec change.

#### Scenario: Comma-decimal rate yields the same result as dot-decimal
- **WHEN** `parse_rate('pick-up point  \n¥1,70+¥0,04675/1g')` is called
- **THEN** the returned tuple equals `parse_rate('pick-up point  \n¥1.70+¥0.04675/1g')`

#### Scenario: CIS Kazakhstan air row's rate parses as expected
- **WHEN** the importer reads CIS row 6 (`China Post ePacket Kazakhstan (air delivery)` with price text `pick-up point\n¥1,70+¥0,04675/1g`)
- **THEN** the resulting `LogisticsPool` row has `base_fee = 1.7`, `continue_fee = 0.04675`, `continue_unit = '1g'`
