## MODIFIED Requirements

### Requirement: 试用状态查询接口

系统 SHALL 提供 `GET /api/subscriptions/trial/status` 端点,返回当前用户的试用领取资格、试用是否进行中、剩余秒数等信息,供前端横幅与领取按钮判断。

此外，`GET /api/auth/me`、`POST /api/auth/login`、`POST /api/auth/register` 三处响应中的 `UserResponse`，以及认证依赖 `get_current_user` 与 `get_user_with_subscription` 两处返回的 user dict SHALL 同时携带 trial 四字段：`trial_used`（int，0/1）、`trial_started_at`（int unix epoch 秒，0 表示未领取）、`trial_expires_at`（int unix epoch 秒，0 表示未领取）、`trial_plan_at_start`（string，未领取时为空字符串），以便前端在不调用 `trial/status` 的情况下即可计算 `is_in_trial`。这些字段 SHALL 来自 `users` 表对应字段（NOT NULL，server defaults 0/0/0/''），无任何二次衍生计算；schema 字段为非 Optional + 默认零值，与 ORM 列契约直接对齐。

#### Scenario: 未领取过试用且符合资格
- **WHEN** 真实套餐为 `free` 或 `efficiency` 且 `trial_used = 0` 的用户请求 `GET /api/subscriptions/trial/status`
- **THEN** 系统返回 `{ eligible: true, in_trial: false, trial_used: false, trial_started_at: 0, trial_expires_at: 0, remaining_seconds: 0 }`

#### Scenario: 试用进行中
- **WHEN** 用户 `trial_expires_at > now` 且真实套餐 ∈ {free, efficiency}
- **THEN** 系统返回 `{ eligible: false, in_trial: true, trial_used: true, trial_started_at: <epoch>, trial_expires_at: <epoch>, remaining_seconds: <int> }`

#### Scenario: 试用已结束或不适用
- **WHEN** 用户 `trial_used = 1` 且 `trial_expires_at <= now`,或真实套餐为 `professional` / `enterprise`
- **THEN** 系统返回 `{ eligible: false, in_trial: false, trial_used: <bool>, ... }`

#### Scenario: /api/auth/me 携带 trial 字段
- **WHEN** 任意已登录用户调用 `GET /api/auth/me`
- **THEN** 响应 JSON 包含 `trial_used`, `trial_started_at`, `trial_expires_at`, `trial_plan_at_start` 四字段，值与 `users` 表当前快照一致

#### Scenario: /api/auth/login 响应携带 trial 字段
- **WHEN** 用户成功登录
- **THEN** 响应中 `user` 对象包含 4 trial 字段，值与 `users` 表当前快照一致；前端登录后立即可计算 `isInTrial()`，无需追加 `/me` 请求

#### Scenario: /api/auth/register 响应携带 trial 字段
- **WHEN** 新用户成功注册
- **THEN** 响应中 `user` 对象包含 4 trial 字段，值为零值默认（`trial_used=0`, `trial_started_at=0`, `trial_expires_at=0`, `trial_plan_at_start=""`）

#### Scenario: get_current_user 依赖返回 trial 字段
- **WHEN** 任何后端路由通过 `Depends(get_current_user)` 获取当前用户 dict
- **THEN** 该 dict 包含 `trial_used`, `trial_started_at`, `trial_expires_at`, `trial_plan_at_start` 四字段

#### Scenario: get_user_with_subscription 依赖返回 trial 字段
- **WHEN** 任何后端路由通过 `Depends(get_user_with_subscription)` 获取当前用户 dict（如 commission_categories GET 端点）
- **THEN** 该 dict 包含 `trial_used`, `trial_started_at`, `trial_expires_at`, `trial_plan_at_start` 四字段

#### Scenario: 未领取试用用户的 trial 字段返回零值
- **WHEN** `trial_used = 0` 的用户调用 `GET /api/auth/me`
- **THEN** 响应中 `trial_used = 0`、`trial_started_at = 0`、`trial_expires_at = 0`、`trial_plan_at_start = ""`

#### Scenario: 真实专业版用户的 trial 字段如实返回
- **WHEN** `subscription_type = 'professional'`、历史上曾领取过试用的用户调用 `GET /api/auth/me`
- **THEN** 响应中 trial 字段如实返回历史值，不被 `subscription_type` 覆盖
