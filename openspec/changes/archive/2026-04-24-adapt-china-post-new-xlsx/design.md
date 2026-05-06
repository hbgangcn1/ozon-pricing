## Context

`xlsx_import/parsers/china_post.py` was authored against the old supplier file `China_post_10_2_26_ENG_CN_1770625401.xlsx`, which had:
- One English sheet `Russia-China CP` (plus a Chinese mirror that the parser ignored).
- All routes terminating in Russia (`destination='RU'`).

The supplier replaced this with `China_post_HELP_ePacket_AM_AZ_UZ_1776238342.xlsx`, which has:
- Two English sheets: `China to Russia by CP` and `China to CIS by CP ` (the CIS sheet name has a literal trailing space) plus two Chinese mirror sheets that must be skipped.
- **Column layout shifted LEFT by one starting at column E** because the old file's column E "Courier" was removed. Verified by reading both workbooks header row 5:
  - Old file row 5: B=Method, C=PUDO, D=Days, **E=Courier**, F=Batteries, G=Liquids, H=Measurements, I=Wmin, J=Wmax, K=RUBmin, L=RUBmax, M=CNYmin, N=CNYmax, O=USDmin, P=USDmax, Q=EURmin, R=EURmax, S=Tarification, T=VolumeCalc, U/V=Cancellation
  - New file row 5: B=Method, C=Price, D=Days, **E=Batteries**, F=Liquids, G=Measurements, H=Wmin, I=Wmax, J=RUBmin, K=RUBmax, L=CNYmin, M=CNYmax, N=USDmin, O=USDmax, P=EURmin, Q=EURmax, R=Tarification, S=VolumeCalc, T/U/V=Cancellation
  - Net effect: every field from Batteries (col E) onward shifts LEFT by 1 column. Columns from T onward in the new file (cancellation policies, return flow) must be ignored.
- CIS sheet has 7 rows across 5 destination countries, encoded in the delivery method name: Kazakhstan ×2, Belarus ×2, AM ×1, UZ ×1, AZ ×1.
- CIS sheet uses Russian-style decimal commas in the price string (e.g. `¥1,70+¥0,04675/1g`); the Russia sheet keeps dot decimals (`¥1.90+¥0.067/1 г`). The existing `common.parse_rate` already normalises commas to dots via `.replace(",", ".")`, so no helper change is needed.

The detector (`xlsx_import/detector.py`) currently routes China Post files via:
1. Sheet-name keyword `russia-china cp`.
2. Header sniffing on `delivery method` + `pudo`.

The new file no longer contains either signal: the sheet names changed and the column-3 header is now `Price` instead of `PUDO`. Detection breaks before parsing is even attempted.

The `LogisticsPool` model already has the fields we need (`destination`, `volume_mode`, `volume_coefficient`, `longest_side_threshold`, `sum_of_sides_threshold`, CNY min/max, fee structure) and it does not store EUR or Tarification text. No DB migration is required.

## Goals / Non-Goals

**Goals:**
- Cleanly import all 14 services from the new file (7 Russia rows + 7 CIS rows) in a single upload.
- Produce one `LogisticsPool` row per service with the correct `destination` country code (RU / KZ / BY / AM / UZ / AZ).
- Preserve existing parsing semantics for fields that did not change meaning (rate / days / weight / size / batteries / liquids / CNY price limits / volume_mode / volume_coefficient / air-vs-land classification).
- Make the column-index mapping explicit and centralized so future supplier-file shifts are easy to re-target.
- Fail fast with a clear error if someone uploads the legacy file format.

**Non-Goals:**
- Persisting EUR price limits, Tarification type text, cancellation policies, or return-flow text.
- Supporting both old and new file formats simultaneously.
- Refactoring the broader xlsx_import architecture (detector, common helpers, other carrier parsers) beyond what this change strictly needs.
- Changing the upload API contract or the frontend upload flow.
- Adding a new exception class — reuse `ValueError` with `"无法识别xlsx格式"` message for consistency with the existing detector contract (`tests/test_xlsx_import.py:136`).
- Migrating existing `LogisticsPool` rows in the database (out of scope; users are expected to clear and re-import the China Post pool with the new file).

## Decisions

### Decision 1: Use a column-index constants table instead of magic numbers

Define module-level constants at the top of `china_post.py`. Values use openpyxl's 1-indexed `ws.cell(row, col)` convention; the parser builds `values = [ws.cell(row, col).value for col in range(1, MAX_COL + 1)]`, so `values[i]` corresponds to spreadsheet column `i + 1` (i.e. `values[1]` = column B, `values[17]` = column R).

```python
HEADER_ROW = 5
COL_METHOD = 1          # B → values[1]
COL_PRICE = 2           # C → values[2]
COL_DAYS = 3            # D → values[3]
COL_BATTERIES = 4       # E → values[4]   (old file had Courier here at values[5])
COL_LIQUIDS = 5         # F → values[5]
COL_MEASUREMENTS = 6    # G → values[6]
COL_WEIGHT_MIN = 7      # H → values[7]
COL_WEIGHT_MAX = 8      # I → values[8]
COL_CNY_MIN = 11        # L → values[11]
COL_CNY_MAX = 12        # M → values[12]
COL_TARIFICATION = 17   # R → values[17]  (old file had EUR-max here)
COL_VOLUME_CALC = 18    # S → values[18]  (old file had Tarification here)
MAX_COL = 19            # read columns 1..19 (A..S); cells from col 20 (T) onward are ignored
```

These constants reflect the **NEW** file layout, which differs from the old file by a left-shift of 1 column starting at column E (the old "Courier" column was removed). The current `china_post.py` uses raw `values[5]`, `values[6]`, `values[12]`, `values[13]`, `values[18]`, `values[19]` etc. — those indices match the OLD file and are off-by-one for the NEW file. This decision both names AND corrects the indices.

**Why**: Eliminates the silent off-by-one risk. Future supplier shifts become a one-block edit. Reviewers can verify the mapping against a printed spreadsheet header without running code.

**Alternatives considered**:
- Keep raw `values[12]` etc. inline → rejected; that's exactly what made the column-shift question hard to answer during exploration.
- Use a `dict` keyed by field name → rejected; constants are dead-simple and play nicely with type checkers.

### Decision 2: Iterate every worksheet with a name allow-list

Pattern modelled on `xlsx_import/parsers/cis_rfbs.py`. Inside `china_post.parse(wb)`:

```python
TARGET_SHEETS = {
    "china to russia by cp": "RU",
    "china to cis by cp": None,   # destination resolved per row
}

for sheet_name in wb.sheetnames:
    key = sheet_name.strip().lower()
    if key not in TARGET_SHEETS:
        continue
    ws = wb[sheet_name]
    default_dest = TARGET_SHEETS[key]
    _parse_sheet(ws, default_dest, result, source_name)
```

`sheet_name.strip().lower()` defends against the literal trailing space in `'China to CIS by CP '` and any future casing drift.

**Why**: Mirrors a working pattern already in the codebase (`cis_rfbs.py`). Skips Chinese mirror sheets (`中国至俄罗斯-邮政`, `中国至独联体-邮政`) automatically because they don't match the allow-list. No reliance on workbook sheet ordering.

**Alternatives considered**:
- Hard-code two `wb[...]` lookups → fragile against the trailing space and future renames.
- Detect by header sniffing per sheet → reuses the detector logic, but adds complexity for no gain since the names are stable upstream.

### Decision 3: Resolve CIS destination by keyword scan of the method name

```python
CIS_COUNTRY_KEYWORDS = [
    ("kazakhstan", "KZ"),
    ("belarus", "BY"),
    (" am ", "AM"),   # spaces avoid matching "ePacket Amazon" etc.
    (" uz ", "UZ"),
    (" az ", "AZ"),
]

def _resolve_cis_destination(name_text: str) -> str | None:
    lower = " " + name_text.lower().replace("/", " ") + " "
    for needle, code in CIS_COUNTRY_KEYWORDS:
        if needle in lower:
            return code
    return None
```

The verified CIS row names look like `'China Post ePacket AM / (air delivery)'` (the `/` comes from the openpyxl conversion of the line-break in the cell). The destination token is whitespace-bordered after that normalisation, so the leading-and-trailing-space guard for the short codes (AM/UZ/AZ) prevents false hits inside English words.

If no keyword matches, the row is counted as `skipped` with a structured error and not written to `LogisticsPool`. This protects against silent data corruption when the supplier adds a country we haven't whitelisted yet.

**Why**: All five current CIS countries are encoded distinctively. The leading-space guard for short codes (AM/UZ/AZ) prevents accidental substring hits inside longer English words. Falling back to `skipped` rather than guessing keeps the import deterministic.

**Alternatives considered**:
- Regex `\b(AM|UZ|AZ)\b` → works too, but the keyword list is easier to extend and review.
- Map by row index → brittle if the supplier adds a row.

### Decision 4: `volume_mode` reads column R (Tarification at values[17]) — honoring the user's "S=T" directive

The user's directive: "新文件 S 列 = 旧文件 T 列, S 列后面的列都不需要处理". Verified: column shift IS real. Old file column T (Volume weight calculation) is the new file column S; old file column S (Tarification type) is the new file column R; old file columns U+ (Cancellation policies) are the new file columns T+.

So `volume_mode` should be derived from `values[17]` (new col R, Tarification text) and `volume_coefficient` from `values[18]` (new col S, VolumeCalc formula). The existing parser uses `values[18]` and `values[19]` respectively — those are the OLD file indices and are off-by-one for the new file. The constants `COL_TARIFICATION = 17` and `COL_VOLUME_CALC = 18` correct this.

Inside `_apply_volume_mode`, replace `normalize_text(values[18])` with `normalize_text(values[COL_TARIFICATION])` and `parse_volume_coeff(values[19])` with `parse_volume_coeff(values[COL_VOLUME_CALC])`. The branching logic itself (triple-condition `longest_side`, blank/dash/`physical weight` → `none`, else `max_actual_vs_volume`) is correct and unchanged.

The eEMS row in the new file (R12) has Tarification text at column R:
```
No side < 40 cm — physical weight;
One side > 40 cm — volume weight
```
which lowercased contains `"no side"`, `"physical weight"`, AND `"one side"` — the existing triple-condition `longest_side` branch matches it. Regex `r"no side\s*[<>≤≥]\s*(\d+)"` captures `40`. Volume coefficient at column S is `'L × W × H (cm) ÷ 6000'` → `parse_volume_coeff` returns `6000.0`.

### Decision 5: Air/land classification stays as-is

Verified all 14 service rows in the new file:

| Row | Method | Expected | Existing rule output |
|---|---|---|---|
| Russia R6 | `China Post to PUDO Standard (air delivery)` | air | air ✅ |
| Russia R7 | `China Post to PUDO Economy (ground delivery)` | land | land ✅ |
| Russia R8 | `China Post ePacket Super Express (air delivery)` | air | air ✅ |
| Russia R9 | `China Post ePacket (air delivery)` | air | air ✅ |
| Russia R10 | `China Post ePacket Economy Track (ground delivery)` | land | land ✅ |
| Russia R11 | `China Post eParcel Economy` | land | land ✅ (no keyword → else branch) |
| Russia R12 | `China Post eEMS` | air | air ✅ (`eems` keyword) |
| CIS R6 | `China Post ePacket Kazakhstan (air delivery)` | air | air ✅ |
| CIS R7 | `China Post ePacket Economy Track Kazakhstan (ground delivery)` | land | land ✅ |
| CIS R8 | `China Post ePacket Belarus (air delivery)` | air | air ✅ |
| CIS R9 | `China Post ePacket Economy Belarus (ground delivery)` | land | land ✅ |
| CIS R10/11/12 | `China Post ePacket AM/UZ/AZ (air delivery)` | air | air ✅ |

**Decision: do not touch the rule.** The current `eems`/`air delivery`/else=`land` triple is already correct for all 14 rows.

### Decision 6: `parse_rate` already handles Russian comma decimals — no helper extension needed

Inspection of `xlsx_import/common.py` line 71 shows `compact = text.replace(" ", "").replace(",", ".")` is already applied before the numeric regex runs. Existing test `test_parse_rate_precision_5_decimals` (line 54) verifies `¥3 + ¥0,035/1g` parses to `0.035`. Therefore the CIS comma-decimal strings (`¥1,70+¥0,04675/1g`) parse correctly today.

**No change to `common.py` is required.** The earlier proposal called for a `_normalize_decimal_separators` helper; that was redundant.

### Decision 7: Detector — replace `PUDO` heuristic, swap sheet-name keywords, fail-fast on legacy

In `xlsx_import/detector.py`:

1. Add `'china to russia by cp'` and `'china to cis by cp'` to the `KEYWORDS` tuple, both mapped to `'china_post'`.
2. Drop `'russia-china cp'` from `KEYWORDS` (legacy; replaced by the explicit deprecation check below).
3. Update `_detect_by_headers()` so the China Post header signature becomes `delivery method` (col 2) + `price` (col 3) + `tarification type` (col 18) — all three required at row 5. The old signature required `pudo` at col 3, which no longer appears in any new file.
4. Add a `DEPRECATED_CHINA_POST_SHEETS = {"russia-china cp"}` set checked **before** `_detect_by_sheet_names`. If any worksheet's normalised title matches, raise `ValueError("无法识别xlsx格式: 检测到旧版 China Post (Russia-China CP) 工作表，已不再支持。请联系供应商获取新版 ePacket 文件。工作表: {titles}")`. Reuses the existing `ValueError` contract (consistent with `tests/test_xlsx_import.py:136`); does **not** introduce a new exception class.

Because sheet-name detection runs before header detection in the existing flow, header sniffing only fires as a fallback. Both pathways now point at the new file shape.

**Why reuse `ValueError` not introduce `UnsupportedFileFormatError`**: the codebase has exactly one detector error path today (`raise ValueError("无法识别xlsx格式...")`), surfaced verbatim by the upload route. Adding a second error class for one call site would force every existing handler / test / frontend message-matcher to grow a branch for no behavioural gain. The legacy-rejection message is sufficiently distinctive on its own.

## Risks / Trade-offs

- **Risk: Supplier adds a sixth CIS country we haven't whitelisted** → Mitigation: row is counted in `result["skipped"]` with an `errors` entry, not silently dropped. Operations can grep the import response for the structured error.
- **Risk: Hard fail on legacy file uploads frustrates users mid-rollout** → Mitigation: the error message points at the new file source so support can hand it out without escalation. Frontend already surfaces import errors verbatim.
- **Trade-off: Choosing not to persist EUR / Tarification / cancellation columns** → Aligns with the user's explicit decision and the `LogisticsPool` schema. If business later needs them, it's a clean additive change (new columns + persistence, no destruction).
- **Trade-off: Two-sheet allow-list is hard-coded** → Future expansion (e.g. China-to-Europe sheet) requires a one-line addition to `TARGET_SHEETS`. Acceptable for the current scope.
- **Trade-off: Reusing `ValueError` for both "unknown format" and "deprecated format"** → Caller cannot programmatically distinguish them. Acceptable: there is no caller today that needs to (the upload route surfaces the message string directly to the user).

## Migration Plan

1. Merge change. Deploy backend.
2. Operations / data team clears the China Post rows from `LogisticsPool` (manual SQL or via an existing admin endpoint).
3. Upload the new `China_post_HELP_ePacket_AM_AZ_UZ_1776238342.xlsx` via the existing import UI.
4. Verify 14 rows imported (7 RU + 7 CIS distributed correctly: KZ ×2, BY ×2, AM ×1, UZ ×1, AZ ×1).
5. Spot-check pricing calculation for one Russia route and one CIS route.

Rollback: revert the change, redeploy. The legacy rows in `LogisticsPool` are unaffected by the parser swap (no schema change), so reverting is purely a code rollback.

## Open Questions

None at change-authoring time. All scope questions and the volume_mode column conflict were resolved with the user before this document was written; the column-shift assumption was disproven by direct workbook inspection during apply.
