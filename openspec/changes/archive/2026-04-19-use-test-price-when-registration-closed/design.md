## Context

当前支付创建端点 `POST /api/payments/create` 调用 `get_plan_price()` 时始终使用 `use_test_price=False`（默认值），导致即使套餐设置了测试价，支付时也只会使用实际价格。

系统已有"开放注册"设置存储在 `system_config` 表中，可通过 `is_registration_open()` 函数查询。

## Goals / Non-Goals

**Goals:**
- 在"开放注册"为"已关闭"时，支付使用测试价
- 在"开放注册"为"已开启"时，支付使用实际价
- 不改变前端逻辑，后端自动处理价格选择

**Non-Goals:**
- 不修改套餐管理界面的价格显示
- 不添加新的测试价管理功能
- 不涉及退款、优惠等价格逻辑

## Decisions

### Decision 1: 使用 `is_registration_open()` 判断

**选择**：直接调用 `is_registration_open()` 获取注册开放状态

**理由**：
- 函数已存在且被其他模块使用
- 逻辑清晰：注册关闭 = 内部测试模式 = 使用测试价

**替代方案**：
- 添加新的环境变量或配置项 → 增加维护复杂度
- 前端传递 `use_test_price` 标志 → 增加前端复杂度，且不安全

### Decision 2: 传递 `use_test_price=not is_open`

**选择**：将 `not is_registration_open()` 的结果传递给 `get_plan_price()`

**理由**：
- 最小改动：仅修改一处
- 利用现有 `get_plan_price()` 的 `use_test_price` 参数
- 注册关闭时测试价为 0 也不会导致支付异常（金额为 0 时可正常创建订单）

## Risks / Trade-offs

[Risk] 测试价设置为 0 可能导致免费支付 → ** Mitigation**: 测试时应将测试价设为合理值（如 0.01），或在前端限制测试价必须大于 0

[Risk] 注册状态切换时，正在进行的支付订单价格与最终价格不一致 → ** Mitigation**: 订单创建时已锁定金额，状态切换不影响已创建的订单

## Open Questions

无
