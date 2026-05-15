## MODIFIED Requirements

### Requirement: Batch add public pool entries to user logistics

The system SHALL provide `POST /api/logistics-pool/batch-add-to-my-logistics` accepting a JSON body `{"ids": [int, ...]}` and SHALL copy each referenced public pool entry into the authenticated user's logistics table, returning a JSON object `{added: int, not_found: list[int], new_ids: list[int], errors: list[str]}` with HTTP 200.

The endpoint MUST require authentication via the project's standard JWT/cookie dependency. The endpoint MUST enforce the user's subscription logistics quota (`_check_logistics_limit`) BEFORE attempting any insert; if quota would be exceeded the endpoint MUST return the existing quota error (per `_check_logistics_limit` contract) without partial inserts.

`_check_logistics_limit` SHALL resolve the user's effective limit via `services.plan_resolution.get_effective_logistics_limit(session, user)` and SHALL count the user's currently active rules via `services.plan_resolution.count_user_active_rules(session, user_id)`. The function SHALL NOT read `users.subscription_type` directly nor maintain its own hardcoded plan-to-limit mapping. When `get_effective_logistics_limit` returns `-1`, the quota check SHALL pass unconditionally (unlimited). When it returns a positive integer `N`, the request SHALL be rejected if `count_user_active_rules + len(ids) > N`.

Quota rejection SHALL return HTTP 403 with response detail string `"已达到您当前方案的物流规则上限（N 条）"`, where `N` is the resolved limit. The detail SHALL NOT include any internal plan label (e.g. "免费版", "专业版") nor disclose trial status.

The endpoint MUST validate `ids` length explicitly inside the route handler BEFORE Pydantic max_length kicks in: empty list returns HTTP 400 with detail `"ids 不能为空"`; more than 200 ids returns HTTP 400 with detail `"单次最多添加 200 条"`. The Pydantic schema `BatchAddBody.ids` SHALL declare `Field(..., max_length=200)` as a defense-in-depth bound only — the explicit handler check is the contractual source of truth and MUST run first so the response detail is always a plain string, never the Pydantic 422 array `[{type, loc, msg, input, ctx}, ...]`. (NOTE: 400 with string detail is the existing behavior preserved for backward compatibility; this is intentionally NOT 422.)

#### Scenario: Successful full batch
- **WHEN** authenticated user POSTs `{"ids": [p1, p2, p3]}` where all three pool ids exist and quota allows three inserts
- **THEN** response is HTTP 200 with `added=3`, `not_found=[]`, `new_ids` containing 3 new logistics ids, `errors=[]`
- **AND** three new rows exist in the logistics table owned by the user

#### Scenario: Partial not_found
- **WHEN** authenticated user POSTs `{"ids": [p1, 999999]}` where `p1` exists and `999999` does not
- **THEN** response is HTTP 200 with `added=1`, `not_found=[999999]`, `new_ids` containing 1 id, `errors=[]`

#### Scenario: Empty ids rejected with 400
- **WHEN** authenticated user POSTs `{"ids": []}`
- **THEN** response is HTTP 400 with `detail="ids 不能为空"` (string, not array)

#### Scenario: Over-limit ids rejected with 400 string detail
- **WHEN** authenticated user POSTs `{"ids": [...201 ids...]}`
- **THEN** response is HTTP 400 with `detail="单次最多添加 200 条"` (string, not the Pydantic 422 array)
- **AND** the explicit handler length check fires before Pydantic validation produces a 422

#### Scenario: 200 ids accepted (exact boundary)
- **WHEN** authenticated user POSTs `{"ids": [...exactly 200 ids...]}` and quota allows
- **THEN** response is HTTP 200; no 422 / no 400; processing proceeds via the SAVEPOINT loop

#### Scenario: 51 ids accepted (regression guard for old max_length=50)
- **WHEN** authenticated user POSTs `{"ids": [...51 ids...]}` and quota allows
- **THEN** response is HTTP 200 (NOT HTTP 422 as the prior implementation incorrectly returned)

#### Scenario: Quota exceeded blocks all inserts
- **WHEN** user's effective logistics limit is `N` (positive integer) and the user has `K` currently active rules and the request contains `M` ids where `K + M > N`
- **THEN** response is HTTP 403 with `detail="已达到您当前方案的物流规则上限（N 条）"`, zero rows are inserted

#### Scenario: Unlimited plan never blocks
- **WHEN** `get_effective_logistics_limit` returns `-1` for the user
- **THEN** the quota check passes regardless of current row count and request size

#### Scenario: Trial user enjoys professional limit
- **WHEN** user with real `subscription_type='free'` and `trial_expires_at > now` POSTs `{"ids": [...5 ids...]}`, currently has 0 rows, and `plans.professional.logistics_limit = -1`
- **THEN** response is HTTP 200, `added=5` (because `get_effective_logistics_limit` returns -1 via `get_effective_plan -> 'professional' -> plans table -> -1`)

#### Scenario: Quota error detail is plan-agnostic
- **WHEN** any user is rejected by the quota check
- **THEN** response detail SHALL match the literal pattern `"已达到您当前方案的物流规则上限（N 条）"` and SHALL NOT contain any plan label or trial wording

## ADDED Requirements

### Requirement: Frontend multi-batch quota semantics for "add all"

The frontend `LogisticsPoolPage` "add selected to my logistics" flow SHALL split the selected pool ids into sequential POST batches of size `BATCH_SIZE = 200` (matching the backend per-request cap defined above). Each batch is an independent atomic request from the backend's perspective; the frontend SHALL coordinate cross-batch behavior per the rules below.

The frontend SHALL await each batch's response before issuing the next; concurrent batch requests are FORBIDDEN (sequential ordering ensures deterministic quota arithmetic and predictable failure handling).

When any batch returns HTTP 403 (quota exceeded), the frontend SHALL immediately STOP issuing subsequent batches. The frontend SHALL NOT call `undo` or attempt to roll back successful prior batches — the backend contract is "single-request atomic, cross-request independent".

When any batch returns a non-403 network or 5xx error, the frontend SHALL also STOP subsequent batches (avoid lossy mid-progress state) and surface a clear error toast.

After the loop terminates (full success / quota stop / error stop), the frontend SHALL invoke `fetchLogistics()` exactly once to refresh the list, regardless of outcome.

After the loop terminates, the frontend SHALL update selection state to retain only the ids that were neither successfully added nor explicitly rejected as `not_found`. Successfully-added pool ids SHALL be deselected; quota-rejected and untried ids SHALL remain selected so the user can retry after upgrading or freeing space.

The user-visible toast SHALL aggregate across all batches as one of:
- All success: `toast.success("已成功添加 X 条到我的物流")`.
- Partial success due to quota: `toast.warning("已添加 X 条，剩余 Y 条因物流规则上限未添加")` where Y = total selected − X.
- Partial success due to network/5xx: `toast.warning("已添加 X 条，剩余 Y 条因网络错误未添加")`.
- Zero added due to immediate quota: `toast.error("已达到您当前方案的物流规则上限（N 条）")` (passes through backend detail string via `getApiErrorMessage`).

The frontend SHALL NOT perform a client-side quota pre-check; it relies on the backend's per-request `_check_logistics_limit` (which already holds `pg_advisory_xact_lock(user_id)` and re-counts active rules), so cross-tab modifications are correctly serialized.

#### Scenario: 408 selected, quota allows all
- **WHEN** user selects 408 pool rows and clicks "全部添加到我的物流", and effective quota covers all 408
- **THEN** frontend sends 3 sequential POSTs of [200, 200, 8] ids, all return HTTP 200
- **AND** toast reads `"已成功添加 408 条到我的物流"`
- **AND** `fetchLogistics()` is called once after the third response
- **AND** the selection is cleared

#### Scenario: 408 selected, quota allows only 250
- **WHEN** user selects 408 pool rows, batch 1 (200 ids) succeeds, batch 2 (200 ids) returns HTTP 403 because `K + 200 > N`
- **THEN** frontend STOPS after batch 2's 403 (no batch 3)
- **AND** toast reads `"已添加 200 条，剩余 208 条因物流规则上限未添加"`
- **AND** `fetchLogistics()` is called once
- **AND** the 200 already-added pool ids are deselected; the remaining 208 stay selected

#### Scenario: Network failure mid-loop
- **WHEN** batch 1 succeeds, batch 2 fails with network error / HTTP 5xx
- **THEN** frontend stops after batch 2; toast reads `"已添加 X 条，剩余 Y 条因网络错误未添加"`; `fetchLogistics()` runs once; failed/untried ids stay selected

#### Scenario: First batch quota rejection
- **WHEN** batch 1 immediately returns HTTP 403 (quota already exceeded before any insert)
- **THEN** no further batches sent; toast reads the backend detail (e.g. `"已达到您当前方案的物流规则上限（10 条）"`); `fetchLogistics()` still runs; selection unchanged
