## Why

The China Post logistics rate file changed from `China_post_10_2_26_ENG_CN_1770625401.xlsx` (single sheet `Russia-China CP`) to `China_post_HELP_ePacket_AM_AZ_UZ_1776238342.xlsx` (two sheets: `China to Russia by CP` and `China to CIS by CP `). The current importer reads the old layout and either errors out or writes column-shifted, garbage data when fed the new file. The business needs CIS-country routes (KZ, BY, AM, UZ, AZ) imported alongside Russia routes, and the old file is being retired upstream.

## What Changes

- **BREAKING**: Drop support for the old `Russia-China CP` single-sheet layout. The importer only accepts the new two-sheet format going forward.
- Add multi-sheet iteration to the China Post parser (mirrors the existing `cis_rfbs.py` pattern) so both `China to Russia by CP` and `China to CIS by CP ` (note trailing space) are processed in one upload.
- Per-row destination resolution: Russia sheet rows → `destination = 'RU'`; CIS sheet rows → ISO country code parsed from the delivery method name (`Kazakhstan`→`KZ`, `Belarus`→`BY`, `AM`/`UZ`/`AZ` literal).
- Re-map column indices to the new layout (PUDO + Courier columns merged into a single `Price` column; everything from column E onward shifts left by one).
- `volume_mode` continues to be derived from the Tarification type column (now column R / index 17 in the new layout).
- `volume_coefficient` continues to be derived from the Volume weight calculation column (now column S / index 18 in the new layout).
- Ignore new columns introduced by the source file: EUR min/max (P/Q), Canceled shipment policies (T/U/V), and any trailing return-flow columns. RUB min/max and USD min/max are also not imported (matches existing behaviour — only CNY price limits are persisted).
- Air/land classification preserved unchanged: `eems` keyword → `air`, `air delivery` keyword → `air`, otherwise `land`. Verified against all 13 service rows in the new file.
- Extend `parse_rate` in `xlsx_import/common.py` to accept Russian comma-decimal numbers (`¥1,70+¥0,04675/1g`) used by CIS rows, in addition to the existing dot-decimal format.
- Update the China Post sheet detector in `xlsx_import/detector.py` to match the two new sheet names and rework `_detect_by_headers()` so it no longer requires the now-removed `PUDO` column header.
- Replace China Post test fixtures and assertions to cover the new file (Russia + CIS sheets, per-country destinations, comma-decimal rate parsing, air/land classification edge cases like `China Post eEMS` and `China Post eParcel Economy`). Remove or skip tests bound to the retired old file.

## Capabilities

### New Capabilities

- `xlsx-import`: Parsing of supplier rate-card spreadsheets (China Post and other carriers) into `LogisticsPool` rows, including sheet detection, column mapping, value normalization, and destination resolution. This change formalizes the requirements that the China Post parser must satisfy and the contract between the detector and per-carrier parsers.

### Modified Capabilities

(None — `xlsx-import` did not previously exist as a tracked spec.)

## Impact

- **Affected code**:
  - `xlsx_import/parsers/china_post.py` — rewritten for two-sheet iteration, new column indices, per-row destination, retains volume_mode/coefficient logic on shifted columns.
  - `xlsx_import/detector.py` — sheet-name keyword list updated; `_detect_by_headers()` rule no longer keys on `PUDO`.
  - `xlsx_import/common.py` — `parse_rate` extended for Russian comma decimals.
  - `tests/` — new fixture for the new file, new assertions for both sheets, removal/skip of old-file-specific tests.
- **Affected APIs**: None. `POST /api/products/import` (or equivalent China Post upload endpoint) keeps its contract; only the file format it accepts changes.
- **Database schema**: No migration. EUR, Tarification text, and cancellation policy columns are intentionally not persisted, so no new fields are needed on `LogisticsPool`.
- **Frontend**: No change. The upload UI is format-agnostic.
- **Operational risk**: Low. Changes are scoped to the importer module; old-file uploads will fail fast at the detector with a clear "unsupported sheet layout" error rather than silently importing garbage.
