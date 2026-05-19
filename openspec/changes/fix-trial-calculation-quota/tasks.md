## 1. Core Fix

- [x] 1.1 修改 `db/subscription_quota.py`：`decrement_user_calculations` 导入并使用 `get_effective_plan(user)` 替代直接读取 `subscription_type` / `user_type`；试用期间（effective_plan == "professional" 由试用触发）返回 `True`
- [x] 1.2 修改 `db/subscription_quota.py`：`reset_user_daily_calculations` 导入并使用 `is_in_trial(user)`，试用期间直接返回 `False`（跳过重置）
- [x] 1.3 运行 `python -m flake8 db/subscription_quota.py`，确保无风格错误

## 2. Testing

- [x] 2.1 新增 `tests/test_subscription_quota_trial.py`：覆盖试用中 user（`trial_expires_at > now`, `subscription_type='free'`）调用 `decrement_user_calculations` 返回 `True`
- [x] 2.2 新增测试：试用过期 user（`trial_expires_at <= now`）调用 `decrement_user_calculations` 正常进入限制逻辑
- [x] 2.3 新增测试：真实 professional user 调用 `decrement_user_calculations` 返回 `True`
- [x] 2.4 新增测试：试用中 user 调用 `reset_user_daily_calculations` 返回 `False`
- [x] 2.5 新增测试：试用过期 user 调用 `reset_user_daily_calculations` 正常重置
- [x] 2.6 运行 `python -m pytest tests/test_subscription_quota_trial.py --tb=short`，确保新增测试通过
- [x] 2.7 运行 `python -m pytest tests/ --tb=short`，确保全量回归零失败

## 3. Verification

- [x] 3.1 启动后端，用免费测试账号领取试用后连续计算 11 次，确认第 11 次不返回 403
- [x] 3.2 等待试用过期（或手动修改 `trial_expires_at` 为过去时间），确认计算次数限制恢复正常
- [x] 3.3 更新 PLAN.md 记录本次修复
