## ADDED Requirements

### Requirement: 试用领取一次性约束

系统 SHALL 允许每个用户终身仅领取一次 7 天专业版试用。试用领取 SHALL 仅对真实 `subscription_type ∈ {free, efficiency}` 且 `trial_used = 0` 的用户开放。领取动作 SHALL 在事务内通过条件 UPDATE 实现,确保并发请求中只有一个成功。

#### Scenario: 免费用户首次领取试用成功
- **WHEN** 真实套餐为 `free`、`trial_used = 0` 的用户调用试用领取接口
- **THEN** 系统在事务内将 `trial_used = 1`、`trial_started_at = now`、`trial_expires_at = now + 7 * 86400`、`trial_plan_at_start = 'free'`,返回 HTTP 200 与新的试用状态

#### Scenario: 已领取过试用的用户再次领取被拒绝
- **WHEN** `trial_used = 1` 的用户调用试用领取接口
- **THEN** 系统返回 HTTP 409 `{ error: "trial_already_used" }`,不修改任何字段

#### Scenario: 专业版用户领取试用被拒绝
- **WHEN** 真实套餐为 `professional` 或 `enterprise` 的用户调用试用领取接口
- **THEN** 系统返回 HTTP 400 `{ error: "trial_not_applicable" }`

#### Scenario: 并发重复领取仅成功一次
- **WHEN** 同一 `trial_used = 0` 用户在短时间内并发发起多次领取请求
- **THEN** 系统通过条件 UPDATE `WHERE trial_used = 0` 保证只有一次 UPDATE 影响行数 = 1 并返回成功,其余请求返回 HTTP 409

### Requirement: 有效套餐(effective plan)解析

系统 SHALL 提供 `get_effective_plan(user) -> str` 与 `get_effective_logistics_limit(user) -> int` 两个 helper。试用未过期且真实套餐 ∈ {free, efficiency} 时,有效套餐 SHALL 返回 `professional`;其他情况 SHALL 返回真实 `subscription_type`。所有特性闸门、规则数量限额计算、前端状态查询 SHALL 一致地使用这组 helper。

#### Scenario: 试用期内免费用户有效套餐为专业版
- **WHEN** 用户 `subscription_type = 'free'` 且 `trial_expires_at > now`
- **THEN** `get_effective_plan(user)` 返回 `'professional'`,`get_effective_logistics_limit(user)` 返回 `-1`(无限),`subscription_type` 字段值不变

#### Scenario: 试用过期后免费用户有效套餐回到免费
- **WHEN** 用户 `subscription_type = 'free'` 且 `trial_expires_at <= now`
- **THEN** `get_effective_plan(user)` 返回 `'free'`,`get_effective_logistics_limit(user)` 返回 `1`

#### Scenario: 真实专业版用户不受试用字段影响
- **WHEN** 用户 `subscription_type = 'professional'`(无论 `trial_used` / `trial_expires_at` 取值)
- **THEN** `get_effective_plan(user)` 返回 `'professional'`,`get_effective_logistics_limit(user)` 返回 `-1`

### Requirement: 试用不修改 subscription_type

试用领取、试用过期、试用期内升级 SHALL 永不修改 `users.subscription_type` 字段。`subscription_type` 仅由真实订阅(支付成功 / admin 调整 / 自然过期)变更,且必须经由 `db/subscriptions.apply_subscription_change(...)` chokepoint。

#### Scenario: 领取试用后真实套餐字段不变
- **WHEN** 免费用户成功领取试用
- **THEN** 数据库 `users.subscription_type` 保持 `'free'` 不变

#### Scenario: 试用自然过期后真实套餐字段不变
- **WHEN** `trial_check` 脚本处理一个 `trial_expires_at < now` 的免费用户
- **THEN** 数据库 `users.subscription_type` 保持 `'free'` 不变,有效套餐自动回到 `'free'`

### Requirement: 试用状态查询接口

系统 SHALL 提供 `GET /api/subscriptions/trial/status` 端点,返回当前用户的试用领取资格、试用是否进行中、剩余秒数等信息,供前端横幅与领取按钮判断。

#### Scenario: 未领取过试用且符合资格
- **WHEN** 真实套餐为 `free` 或 `efficiency` 且 `trial_used = 0` 的用户请求 `GET /api/subscriptions/trial/status`
- **THEN** 系统返回 `{ eligible: true, in_trial: false, trial_used: false, trial_started_at: 0, trial_expires_at: 0, remaining_seconds: 0 }`

#### Scenario: 试用进行中
- **WHEN** 用户 `trial_expires_at > now` 且真实套餐 ∈ {free, efficiency}
- **THEN** 系统返回 `{ eligible: false, in_trial: true, trial_used: true, trial_started_at: <epoch>, trial_expires_at: <epoch>, remaining_seconds: <int> }`

#### Scenario: 试用已结束或不适用
- **WHEN** 用户 `trial_used = 1` 且 `trial_expires_at <= now`,或真实套餐为 `professional` / `enterprise`
- **THEN** 系统返回 `{ eligible: false, in_trial: false, trial_used: <bool>, ... }`

### Requirement: 前端试用横幅与提示

前端 SHALL 在已登录布局中根据 `GET /api/subscriptions/trial/status` 显示如下控件,且整个体验完全基于轮询 / 路由切换刷新,SHALL NOT 依赖任何服务端推送通道:

- 试用进行中:全局横幅显示剩余天/小时数,可关闭(关闭后 24h 不重显)。
- 试用即将过期(< 24h):横幅升级为高亮提示。
- 试用刚过期(用户首次访问且本端未提示过):弹窗告知试用已结束、超额规则已被自动裁剪、48h 内可重新选择保留规则。
- 符合领取资格:订阅管理页与首屏出现"开始 7 天专业版试用"按钮。

#### Scenario: 试用进行中显示横幅
- **WHEN** 已登录用户的状态接口返回 `in_trial: true, remaining_seconds > 86400`
- **THEN** 应用根布局渲染包含剩余天数与"剩余 N 天"文案的横幅,并提供关闭按钮

#### Scenario: 试用刚过期弹窗一次
- **WHEN** 用户登录后状态接口返回 `in_trial: false, trial_used: true, trial_expires_at` 在过去 48h 内,且该客户端尚未弹过本次过期提示
- **THEN** 前端弹出"试用已结束 + 自动裁剪说明 + 进入重新选择"模态,并在本地存储记录已弹

#### Scenario: 不符合资格不显示领取按钮
- **WHEN** 状态接口返回 `eligible: false`
- **THEN** 订阅管理页与首屏 SHALL NOT 显示"开始 7 天专业版试用"按钮
