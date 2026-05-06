## ADDED Requirements

### Requirement: 支付发起端点
系统 SHALL 提供 `POST /api/payments/create` 端点，接受认证用户请求，在数据库创建 PaymentOrder（status=PENDING），调用 `wechat_pay_v3.create_native_order()` 获取 `code_url`，返回 `{ order_id, code_url }` 给前端。

#### Scenario: 成功创建支付订单
- **WHEN** 认证用户发送 `POST /api/payments/create`，body 包含 `{ plan_code, billing_cycle, amount }`
- **THEN** 系统创建 PaymentOrder 记录（status=PENDING, user_id=当前用户, amount=金额(分), description=套餐描述），调用微信 Native 下单接口，返回 HTTP 200 `{ order_id, code_url }`

#### Scenario: 未认证用户被拒绝
- **WHEN** 未携带有效 JWT token 的请求发送 `POST /api/payments/create`
- **THEN** 系统返回 HTTP 401

#### Scenario: 微信下单失败
- **WHEN** 认证用户发送有效请求但微信 API 返回错误（证书过期、参数无效等）
- **THEN** 系统将 PaymentOrder 状态设为 FAILED，返回 HTTP 502 `{ error, message }`

#### Scenario: 套餐金额校验
- **WHEN** 请求中的 amount 与数据库 plans 表中对应 plan_code 和 billing_cycle 的 actual_price 不一致
- **THEN** 系统返回 HTTP 400 `{ error: "amount_mismatch" }`

### Requirement: 微信回调通知端点
系统 SHALL 提供 `POST /api/payments/notify` 端点（无认证），接收微信支付回调通知，验证签名，解密数据，调用 `PaymentHandler.handle_payment_success()` 更新订单和用户订阅状态，并在 5 秒内返回 HTTP 200。

#### Scenario: 成功处理支付回调
- **WHEN** 微信服务器发送有效的支付成功回调（event_type=TRANSACTION.SUCCESS），签名验证通过
- **THEN** 系统解密回调数据，异步调用 `handle_payment_success()` 更新 PaymentOrder.status 为 SUCCESS 和用户订阅信息，在 5 秒内返回 HTTP 200 `{ code: "SUCCESS", message: "成功" }`

#### Scenario: 签名验证失败
- **WHEN** 微信服务器发送的回调请求签名验证失败
- **THEN** 系统返回 HTTP 400 `{ code: "FAIL", message: "签名验证失败" }`

#### Scenario: 重复回调幂等处理
- **WHEN** 微信服务器对同一订单重复发送回调（PaymentOrder.status 已为 SUCCESS）
- **THEN** 系统跳过业务处理，直接返回 HTTP 200 `{ code: "SUCCESS", message: "成功" }`

#### Scenario: 回调无需用户认证
- **WHEN** 微信服务器发送回调请求（不携带 JWT token）
- **THEN** 系统不要求 JWT 认证，仅通过微信签名验证请求合法性

### Requirement: 订单状态查询端点
系统 SHALL 提供 `GET /api/payments/{order_id}/status` 端点，返回指定订单的当前支付状态。若订单状态仍为 PENDING，SHALL 同时调用微信查询接口同步最新状态。

#### Scenario: 查询待支付订单状态
- **WHEN** 认证用户查询自己的 PENDING 状态订单
- **THEN** 系统调用 `wechat_pay_v3.query_order()` 获取最新状态，若微信返回 SUCCESS 则更新 DB 并返回 `{ status: "SUCCESS", trade_state: "SUCCESS" }`，若未支付则返回 `{ status: "PENDING", trade_state: "NOTPAY" }`

#### Scenario: 查询已完成订单状态
- **WHEN** 认证用户查询自己的 SUCCESS 状态订单
- **THEN** 系统直接从数据库返回 `{ status: "SUCCESS" }`，不调用微信接口

#### Scenario: 查询非本人订单被拒绝
- **WHEN** 认证用户查询其他用户的订单
- **THEN** 系统返回 HTTP 404

### Requirement: 订单列表增强
系统 SHALL 增强现有 `GET /api/orders` 端点，支持按状态筛选（`?status=SUCCESS`）和分页参数（`?page=1&page_size=10`），返回包含总数的响应。

#### Scenario: 按状态筛选订单
- **WHEN** 认证用户发送 `GET /api/orders?status=SUCCESS`
- **THEN** 系统返回该用户所有 status=SUCCESS 的订单列表

#### Scenario: 分页查询订单
- **WHEN** 认证用户发送 `GET /api/orders?page=2&page_size=5`
- **THEN** 系统返回第 2 页的 5 条订单，响应包含 `{ orders: [...], total: N, page: 2, page_size: 5 }`

#### Scenario: 无参数时返回全部订单
- **WHEN** 认证用户发送 `GET /api/orders`（无筛选参数）
- **THEN** 系统返回该用户所有订单，默认按创建时间降序
