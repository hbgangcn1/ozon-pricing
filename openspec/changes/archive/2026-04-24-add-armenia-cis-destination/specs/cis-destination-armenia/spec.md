## ADDED Requirements

### Requirement: China Post NEW xlsx multi-sheet parsing SHALL be supported

The xlsx import detector and China Post parser SHALL support the new China Post xlsx format (e.g. `China_post_HELP_ePacket_AM_AZ_UZ_*.xlsx`) which contains multiple worksheets covering RU, CIS countries (KZ/BY/AM/UZ/AZ etc.), and eParcel methods. The detector SHALL identify China Post format via KEYWORDS-first anchors (e.g. "China Post", "ePacket") rather than a single fixed sheet name. The parser SHALL iterate all matching sheets, parse each independently, and merge the results into a single rule list.

#### Scenario: NEW xlsx with multiple sheets is fully imported
- **WHEN** a user uploads `China_post_HELP_ePacket_AM_AZ_UZ_1776238342.xlsx` to `POST /api/logistics-pool/import`
- **THEN** the response is `{imported: 14, skipped: 0, errors: []}`
- **AND** the imported rules cover destinations `{RU: 7, KZ: 2, BY: 2, AM: 1, UZ: 1, AZ: 1}` exactly matching the xlsx content

#### Scenario: Detector identifies NEW xlsx via keyword anchors
- **WHEN** the detector scans an xlsx whose sheet names do not match the legacy `Russia-China CP` pattern but contain China Post / ePacket keyword anchors in headers or sheet names
- **THEN** the detector classifies the file as China Post format
- **AND** the China Post parser is invoked on all matching sheets

### Requirement: China Post parser SHALL resolve destination per row

The China Post parser SHALL determine each rule's destination ISO code on a per-row basis, by inspecting the method name (e.g. `EMS-AM`, `ePacket-KZ`) and/or the containing sheet name. The destination SHALL NOT be assumed from a single sheet-level default. Supported destinations include `RU, KZ, BY, KGZ, UZ, GE, AZ, AM`.

#### Scenario: AM is resolved from method name token
- **WHEN** the parser encounters a row with method name containing `AM` token (e.g. `EMS-AM`, `ePacket AM`)
- **THEN** the row's destination is set to `AM`
- **AND** the row is included in the imported rule list

#### Scenario: Mixed-destination sheet rows are correctly classified
- **WHEN** a single sheet contains rows for multiple destinations (e.g. CIS sheet with KZ/BY/AM/UZ/AZ rows)
- **THEN** each row's destination is independently resolved from its method name
- **AND** the merged result preserves the per-row destination assignment

### Requirement: Legacy `Russia-China CP` xlsx SHALL fail loud (BREAKING)

The xlsx import detector SHALL reject any xlsx file containing a worksheet named `Russia-China CP` (the legacy single-sheet China Post format). The detector SHALL raise `ValueError` with a clear message indicating the legacy format is no longer supported. This is a BREAKING change: users with old xlsx files MUST obtain the new multi-sheet xlsx from the supplier.

#### Scenario: OLD xlsx upload is rejected with clear error
- **WHEN** a user uploads an xlsx containing a `Russia-China CP` worksheet (e.g. `China_post_10_2_26_ENG_CN_*.xlsx`)
- **THEN** the import operation raises `ValueError` with message `检测到旧版 China Post (Russia-China CP) 工作表,已不再支持`
- **AND** zero rules are imported
- **AND** no silent fallback or partial import occurs

### Requirement: Empty parse result SHALL fail loud

The China Post parser SHALL raise `ValueError` if zero matching sheets are found OR zero rules are extracted from all matching sheets. The parser SHALL NOT return an empty list silently, to prevent the historical "import succeeded but pool is empty" silent failure.

#### Scenario: Zero sheets matched raises ValueError
- **WHEN** the parser is invoked on an xlsx whose sheets do not contain any China Post anchors
- **THEN** the parser raises `ValueError` with a message indicating no matching sheets were found

#### Scenario: Zero rows extracted raises ValueError
- **WHEN** the parser identifies matching sheets but extracts zero valid data rows from all of them combined
- **THEN** the parser raises `ValueError` with a message indicating no valid rows were extracted

### Requirement: Backend CIS grouping SHALL include Armenia (AM)

The backend pricing grouping logic SHALL recognise `'AM'` as a valid CIS destination code, alongside `KZ`, `BY`, `KGZ`, `UZ`, `GE`, `AZ`. Logistics rows with `destination='AM'` SHALL be classified into the CIS group (not the "other" group), and the grouped pricing API response SHALL emit a `rfbs_AM` key.

#### Scenario: AM rule is grouped under CIS, not other
- **WHEN** the grouped pricing logic processes a logistics rule with `destination='AM'` and `method_type='rfbs'`
- **THEN** the rule is placed in the CIS group (the same group as KZ/BY/KGZ/UZ/GE/AZ rfbs rules)
- **AND** the resulting grouped dictionary contains a key `rfbs_AM` whose value is a list of matching rules

#### Scenario: AM key appears in pricing API response even when empty
- **WHEN** the pricing API computes grouped results for a user who has no AM rules
- **THEN** the response's `grouped` object contains the key `rfbs_AM` with an empty array value (not omitted)

### Requirement: Frontend logistics edit page SHALL allow Armenia as rFBS destination

The frontend logistics edit form (`LogisticsBasicSection.jsx`) SHALL allow the user to select `AM (亚美尼亚)` as a destination when the selected method type is rFBS. AM SHALL NOT appear in the destination dropdown when the method type is FBP economy or FBP standard. This matches the existing rule applied to KGZ, UZ, GE, and AZ.

#### Scenario: AM is selectable under rFBS method type
- **WHEN** the user opens the logistics edit page and selects method type `rfbs`
- **THEN** the destination dropdown includes the option `亚美尼亚(AM)` with value `AM`
- **AND** the option is positioned in the rFBS branch's CIS country group (after AZ, before any non-CIS options)

#### Scenario: AM is NOT selectable under FBP method types
- **WHEN** the user selects method type `fbp_economy` or `fbp_standard`
- **THEN** the destination dropdown does NOT include `AM` as an option

### Requirement: Frontend logistics list filter SHALL support Armenia

The logistics list page's destination filter dropdown (`FILTER_DESTINATION_OPTIONS`) SHALL include `AM (亚美尼亚)` as a filter value, allowing the user to filter logistics rules by `destination='AM'`.

#### Scenario: AM appears in destination filter dropdown
- **WHEN** the user opens the logistics list page and clicks the destination filter dropdown
- **THEN** the dropdown includes the option `亚美尼亚(AM)` with value `AM`
- **AND** selecting it filters the visible rows to only those with `destination='AM'`

### Requirement: Frontend pricing result rFBS-CIS sub-tabs SHALL include Armenia

The pricing result page's rFBS-独联体 (CIS) tab section SHALL render a sub-tab for `亚美尼亚` (key: `rfbs_AM`). The CIS country list (`CIS_COUNTRIES` in `pricingConstants.js`) SHALL contain AM as the seventh entry, appended after AZ. The CSS grid containing the CIS sub-tab buttons SHALL use `grid-cols-7` to fit all seven country tabs in a single row of equal width.

#### Scenario: AM tab is rendered after AZ
- **WHEN** the pricing result page is displayed and the user opens the rFBS-独联体 tab
- **THEN** seven country sub-tabs are rendered in this order: 哈萨克斯坦, 白俄罗斯, 吉尔吉斯斯坦, 乌兹别克斯坦, 格鲁吉亚, 阿塞拜疆, 亚美尼亚
- **AND** all seven tabs are arranged in a single row using `grid-cols-7`

#### Scenario: AM tab displays the correct grouped data
- **WHEN** the user clicks the 亚美尼亚 sub-tab
- **THEN** the displayed pricing rows are exactly those from the API response's `grouped.rfbs_AM` array

### Requirement: CIS rFBS xlsx parser DEST_MAP SHALL include Armenia

The xlsx import parser `xlsx_import/parsers/cis_rfbs.py` SHALL include AM in its `DEST_MAP` country-name-to-ISO-code mapping. This is a consistency requirement; the China Post parser does not use this map, but other future CIS rFBS supplier formats may. The mapping SHALL recognise both `armenia` (case-insensitive full name) and `AM` (standalone token) as resolving to ISO code `AM`.

#### Scenario: armenia full name maps to AM
- **WHEN** the cis_rfbs parser encounters a sheet column or cell containing `Armenia` (any case)
- **THEN** the parser resolves the destination to ISO code `AM`

#### Scenario: AM standalone token maps to AM
- **WHEN** the cis_rfbs parser encounters a column header or row containing the standalone token `AM`
- **THEN** the parser resolves the destination to ISO code `AM`

### Requirement: Pool-to-private import SHALL preserve Armenia destination

When a logistics rule with `destination='AM'` is imported from `LogisticsPool` (public pool) into a user's private `Logistics` table via the batch-add endpoint, the `destination='AM'` value SHALL be preserved unchanged in the destination column. The receiving user SHALL be able to see and edit this rule under the AM (亚美尼亚) tab/option in the frontend.

#### Scenario: AM rule survives pool→private copy
- **WHEN** a `LogisticsPool` row with `destination='AM'` is copied into a user's private `Logistics` table via the batch-add API
- **THEN** the new `Logistics` row has `destination='AM'` (no transformation, no fallback to RU)

#### Scenario: Private AM rule is editable in frontend
- **WHEN** a user opens the logistics edit page for a private rule with `destination='AM'` and `method_type='rfbs'`
- **THEN** the destination dropdown displays `亚美尼亚(AM)` as the currently selected value
- **AND** saving the form without changes does not alter the destination value
