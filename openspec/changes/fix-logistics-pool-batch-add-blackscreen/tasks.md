## 1. Backend: align BatchAddBody to spec

- [x] 1.1 Edit `api/routes/logistics_pool.py` L103-104: drop `max_length=50` from `Field(...)` (Pydantic-level cap would yield 422 array detail and bypass the handler's spec-mandated 400 string detail; handler-side check at task 1.2 is now the single authoritative gate).
- [x] 1.2 In the same file's batch handler (L242-299), keep explicit length validation at the very top of the function, BEFORE `_check_logistics_limit`: `if not body.ids: raise HTTPException(400, "ids 不能为空")` and `if len(body.ids) > 200: raise HTTPException(400, "单次最多添加 200 条")` (status code corrected from prior 422 to 400 per spec line 16).
- [x] 1.3 Run `python -m flake8 api/routes/logistics_pool.py` — must pass.

## 2. Backend: tests for new boundary behavior

- [x] 2.1 Add `tests/test_api_logistics_pool_batch_boundary.py` covering: empty ids → 400 string detail; 201 ids → 400 string detail "单次最多添加 200 条"; exactly 200 ids → 200; 51 ids regression guard → 200 (not 422).
- [x] 2.2 Run `python -m pytest tests/test_api_logistics_pool_batch_boundary.py -v` — must pass.
- [x] 2.3 Run full backend suite `python -m pytest --tb=short` — must pass with zero new failures. (2478 passed / 3 pre-existing failures in `test_e2e_volume_modes.py`, unrelated to this change.)

## 3. Frontend: shared error normalizer

- [x] 3.1 Create `frontend/src/lib/api-error.js` exporting `getApiErrorMessage(error, fallback)` per spec rules in `frontend-error-resilience` requirement.
- [x] 3.2 Create `frontend/src/__tests__/api-error.test.js` covering all 7 scenarios in the spec (string / 422 array / network / unknown / null / undefined / object detail / empty array).
- [x] 3.3 Run `npm run test -- api-error` (vitest) — must pass.

## 4. Frontend: Toaster topology

- [x] 4.1 Edit `frontend/src/App.jsx`: move `<Toaster richColors position="top-right" />` from L85 (sibling of ErrorBoundary) into INSIDE the existing `<ErrorBoundary>` block at L91-152, as a sibling of `<Suspense>`.
- [x] 4.2 Verify `<SessionKickedDialog />` placement is unaffected (do NOT move it inside ErrorBoundary unless it currently throws — leave it as-is).
- [x] 4.3 Visual smoke test (Playwright): boot app, login, observe toast still appears at top-right and dismisses normally. (Verified during Wave 4 E2E: success toast rendered top-right, page did not unmount, screenshot saved.)

## 5. Frontend: LogisticsPoolPage batch handler rewrite

- [x] 5.1 Edit `frontend/src/pages/LogisticsPoolPage.jsx` import block: add `import { getApiErrorMessage } from '@/lib/api-error'`.
- [x] 5.2 Define `const BATCH_SIZE = 200` as module constant (not inside function) so tests can import.
- [x] 5.3 Rewrite `handleBatchAddToMyLogistics` per the `Frontend multi-batch quota semantics` spec:
  - sequential `for` loop over chunks of 200
  - track `addedTotal`, `untriedIds`, `quotaRejected`, `networkError`
  - on per-batch HTTP 403: STOP loop, set `quotaRejected = true`, accumulate remaining ids into `untriedIds`
  - on per-batch network/5xx: STOP loop, set `networkError = true`, accumulate remaining ids
  - on success: accumulate `response.added` into `addedTotal`
- [x] 5.4 After loop, build aggregate toast:
  - `addedTotal === total && !quotaRejected && !networkError` → `toast.success('已成功添加 N 条到我的物流')`
  - `quotaRejected` and `addedTotal > 0` → `toast.warning('已添加 X 条，剩余 Y 条因物流规则上限未添加')`
  - `quotaRejected` and `addedTotal === 0` → `toast.error(getApiErrorMessage(error, '已达到物流规则上限'))`
  - `networkError` → `toast.warning('已添加 X 条，剩余 Y 条因网络错误未添加')` (or error variant if X==0)
- [x] 5.5 After toast, call `await fetchLogistics()` exactly once unconditionally.
- [x] 5.6 Update selection state: `setSelectedIds(new Set(untriedIds))` so successful ids drop and failed/untried stay.
- [x] 5.7 Replace ALL existing `toast.error(error?.response?.data?.detail || ...)` in this file with `toast.error(getApiErrorMessage(error, fallbackString))`.

## 6. Frontend: tests for batch handler

- [x] 6.1 Create `frontend/src/__tests__/LogisticsPoolPage.batch.test.jsx` (or extend existing) with mocked `logisticsPoolAPI.batchAddToMyLogistics`:
  - all-success across 3 batches → success toast, fetchLogistics called once, selection cleared
  - batch 2 returns 403 → loop stops, warning toast `"已添加 200 条，剩余 208 条因物流规则上限未添加"`, fetchLogistics called once, untried ids retained in selection
  - batch 1 returns 422 array detail (regression guard) → boundary catches OR `getApiErrorMessage` neutralizes; React root NOT unmounted; assertion: `document.body.textContent.length > 0`
  - network error mid-loop → warning toast network variant
- [x] 6.2 Run `npm run test -- LogisticsPoolPage` — all green.

## 7. End-to-end verification (Playwright via MCP)

- [x] 7.1 Restart backend (uses detach script per AGENTS.md) + frontend dev.
- [x] 7.2 Login as admin (creds from `.sisyphus/credentials.local.md`).
- [x] 7.3 Navigate to `/logistics-pool`, select all rows, click "全部添加到我的物流". (Scope reduction: pool currently holds 160 rows < spec's hypothetical 408. Single-batch path covers end-to-end render; multi-batch loop is exhaustively covered by 6/6 vitest mocks in `LogisticsPoolPage.batch.test.jsx` including 3-batch all-success, mid-loop 403 stop, mid-loop network error, and 422 array-detail regression guard. No new data fabricated to inflate to 408 — would be test gaming.)
- [x] 7.4 Observe: POST /api/logistics-pool/batch-add-to-my-logistics → 200 with `{added:160, not_found:[], new_ids:[50132..50291], errors:[]}`; list auto-refreshed; NO black screen; `#root.children.length === 2`; 0 console errors; `poolTotal=160` heading intact.
- [x] 7.5 Save before/after screenshots to `./logistics-pool-before-batch-add.png` and `./logistics-pool-batch-success.png`.

## 8. Lint + type checks

- [x] 8.1 `python -m flake8` — zero errors.
- [x] 8.2 Open changed JS files in editor / run `npm run lint` if configured — zero new warnings.
- [x] 8.3 Pylance / Pyright clean on `api/routes/logistics_pool.py`.

## 9. Final OpenSpec validation

- [x] 9.1 `openspec validate fix-logistics-pool-batch-add-blackscreen --strict` — must pass.
- [x] 9.2 Update `PLAN.md` with this change's status (in-progress → ready-for-archive once apply phase completes).
