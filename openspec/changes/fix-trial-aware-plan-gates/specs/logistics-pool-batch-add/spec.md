## MODIFIED Requirements

### Requirement: Batch add public pool entries to user logistics

The system SHALL provide `POST /api/logistics-pool/batch-add-to-my-logistics` accepting a JSON body `{"ids": [int, ...]}` and SHALL copy each referenced public pool entry into the authenticated user's logistics table, returning a JSON object `{added: int, not_found: list[int], new_ids: list[int], errors: list[str]}` with HTTP 200.

The endpoint MUST require authentication via the project's standard JWT/cookie dependency. The endpoint MUST enforce the user's subscription logistics quota (`_check_logistics_limit`) BEFORE attempting any insert; if quota would be exceeded the endpoint MUST return the existing quota error (per `_check_logistics_limit` contract) without partial inserts.

`_check_logistics_limit` SHALL resolve the user's effective limit via `services.plan_resolution.get_effective_logistics_limit(session, user)` and SHALL count the user's currently active rules via `services.plan_resolution.count_user_active_rules(session, user_id)`. The function SHALL NOT read `users.subscription_type` directly nor maintain its own hardcoded plan-to-limit mapping. When `get_effective_logistics_limit` returns `-1`, the quota check SHALL pass unconditionally (unlimited). When it returns a positive integer `N`, the request SHALL be rejected if `count_user_active_rules + len(ids) > N`.

Quota rejection SHALL return HTTP 403 with response detail string `"已达到您当前方案的物流规则上限（N 条）"`, where `N` is the resolved limit. The detail SHALL NOT include any internal plan label (e.g. "免费版", "专业版") nor disclose trial status.

The endpoint MUST validate `ids` length: empty list returns HTTP 400 with detail `"ids 不能为空"`; more than 200 ids returns HTTP 400 with detail `"单次最多添加 200 条"`. (NOTE: 400 is the existing behavior preserved for backward compatibility; this is intentionally NOT 422.)

#### Scenario: Successful full batch
- **WHEN** authenticated user POSTs `{"ids": [p1, p2, p3]}` where all three pool ids exist and quota allows three inserts
- **THEN** response is HTTP 200 with `added=3`, `not_found=[]`, `new_ids` containing 3 new logistics ids, `errors=[]`
- **AND** three new rows exist in the logistics table owned by the user

#### Scenario: Partial not_found
- **WHEN** authenticated user POSTs `{"ids": [p1, 999999]}` where `p1` exists and `999999` does not
- **THEN** response is HTTP 200 with `added=1`, `not_found=[999999]`, `new_ids` containing 1 id, `errors=[]`

#### Scenario: Empty ids rejected with 400
- **WHEN** authenticated user POSTs `{"ids": []}`
- **THEN** response is HTTP 400 with `detail="ids 不能为空"`

#### Scenario: Over-limit ids rejected with 400
- **WHEN** authenticated user POSTs `{"ids": [...201 ids...]}`
- **THEN** response is HTTP 400 with `detail="单次最多添加 200 条"`

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
