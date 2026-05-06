## 1. Database Migration

- [ ] 1.1 Create Alembic migration to add `last_calculations_reset_date` column to `users` table
- [ ] 1.2 Verify migration runs correctly in test environment

## 2. Backend: New Reset Function

- [ ] 2.1 Add `last_calculations_reset_date` field to `User` model in `models/user.py`
- [ ] 2.2 Implement `reset_user_daily_calculations()` in `db/subscriptions.py`
- [ ] 2.3 Export `reset_user_daily_calculations` in `db/__init__.py`
- [ ] 2.4 Write unit tests for `reset_user_daily_calculations()` covering all 4 scenarios

## 3. Backend: Login Integration

- [ ] 3.1 Call `reset_user_daily_calculations()` in `api/routes/auth.py` login endpoint after successful authentication
- [ ] 3.2 Ensure `remaining_calculations` is included in login response
- [ ] 3.3 Write integration test for login with daily reset

## 4. Frontend: Display Fix

- [ ] 4.1 Change `"{plan.calcLimit}次/月"` to `"{plan.calcLimit}次/天"` in `PlanManagementPage.jsx`
- [ ] 4.2 Change `"{limit}次/月"` to `"{limit}次/天"` in `SubscriptionPage.jsx`

## 5. Verification

- [ ] 5.1 Run full test suite to verify no regressions
- [ ] 5.2 Deploy to production and verify migration runs
- [ ] 5.3 Manually test login flow with limited plan user