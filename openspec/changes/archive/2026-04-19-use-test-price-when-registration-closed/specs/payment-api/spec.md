## MODIFIED Requirements

### Requirement: 支付发起端点
系统 SHALL 提供 `POST /api/payments/create` 端点，接受认证用户请求，在数据库创建 PaymentOrder（status=PENDING），调用 `wechat_pay_v3.create_native_order()` 获取 `code_url`，返回 `{ order_id, code_url }` 给前端。

#### Scenario: 成功创建支付订单（注册开放）
- **WHEN** 认证用户发送 `POST /api/payments/create`，body 包含 `{ plan_code, billing_cycle, amount }`，且系统"开放注册"设置为"已开启"
- **THEN** 系统使用 `actual_price`（月/年）创建 PaymentOrder 记录（status=PENDING, user_id=当前用户, amount=金额(分), description=套餐描述），调用微信 Native 下单接口，返回 HTTP 200 `{ order_id, code_url }`

#### Scenario: 成功创建支付订单（注册关闭，使用测试价）
- **WHEN** 认证用户发送 `POST /api/payments/create`，body 包含 `{ plan_code, billing_cycle, amount }`，且系统"开放注册"设置为"已关闭"
- **THEN** 系统使用 `test_price`（月/年）创建 PaymentOrder 记录（status=PENDING, user_id=当前用户, amount=金额(分), description=套餐描述），调用微信 Native 下单接口，返回 HTTP 200 `{ order_id, code_url }`

#### Scenario: 未认证用户被拒绝
- **WHEN** 未携带有效 JWT token 的请求发送 `POST /api/payments/create`
- **THEN** 系统返回 HTTP 401

#### Scenario: 微信下单失败
- **WHEN** 认证用户发送有效请求但微信 API 返回错误（证书过期、参数无效等）
- **THEN** 系统将 PaymentOrder 状态设为 FAILED，返回 HTTP 502 `{ error, message }`

#### Scenario: 套餐金额校验（注册开放）
- **WHEN** 请求中的 amount 与数据库 plans 表中对应 plan_code 和 billing_cycle 的 actual_price 不一致，且"开放注册"为"已开启"
- **THEN** 系统返回 HTTP 400 `{ error: "amount_mismatch" }`

#### Scenario: 套餐金额校验（注册关闭）
- **WHEN** 请求中的 amount 与数据库 plans 表中对应 plan_code 和 billing_cycle 的 test_price 不一致，且"开放注册"为"已关闭"
- **THEN** 系统返回 HTTP 400 `{ error: "amount_mismatch" }`
