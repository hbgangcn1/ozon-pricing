## ADDED Requirements

### Requirement: List endpoint accepts limit up to 1000

The system SHALL expose `GET /api/logistics-pool` accepting query parameter `limit` with bounds `ge=1, le=1000` (inclusive). The default value SHALL remain 100. Requests with `limit` outside `[1, 1000]` SHALL be rejected with HTTP 422 by FastAPI's standard query validation.

The endpoint MUST require authentication via the project's standard JWT/cookie dependency (`get_current_user_id`). The endpoint MUST accept the existing optional filter parameters `fulfillment_type`, `destination`, `fbp_service_level`, and `offset` (with `ge=0`) without behavioral change.

#### Scenario: Limit at upper bound returns 200
- **WHEN** authenticated user calls `GET /api/logistics-pool?limit=1000`
- **THEN** response is HTTP 200 with body `{"items": [...], "total": <int>, "limit": 1000, "offset": 0}`

#### Scenario: Limit one above upper bound returns 422
- **WHEN** authenticated user calls `GET /api/logistics-pool?limit=1001`
- **THEN** response is HTTP 422 with FastAPI validation error indicating `limit` must be `<= 1000`

#### Scenario: Limit at lower bound returns 200
- **WHEN** authenticated user calls `GET /api/logistics-pool?limit=1`
- **THEN** response is HTTP 200 with `items` length `<= 1`

#### Scenario: Default limit when omitted is 100
- **WHEN** authenticated user calls `GET /api/logistics-pool` with no `limit` query parameter
- **THEN** response is HTTP 200 with body containing `"limit": 100`

### Requirement: Empty pool returns 200 with empty items array

The system SHALL return HTTP 200 with body `{"items": [], "total": 0, "limit": <requested-or-default>, "offset": <requested-or-default>}` when the public logistics pool contains zero rows matching the query. The endpoint SHALL NOT return HTTP 404 to indicate empty data, regardless of filter combinations.

#### Scenario: Empty pool with default params
- **WHEN** authenticated user calls `GET /api/logistics-pool` and the public pool table is empty
- **THEN** response is HTTP 200 with body `{"items": [], "total": 0, "limit": 100, "offset": 0}`

#### Scenario: Empty pool with limit=1000
- **WHEN** authenticated user calls `GET /api/logistics-pool?limit=1000` and the public pool table is empty
- **THEN** response is HTTP 200 with body `{"items": [], "total": 0, "limit": 1000, "offset": 0}`

#### Scenario: Filter matches zero rows
- **WHEN** authenticated user calls `GET /api/logistics-pool?destination=NONEXISTENT` and no row matches the filter
- **THEN** response is HTTP 200 with `items=[]` and `total=0` (NOT 404)

### Requirement: Frontend page does not show error toast on 200 OK responses

The public logistics pool page (`frontend/src/pages/LogisticsPoolPage.jsx`) SHALL NOT call `toast.error('获取物流池数据失败')` (or any equivalent error toast) on any code path where `logisticsPoolAPI.getAll()` resolves successfully (i.e., the underlying HTTP response is 2xx). This applies to both the initial mount load (via `useEffect`) and all post-action refreshes (after import, delete-all, batch-add, etc.).

The page MAY call `toast.error` only when the underlying request rejects with a non-cancellation error. Cancellation errors (`AbortError`, axios `CanceledError`, or signals where `signal.aborted === true`) SHALL be treated as silent no-ops.

The page SHALL NOT contain status-code-specific suppression of `toast.error` for non-cancellation errors (in particular, the prior `if (error?.response?.status !== 404)` guard SHALL be removed). All non-cancellation errors SHALL surface as `toast.error`.

#### Scenario: Empty pool does not trigger error toast
- **WHEN** the page mounts and `logisticsPoolAPI.getAll({limit:1000})` resolves with `{items: [], total: 0, ...}` (HTTP 200)
- **THEN** `toast.error` is NOT called
- **AND** the page renders the empty state of `VirtualTable`

#### Scenario: Populated pool does not trigger error toast
- **WHEN** the page mounts and `logisticsPoolAPI.getAll({limit:1000})` resolves with `{items: [...408 rows...], total: 408, ...}` (HTTP 200)
- **THEN** `toast.error` is NOT called
- **AND** the page renders 408 rows

#### Scenario: Server error triggers error toast
- **WHEN** the page mounts and `logisticsPoolAPI.getAll(...)` rejects with HTTP 500
- **THEN** `toast.error('获取物流池数据失败')` is called exactly once

#### Scenario: 422 validation error triggers error toast
- **WHEN** `logisticsPoolAPI.getAll(...)` rejects with HTTP 422 (e.g., regression where frontend passes out-of-bound limit)
- **THEN** `toast.error('获取物流池数据失败')` is called exactly once

#### Scenario: Aborted request is silent
- **WHEN** the page unmounts before `logisticsPoolAPI.getAll(...)` resolves and the request is aborted via AbortController
- **THEN** `toast.error` is NOT called
- **AND** no React state update is attempted on the unmounted component (i.e., `setLogistics` / `setIsLoading` are not called after abort)

### Requirement: Frontend page uses single source of truth for pool fetch

The page SHALL define exactly one fetch function for `GET /api/logistics-pool`, named `fetchLogistics`, accepting an optional `AbortSignal` parameter. The initial-mount `useEffect` SHALL invoke this single function with a signal from a freshly created `AbortController`, and SHALL call `controller.abort()` in its cleanup. Post-action refreshes (after import success, delete-all success, batch-add success, etc.) SHALL invoke the same `fetchLogistics` function.

The page SHALL NOT contain a second inline copy of the fetch logic (no parallel `loadLogistics` defined inside `useEffect`).

#### Scenario: Single fetch function exists
- **WHEN** reading `LogisticsPoolPage.jsx`
- **THEN** there is exactly one definition matching `const fetchLogistics = useCallback(async (signal?) => {...})`
- **AND** there is no other inline async function performing `logisticsPoolAPI.getAll(...)` inside `useEffect`

#### Scenario: Initial mount uses AbortController
- **WHEN** the component mounts
- **THEN** the mount `useEffect` creates a `new AbortController()`, invokes `fetchLogistics(controller.signal)`, and registers `() => controller.abort()` as cleanup

#### Scenario: Post-import refresh uses same function
- **WHEN** user successfully imports an XLSX file
- **THEN** the success handler invokes `fetchLogistics()` (the same function referenced by the mount effect)
