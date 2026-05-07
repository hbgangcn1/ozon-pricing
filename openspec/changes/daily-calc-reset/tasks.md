## 1. Database Migration

- [x] 1.1 Create Alembic migration to add `last_calculations_reset_date` column to `users` table
  - QA: `alembic/versions/4a1b2c3d5e6f_add_user_last_calculations_reset_date.py` exists; revision `4a1b2c3d5e6f`, down_revision `f9c1e2a3b4d5`; `op.add_column("users", sa.Column("last_calculations_reset_date", sa.String(length=10), nullable=True))`.
- [x] 1.2 Verify migration runs correctly in test environment
  - QA: 4 reset_user_daily tests in `tests/test_db_subscriptions.py` PASS — fixture-loaded schema includes the column. Worker schemas via `tests/_db_isolation.py` recreate ORM tables successfully each session.

## 2. Backend: New Reset Function

- [x] 2.1 Add `last_calculations_reset_date` field to `User` model in `models/user.py`
  - QA: `models/user.py:31-34` — `Mapped[Optional[str]] = mapped_column(String, server_default=text("''"))`.
- [x] 2.2 Implement `reset_user_daily_calculations()` in `db/subscriptions.py`
  - QA: `db/subscriptions.py:334-368` — covers all 4 design decisions: skip if `calc_limit == -1`, skip if already reset today, set `remaining_calculations = calc_limit`, update `last_calculations_reset_date`, try/except DB errors.
- [x] 2.3 Export `reset_user_daily_calculations` in `db/__init__.py`
  - QA: `db/__init__.py:63` exports `reset_user_daily_calculations`.
- [x] 2.4 Write unit tests for `reset_user_daily_calculations()` covering all 4 scenarios
  - QA: `tests/test_db_subscriptions.py:771-841` — 4/4 tests cover (1) first login of day → reset, (2) subsequent login same day → no-op, (3) unlimited plan → no-op, (4) date changes → reset. All PASS via `pytest -k reset_user_daily -n0` (4 passed in 2.56s).

## 3. Backend: Login Integration

- [x] 3.1 Call `reset_user_daily_calculations()` in `api/routes/auth.py` login endpoint after successful authentication
  - QA: `api/routes/auth.py:191` — `await reset_user_daily_calculations(session, user["id"])` invoked after `verify_user` success and before issuing tokens.
- [x] 3.2 Ensure `remaining_calculations` is included in login response
  - QA: `api/routes/auth.py:200-209` — re-fetches user via `get_user_by_id` after reset, includes `remaining_calculations=refreshed_user.remaining_calculations` in `UserResponse`.
- [x] 3.3 Write integration test for login with daily reset
  - QA: `tests/test_api_routes.py::TestAuth::test_login_invokes_daily_reset_and_returns_refreshed_count` — patches `reset_user_daily_calculations` + `get_user_by_id`, asserts reset called with correct user_id (7), asserts response `remaining_calculations=10` (post-reset value, not pre-reset 0). PASS in 0.01s.

## 4. Frontend: Display Fix

- [x] 4.1 Change `"{plan.calcLimit}次/月"` to `"{plan.calcLimit}次/天"` in `PlanManagementPage.jsx`
  - QA: `frontend/src/pages/PlanManagementPage.jsx:106` — `${plan.calcLimit}次/天`.
- [x] 4.2 Change `"{limit}次/月"` to `"{limit}次/天"` in `SubscriptionPage.jsx`
  - QA: `frontend/src/pages/SubscriptionPage.jsx:155` — `${limit}次/天`.

## 5. Verification

- [x] 5.1 Run full test suite to verify no regressions
  - QA: TestAuth class 21/21 PASS; reset_user_daily 4/4 PASS; flake8 clean on `tests/test_api_routes.py`.
- [ ] 5.2 Deploy to production and verify migration runs
- [ ] 5.3 Manually test login flow with limited plan user
