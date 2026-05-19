## Why

免费版用户领取 7 天专业版试用后，`subscription_type` 仍为 `"free"`，但功能门控（精准模式、物流模板上限）已通过 `get_effective_plan()` 正确识别试用状态。然而**计算次数限制**由 `decrement_user_calculations()` 独立判断，该函数仅读取 `subscription_type` / `user_type`，完全不检查 `trial_expires_at`，导致试用期间用户仍被按 `"free"` 处理，10 次计算后触发 `"今日计算次数已用完"`。试用即专业版体验，不应在计算次数上做限制。

## What Changes

- 修改 `db/subscription_quota.py` 的 `decrement_user_calculations()`，引入试用状态判断；试用期间（`is_in_trial()` 为 `True`）豁免计算次数限制，视同 `professional` 用户。
- 同步检查 `reset_user_daily_calculations()`：试用中的用户不应被重置为有限次数。
- 为上述两处逻辑新增/补充单元测试，覆盖试用中、试用过期、非试用三种场景。
- 无 API 变更，无前端变更，无数据库 schema 变更。

## Capabilities

### New Capabilities
- *(无新增能力)*

### Modified Capabilities
- `trial-calculation-quota`: 试用期间的计算次数限制行为从"按原套餐限制"改为"试用期间不受限制"。

## Impact

- **后端**：`db/subscription_quota.py`（核心修复）
- **测试**：`tests/test_plan_resolution.py` 或新增 `tests/test_subscription_quota.py`
- **无影响**：前端页面、API 接口签名、数据库 schema、部署流程
