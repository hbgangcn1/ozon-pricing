## ADDED Requirements

### Requirement: Admin 调整用户订阅到期时间
系统 SHALL 提供端点让 Admin 为任意用户增加或减少订阅有效天数，调整后立即生效。

#### Scenario: 延长订阅时长
- **WHEN** Admin 提交 POST /api/admin/users/{user_id}/subscription/extend，body 含 days=30
- **THEN** 系统将该用户的 subscription_expires 增加 30 天对应的秒数，返回更新后的到期时间戳

#### Scenario: 缩短订阅时长
- **WHEN** Admin 提交 days=-7（负数）
- **THEN** 系统将到期时间减少7天，若结果早于当前时间则订阅立即到期

#### Scenario: 非 Admin 无法调整
- **WHEN** 非 Admin 用户调用该端点
- **THEN** 系统返回 403

### Requirement: Admin 调整用户当日剩余计算次数
系统 SHALL 提供端点让 Admin 为任意用户增加或减少当日剩余计算次数（remaining_calculations），主要用于免费版用户（每日10次上限）。

#### Scenario: 增加当日次数
- **WHEN** Admin 提交 POST /api/admin/users/{user_id}/calculations/adjust，body 含 delta=5
- **THEN** 系统将该用户 remaining_calculations 增加5，返回更新后的值

#### Scenario: 减少当日次数
- **WHEN** Admin 提交 delta=-3
- **THEN** 系统将 remaining_calculations 减少3，最低不低于0

#### Scenario: 对无限制用户（remaining_calculations=-1）调整
- **WHEN** Admin 对 remaining_calculations=-1（无限制）的用户调整次数
- **THEN** 系统按实际值操作（-1+5=4），即取消无限制状态，设为4次；Admin 操作日志记录此次变更

### Requirement: Admin 修改用户类型
系统 SHALL 提供端点让 Admin 修改用户的 user_type 字段，支持：免费版（free）、效率版（efficiency）、专业版（professional）、企业版（enterprise）、测试版（trial）、感谢版（grateful）。

#### Scenario: 修改用户类型
- **WHEN** Admin 提交 POST /api/admin/users/{user_id}/type，body 含 user_type='professional'
- **THEN** 系统更新该用户的 user_type 字段，返回更新后的用户信息

#### Scenario: 非法用户类型
- **WHEN** Admin 提交不在允许列表中的 user_type 值
- **THEN** 系统返回 422 验证错误

#### Scenario: Admin 在用户管理页面看到调整控件
- **WHEN** Admin 访问用户管理页面，点击某用户的"订阅管理"
- **THEN** 页面展示：当前订阅到期时间、调整天数输入框；当前剩余次数、调整次数输入框；用户类型下拉选择框；保存按钮
