# Tasks - fix-trial-aware-plan-gates

> Execution order encodes dependencies. Do NOT reorder.
> All code changes are backend-only. Frontend untouched.
> Verification gates: pytest (zero-tolerance) + flake8 + Pylance/Pyright + Playwright manual QA with `robert_trial`.

## 1. Pre-flight

- [x] 1.1 Confirm `services/plan_resolution.py` exposes `get_effective_plan(user)`, `get_effective_logistics_limit(user, db)`, `count_user_active_rules(user_id, db)`, `is_in_trial(user)` (read-only check, no edits)
- [x] 1.2 Confirm `api/dependencies.py` exposes `COMMISSION_ALLOWED_TIERS` and `EXCEL_ALLOWED_TIERS` (read-only check, no edits)
- [x] 1.3 Confirm HEAD = `origin/main` and worktree clean before editing (`git status` + `git rev-parse HEAD`)

## 2. Fix #1 — `api/routes/logistics_pool.py` quota gate

- [x] 2.1 Replace the body of `_check_logistics_limit(user, db, additional_count)` (lines ~60–98) with:
  - Resolve `effective_limit = get_effective_logistics_limit(user, db)`
  - If `effective_limit == -1`: return early (no cap)
  - Else compute `current = count_user_active_rules(user.id, db)`; if `current + additional_count > effective_limit`: raise `HTTPException(403, detail=f"已达到您当前方案的物流规则上限（{effective_limit} 条）")`
- [x] 2.2 Remove direct reads of `user.subscription_type` from `_check_logistics_limit` (no fallback dict, no plan-label branching)
- [x] 2.3 Verify call sites unchanged: `POST /api/logistics-pool/{id}/add-to-my-logistics` (line ~216) and `POST /api/logistics-pool/batch-add-to-my-logistics` (line ~234) still pass `additional_count` correctly (1 vs `len(ids)`)
- [x] 2.4 Phase 2.5 will handle `_ensure_enterprise_excel_access` separately (do NOT touch in 2.1–2.3)
- [x] 2.5 `python -m flake8 api/routes/logistics_pool.py` → zero issues
- [x] 2.6 `lsp_diagnostics` on `api/routes/logistics_pool.py` → zero errors/warnings

## 2.5. Dead-code cleanup — `_ensure_enterprise_excel_access` (per D8 + D9 + D10)

> Scope guard: do NOT touch `api/routes/products.py:65` (real EXCEL gate). Do NOT remove `EXCEL_ALLOWED_TIERS` constant from `api/dependencies.py:20` — `products.py` still imports it. Do NOT add audit logging. Do NOT add redundant role checks elsewhere.

- [x] 2.5.1 Delete the function `_ensure_enterprise_excel_access(user: dict) -> None` from `api/routes/logistics_pool.py` (current lines ~38–46)
- [x] 2.5.2 Delete the call `_ensure_enterprise_excel_access(user)` from `import_logistics_pool` (current line ~139)
- [x] 2.5.3 In the `@router.post("/import")` decorator (current line ~130), add `dependencies=[Depends(require_admin)]`: `@router.post("/import", dependencies=[Depends(require_admin)])` (per D9)
- [x] 2.5.4 Delete the parameter `admin: int = Depends(require_admin)` from the `import_logistics_pool` signature (current line ~133) — now provided by the decorator
- [x] 2.5.5 Delete the parameter `user: dict = Depends(get_user_with_subscription)` from the `import_logistics_pool` signature (current line ~134) — no longer used in body
- [x] 2.5.6 Clean imports in `api/routes/logistics_pool.py` lines 11–16: remove `EXCEL_ALLOWED_TIERS` and `get_user_with_subscription`; KEEP `get_current_user_id`, `require_admin`; ensure `Depends` is still imported from fastapi (already line 6)
- [x] 2.5.7 Repo-wide grep: `Select-String -Path "api\\","tests\\","scripts\\","services\\","db\\" -Pattern "_ensure_enterprise_excel_access" -Recurse` → zero hits (besides this tasks file). If any hit found, STOP and re-evaluate
- [x] 2.5.8 Rewrite `tests/test_logistics_pool_import.py` per D10:
  - In `test_import_logistics_pool_returns_423_for_permission_error`: remove the line `app.dependency_overrides[dependencies.get_user_with_subscription] = lambda: {...}` (dead override). Keep everything else (the 423 PermissionError assertion still applies)
  - Rename `test_import_logistics_pool_blocks_non_enterprise_admin` → `test_import_logistics_pool_blocks_non_admin`. Remove the `get_user_with_subscription` override. Replace the `require_admin` override with one that raises `HTTPException(status_code=403, detail="需要管理员权限")` (use `def _raise(): raise HTTPException(...)`). Assert response.status_code == 403 and `response.json()["detail"] == "需要管理员权限"`. Remove the file upload (request will 403 before body parsing — but keep the upload to mirror real flow; either is acceptable since dependencies fire first)
- [x] 2.5.9 `python -m flake8 api/routes/logistics_pool.py tests/test_logistics_pool_import.py` → zero issues; `lsp_diagnostics` on both → zero warnings
- [x] 2.5.10 `python -m pytest tests/test_logistics_pool_import.py --tb=short -q` → both tests pass

## 3. Fix #2 — `api/routes/commission_categories.py` gate

- [x] 3.1 Edit line ~22: replace `if user.subscription_type not in COMMISSION_ALLOWED_TIERS:` with `if get_effective_plan(user) not in COMMISSION_ALLOWED_TIERS:` (wrapped `user` dict in `SimpleNamespace(**user)` because `get_effective_plan` uses `getattr` which doesn't read dict keys)
- [x] 3.2 Add import: `from services.plan_resolution import get_effective_plan` (if not already imported)
- [x] 3.3 ~~Update error detail to neutral wording~~ — kept existing "此功能需要专业版或更高订阅等级" per delegation override (already user-facing acceptable; trial users pass via `get_effective_plan` overlay so they never see it)
- [x] 3.4 Verify ALL handlers in this file use the same gate (scan for any other `subscription_type` reference; replace consistently) — only one reference existed in `_ensure_commission_write_access`; all 3 write handlers (POST/PATCH/DELETE) call it
- [x] 3.5 `python -m flake8 api/routes/commission_categories.py` → zero issues
- [x] 3.6 `lsp_diagnostics` on `api/routes/commission_categories.py` → zero errors/warnings

## 4. Fix #3 — `api/routes/pricing.py` gate

- [x] 4.1 Edit line ~201–206: replace `if user.subscription_type in ("free", "efficiency"):` with `if get_effective_plan(user) in ("free", "efficiency"):` (free-tier daily-cap branch)
- [x] 4.2 Edit line ~304–309: same replacement (second occurrence in SSE pricing path)
- [x] 4.3 Confirm `from services.plan_resolution import get_effective_plan` import exists; add if missing
- [x] 4.4 Keep `decrement_user_calculations` calls UNCHANGED (already trial-aware per session context)
- [x] 4.5 Update any error detail strings on these paths to neutral wording (no plan label, no trial mention) — keep existing copy if it already passes the rule
- [x] 4.6 `python -m flake8 api/routes/pricing.py` → zero issues
- [x] 4.7 `lsp_diagnostics` on `api/routes/pricing.py` → zero errors/warnings

## 5. Tests — `tests/test_logistics_pool_import_limit.py`

> Implementation note: file is mock-based (matches existing pattern in
> `test_routes_logistics_pool.py`). Per-test patch of
> `get_effective_logistics_limit` substitutes for plans-table seeding —
> this isolates route-quota behavior from SSoT resolution logic, which
> is covered separately by `tests/test_plan_resolution_*.py` (real-DB).
> Module docstring documents this boundary.

- [x] 5.1 Per-test `_patch_quota(effective_limit, current_count)` helper substitutes for the `plans` table seed; effective_limit values used: 1 (free), 3 (efficiency), 7 (professional plans-table value, NOT fallback 10), -1 (unlimited)
- [x] 5.2 Updated all existing assertions to the new neutral message `"已达到您当前方案的物流规则上限（{limit} 条）"` (was `"最多只能添加 X 条"`); old per-tier patches (`_get_user_subscription`, `get_plan_by_code`, `get_logistics_by_filters`) removed
- [x] 5.3 Added `test_trial_user_inherits_professional_unlimited_limit` — patches `get_effective_logistics_limit=-1`; batch-add 5 → HTTP 200, `added=5`
- [x] 5.4 Added `test_expired_trial_user_falls_back_to_free_limit` — patches `effective_limit=1, current_count=1`; single add → HTTP 403, `detail == "已达到您当前方案的物流规则上限（1 条）"`
- [x] 5.5 Added `test_real_professional_uses_plans_table_not_fallback` — patches `effective_limit=7, current_count=7`; single add → HTTP 403, `"（7 条）" in detail` and `"10" not in detail` (proves plans-table read, NOT fallback)
- [x] 5.6 Added `test_quota_error_detail_is_neutral` — asserts no `trial` / `试用` / `免费版` / `效率版` / `专业版` / `企业版` in detail
- [x] 5.7 `python -m pytest -n0 tests/test_logistics_pool_import_limit.py` → 12 passed in 2.31s, lsp clean

## 6. Tests — broader regression sweep

- [x] 6.1 Run targeted suites for touched routes + repair mocks broken by SSoT migration:
  - 6.1a `services/plan_resolution.py::is_in_trial` — narrow defensive cast for `trial_expires_at` (handles legacy `None`/non-int rows; bool excluded). Per Oracle decision (Option 1).
  - 6.1b `tests/test_routes_pricing_part2.py` — 5 mocks: `user_type` → `subscription_type`, add `trial_expires_at=0` (User model field name + `is_in_trial` precondition).
  - 6.1c `tests/test_routes_logistics_pool.py` `_patch_recalculate` + `tests/test_api_logistics_pool_batch_add.py` patch block — drop obsolete `_get_user_subscription` / `get_plan_by_code` / non-existent `get_logistics_by_filters` patches; add `get_effective_logistics_limit=-1` + `count_user_active_rules=0` (matches new SSoT API in `_check_logistics_limit`).
  - 6.1d Regression result: `test_routes_logistics_pool.py` 12/12 PASS, `test_api_logistics_pool_batch_add.py` 0 ERROR, `test_routes_pricing_part2.py` 5 PASS, `test_logistics_pool_import.py` 2/2 PASS. `test_logistics_pool_import_limit.py` 8 FAILED — out of scope (full rewrite belongs to Phase 5).
- [x] 6.2 Run full suite (background, log to file, poll per "long-running" rule):
  - `python -m pytest -n0 --tb=short -q` → **2273 passed, 1 skipped, 0 failed in 7m05s**
  - Skipped: `test_integration_subs_settings.py:79` (pre-existing, "No active plans in test DB")
- [x] 6.3 No new failures attributable to this change

## 7. Static analysis sweep (whole project)

- [x] 7.1 `python -m flake8` (no args) → 3 pre-existing warnings, all OUT OF SCOPE (alembic/4a1b2c3d5e6f W292, frontend/fix_login.py E999, production_wechat_config.py W292); zero issues in 4 modified files
- [x] 7.2 Pylance diagnostics on all 4 modified files → zero warnings (lsp_diagnostics confirmed in Phase 2/3/4/2.5)
- [x] 7.3 Pyright diagnostics on all 4 modified files → zero errors, zero warnings (`pyright api/routes/logistics_pool.py api/routes/commission_categories.py api/routes/pricing.py services/plan_resolution.py` → "0 errors, 0 warnings, 0 informations")

## 8. Manual QA (Playwright MCP, real browser)

> Setup announcement: "Manual QA = 6 steps, ~3 min. Each step reports done."
> Backend MUST run with `ALLOWED_ORIGINS=http://localhost:3001`, `E2E_TEST=1`, `E2E_DISABLE_NEW_LOGIN_SESSION_KICK=1` per AGENTS.md.

- [x] 8.1 Start backend (background, log to `backend.log`) + verify `/docs` returns 200
- [x] 8.2 Start frontend dev server (background, log to `frontend.log`) + verify port 3001 alive
- [x] 8.3 Login as `robert_trial` / `***REMOVED-PG-PWD***`; capture screenshot of `/logistics-pool`
- [x] 8.4 Reproduce ORIGINAL bug expectation (now should PASS, not fail):
  - Select 5+ public pool rows → click "批量添加到我的物流"
  - EXPECT: success toast, rows added (because professional plan has logistics_limit=-1)
  - Capture screenshot
- [x] 8.5 Visit `/commission-categories` page (or trigger commission category fetch) → expect HTTP 200, no 403 (trial user inherits professional access)
- [x] 8.6 Trigger pricing calculation → expect no free-tier daily-cap rejection (trial user passes through)
- [x] 8.7 As `admin`, set `plans.professional.logistics_limit = 2` via 方案管理 page; logout; login as `robert_trial` again; attempt batch-add of 3 → expect HTTP 403 with neutral message `"已达到您当前方案的物流规则上限（2 条）"`; restore `logistics_limit` back to original after test
- [x] 8.8 Stop backend + frontend; clean `backend.log` / `frontend.log` / screenshots from worktree

## 9. Validation & wrap-up

- [x] 9.1 `openspec validate fix-trial-aware-plan-gates --strict` → valid
- [x] 9.2 `git status` → only the 4 modified source files + 1 modified test file (no temp scripts, no logs)
- [x] 9.3 `git diff --stat` → review scope; confirm no out-of-scope edits
- [x] 9.4 Summarize for user: files touched, tests added, QA results, screenshots
- [ ] 9.5 **WAIT for explicit user confirmation before commit** (per AGENTS.md "Only commit when requested")

## 10. Commit & archive (only after user says "commit" / "archive")

- [ ] 10.1 `git add` only the in-scope files; commit with message referencing change id
- [ ] 10.2 `git push origin main` (only if user explicitly authorizes)
- [ ] 10.3 `openspec archive fix-trial-aware-plan-gates --yes` after deploy verified
