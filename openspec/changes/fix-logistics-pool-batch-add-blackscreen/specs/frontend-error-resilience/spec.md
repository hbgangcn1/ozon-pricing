## ADDED Requirements

### Requirement: Toast renders inside ErrorBoundary

The application root layout SHALL render the `<Toaster>` component INSIDE the top-level `<ErrorBoundary>` (not as its sibling), so that any rendering exception thrown by the toast subtree is caught by the boundary and falls back to the boundary's degraded UI rather than unmounting the entire React root.

If the design preference is to keep `<Toaster>` outside the route boundary for layering reasons, the application MUST wrap `<Toaster>` in its own dedicated `<ErrorBoundary>` instance with at minimum a no-op fallback (return `null`) — never leave it unprotected. The boundary's fallback UI MUST NOT itself call `toast()` (avoid re-entrant render loops).

#### Scenario: Toast renders an unrenderable child
- **WHEN** any code path calls `toast.error(value)` where `value` is an Object / Array / non-string non-element
- **THEN** the resulting React render error is caught by the surrounding `<ErrorBoundary>`
- **AND** the React root remains mounted (`document.getElementById('root').children.length > 0`)
- **AND** the boundary's fallback UI is shown OR the toast is silently dropped (depending on which boundary catches), but the page is NEVER fully blank

#### Scenario: Black-screen regression guard
- **WHEN** a Vitest harness calls `toast.error([{type:'x', loc:['body','ids'], msg:'List should have at most 50 items'}])` against a mounted `<App>`
- **THEN** the test asserts `document.body.textContent.length > 0` AND the boundary fallback text or normal app UI is present (not blank)

### Requirement: Shared API error message normalizer

The frontend SHALL provide a pure function `getApiErrorMessage(error, fallback)` exported from `src/lib/api-error.js`. This function SHALL be the single canonical source for converting an axios error (or any object with `response.data.detail`) into a string suitable for `toast.error()` / `toast.warning()` / inline UI.

The function signature: `getApiErrorMessage(error: unknown, fallback: string = '操作失败') => string`.

Rules (in priority order):
1. If `error?.response?.data?.detail` is a non-empty string, return it.
2. If `error?.response?.data?.detail` is an array AND `array.length > 0` AND `array[0]?.msg` is a string, return `array[0].msg`. (This handles FastAPI 422 Pydantic error arrays.)
3. If `error?.message` is a string and starts with "Network Error" or contains `ECONNREFUSED`, return `'网络连接失败'`.
4. Otherwise return `fallback`.

The function SHALL NEVER return `undefined`, `null`, an object, an array, or a Promise. The function SHALL be pure (no side effects, no logging, no toast calls).

All `toast.error(...)` and `toast.warning(...)` call sites in the application SHALL use this helper for any value derived from an HTTP error. Hardcoded literal messages (e.g. `toast.error('保存成功')` for non-error contexts) are NOT subject to this rule.

This change scope mandates migration of `frontend/src/pages/LogisticsPoolPage.jsx` only; full-codebase migration is tracked as a follow-up but the helper MUST be in place and tested as part of this change.

#### Scenario: String detail passes through
- **WHEN** `getApiErrorMessage({response:{data:{detail:'ids 不能为空'}}}, 'fb')` is called
- **THEN** the return value is exactly `'ids 不能为空'`

#### Scenario: FastAPI 422 array detail extracts first msg
- **WHEN** `getApiErrorMessage({response:{data:{detail:[{type:'too_long', loc:['body','ids'], msg:'List should have at most 50 items', input:[], ctx:{max_length:50}}]}}}, 'fb')` is called
- **THEN** the return value is exactly `'List should have at most 50 items'`

#### Scenario: Network error
- **WHEN** `getApiErrorMessage({message:'Network Error'}, 'fb')` is called
- **THEN** the return value is `'网络连接失败'`

#### Scenario: Unknown shape falls back
- **WHEN** `getApiErrorMessage({}, 'fb')` is called
- **THEN** the return value is `'fb'`

#### Scenario: Null/undefined safely fallback
- **WHEN** `getApiErrorMessage(null, 'fb')` or `getApiErrorMessage(undefined, 'fb')` is called
- **THEN** the return value is `'fb'`

#### Scenario: Object detail (defensive) falls back
- **WHEN** `getApiErrorMessage({response:{data:{detail:{some:'object'}}}}, 'fb')` is called
- **THEN** the return value is `'fb'` (NEVER returns the object itself, NEVER returns `'[object Object]'` from coercion)

#### Scenario: Empty array detail falls back
- **WHEN** `getApiErrorMessage({response:{data:{detail:[]}}}, 'fb')` is called
- **THEN** the return value is `'fb'`
