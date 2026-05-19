## ADDED Requirements

### Requirement: 试用期间豁免计算次数限制

系统 SHALL 在计算物流定价次数时，对处于有效试用期内的用户豁免 `remaining_calculations` 限制，视同 `professional` 用户处理。`decrement_user_calculations()` SHALL 在判断用户套餐前，先通过 `get_effective_plan(user)` 解析有效套餐；若返回 `"professional"` 且由试用触发，则直接返回 `True`，不扣减 `remaining_calculations`。

#### Scenario: 试用中用户计算定价不受次数限制
- **WHEN** 用户 `subscription_type = 'free'`、`trial_expires_at > now`，已计算 10 次（`remaining_calculations = 0`）
- **THEN** 再次调用 `/api/pricing/calculate` 或 `/api/pricing/calculate-grouped` 时，`decrement_user_calculations` 返回 `True`，计算正常执行，不返回 403

#### Scenario: 试用过期后恢复计算次数限制
- **WHEN** 用户 `subscription_type = 'free'`、`trial_expires_at <= now`，`remaining_calculations = 0`
- **THEN** 调用定价计算接口时，`decrement_user_calculations` 返回 `False`，返回 HTTP 403 "今日计算次数已用完，请明天再来或升级套餐"

#### Scenario: 真实 professional 用户不受影响
- **WHEN** 用户 `subscription_type = 'professional'`（无试用）
- **THEN** `decrement_user_calculations` 直接返回 `True`，不检查 `remaining_calculations`

### Requirement: 试用期间不重置每日计算次数

`reset_user_daily_calculations()` 在登录触发重置时，若用户处于有效试用期内，SHALL 直接返回 `False`（跳过重置），避免将 `remaining_calculations` 修改为有限值，保持数据语义一致。

#### Scenario: 试用中用户登录不重置 remaining_calculations
- **WHEN** 试用中用户登录，`last_calculations_reset_date < today`
- **THEN** `reset_user_daily_calculations` 返回 `False`，`remaining_calculations` 不被修改

#### Scenario: 试用过期后登录正常重置
- **WHEN** 试用已过期用户登录，`last_calculations_reset_date < today`，有效套餐为 `"free"`
- **THEN** `reset_user_daily_calculations` 按 `"free"` 套餐的 `calc_limit`（如 10）重置 `remaining_calculations`
