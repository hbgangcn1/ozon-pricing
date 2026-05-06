## Why

目前套餐管理中的"测试价"字段（`test_price_month`, `test_price_year`）从未被实际使用。`get_plan_price()` 函数虽然有 `use_test_price` 参数，但调用时从未传递。

为支持运营人员在"开放注册"设置为"已关闭"时能够使用测试价格进行支付测试，需要修改支付创建逻辑：根据开放注册设置动态选择使用实际价格或测试价格。

## What Changes

- **修改支付创建逻辑**：在 `POST /api/payments/create` 端点中，根据系统"开放注册"设置动态决定使用实际价格或测试价格
  - 当"开放注册"为"已开启"时，使用 `actual_price`（正常收费）
  - 当"开放注册"为"已关闭"时，使用 `test_price`（测试价格）
- **无新增端点**：仅修改现有支付创建端点的价格查询逻辑
- **无数据库变更**：使用现有的 `test_price` 字段

## Capabilities

### Modified Capabilities

- `payment-api`: 修改"支付发起端点"需求中的金额校验逻辑，当注册开放状态为"已关闭"时，使用测试价格进行校验和创建订单

## Impact

- **受影响代码**：`api/routes/payment.py` 中的 `create_payment()` 函数
- **依赖函数**：`db/plans.get_plan_price()`、`db/config.is_registration_open()`
- **前端影响**：无 - 前端传递的 `amount` 金额仍由后端重新校验和覆盖
