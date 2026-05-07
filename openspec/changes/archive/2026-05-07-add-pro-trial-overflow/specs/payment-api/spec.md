## MODIFIED Requirements

### Requirement: 微信回调通知端点
系统 SHALL 提供 `POST /api/payments/notify` 端点（无认证），接收微信支付回调通知，验证签名，解密数据，调用 `db.subscriptions.apply_subscription_change(...)` chokepoint 完成订单状态、用户订阅状态、溢出规则恢复的原子更新，并在 5 秒内返回 HTTP 200。SHALL NOT 直接 `UPDATE users SET subscription_type = ...`,所有订阅字段写入 SHALL 经由该 chokepoint。

#### Scenario: 成功处理支付回调
- **WHEN** 微信服务器发送有效的支付成功回调（event_type=TRANSACTION.SUCCESS），签名验证通过
- **THEN** 系统解密回调数据，调用 `apply_subscription_change(user_id, new_plan, billing_cycle, ...)`,函数在事务内更新 PaymentOrder.status 为 SUCCESS、`users.subscription_type` 与到期时间、若新套餐为 professional/enterprise 则一次性恢复该用户全部 `disabled_by_overflow = 1` 规则并关闭未结窗口；在 5 秒内返回 HTTP 200 `{ code: "SUCCESS", message: "成功" }`

#### Scenario: 签名验证失败
- **WHEN** 微信服务器发送的回调请求签名验证失败
- **THEN** 系统返回 HTTP 400 `{ code: "FAIL", message: "签名验证失败" }`

#### Scenario: 重复回调幂等处理
- **WHEN** 微信服务器对同一订单重复发送回调（PaymentOrder.status 已为 SUCCESS）
- **THEN** 系统跳过业务处理，直接返回 HTTP 200 `{ code: "SUCCESS", message: "成功" }`;`apply_subscription_change` 即便被再次调用也保持幂等,不重复恢复溢出规则

#### Scenario: 回调无需用户认证
- **WHEN** 微信服务器发送回调请求（不携带 JWT token）
- **THEN** 系统不要求 JWT 认证，仅通过微信签名验证请求合法性

#### Scenario: 升级触发溢出规则一次性恢复
- **WHEN** 一个有 6 条 `disabled_by_overflow = 1` 规则的 free 用户成功支付升级到 professional,微信回调到达
- **THEN** `apply_subscription_change` 在同一事务内将 6 条规则的 `disabled_by_overflow = 0`、关闭该用户所有未关闭窗口为 `closed_at = now, close_reason = 'upgraded'`、更新订阅;失败回滚整个事务

## ADDED Requirements

### Requirement: 订阅状态变更单一 chokepoint

所有写入 `users.subscription_type`、`subscription_started_at`、`subscription_expires_at` 等订阅字段的代码路径 SHALL 通过 `db.subscriptions.apply_subscription_change(session, user_id, new_plan, billing_cycle, source) -> ChangeResult` 函数。包括但不限于:微信支付回调、admin 手动调整、CLI 工具、未来任何新订阅来源。函数 SHALL 是幂等的,且 SHALL 在新套餐为 professional / enterprise 时执行溢出恢复操作(`disabled_by_overflow = 0` 与窗口关闭)。

#### Scenario: 支付回调路径走 chokepoint
- **WHEN** `payment_handler.py` 处理支付成功事件
- **THEN** SHALL 调用 `apply_subscription_change(...)`,SHALL NOT 直接执行 `UPDATE users SET subscription_type = ...` SQL

#### Scenario: admin 手动调整路径走 chokepoint
- **WHEN** admin 通过 `api/routes/admin.py` 修改某用户订阅
- **THEN** SHALL 调用 `apply_subscription_change(...)`,SHALL NOT 直接修改 `User.subscription_type` ORM 属性后 commit

#### Scenario: 升级到 enterprise 触发恢复
- **WHEN** chokepoint 接收到 `new_plan = 'enterprise'`,且目标用户存在 `disabled_by_overflow = 1` 规则
- **THEN** 函数在事务内将相关规则全部恢复并关闭未结窗口,返回 `ChangeResult` 包含 `restored_count` 与 `closed_window_count`

#### Scenario: 同套餐重复变更幂等
- **WHEN** chokepoint 被调用时 `users.subscription_type` 已等于 `new_plan` 且生效中
- **THEN** 函数返回成功但不进行重复的恢复或日志写入

#### Scenario: 降级触发自动裁剪
- **WHEN** chokepoint 接收到从 `professional` 降级至 `efficiency` 的变更
- **THEN** 函数在事务内更新订阅字段,并调用 `overflow_service.auto_trim_user_rules(...)` 完成裁剪与开窗,确保降级后立即满足新套餐的 logistics_limit
