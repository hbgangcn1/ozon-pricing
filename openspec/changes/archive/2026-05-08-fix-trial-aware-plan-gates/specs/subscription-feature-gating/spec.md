## MODIFIED Requirements

### Requirement: 特性闸门基于 effective plan

所有依赖订阅级别决策的特性闸门 SHALL 基于 `services.plan_resolution.get_effective_plan(user)` 而非直接读 `users.subscription_type`。包括但不限于:物流规则数量限制（含公共物流池单条/批量添加端点 `_check_logistics_limit` 与 `_get_user_subscription`）、佣金品类访问权限（`commission_categories` 路由）、定价计算精准模式入口门禁（`pricing` 路由两处入口）、规则启用动作。试用期内 free/efficiency 用户 SHALL 享有与真实 professional 用户相同的能力闸门待遇。

任何特性闸门 SHALL NOT 在错误响应 detail 中暴露内部 plan 标签（"免费版"/"专业版"等）或 trial 状态。错误文案 SHALL 描述用户可理解的"当前方案"概念而不是数据库内部字段值。

#### Scenario: 试用期内的免费用户创建第 N 条物流规则
- **WHEN** 真实套餐 `free`、`trial_expires_at > now` 的用户尝试创建第 5 条物流规则
- **THEN** 系统允许创建(因 `get_effective_plan` 返回 `professional`,limit 为 -1)

#### Scenario: 试用过期后的免费用户被自动裁剪
- **WHEN** 已过期试用 + 真实套餐 `free` 的用户当前有 5 条启用规则
- **THEN** 自动裁剪逻辑保留 1 条最近使用,其余 4 条 `disabled_by_overflow = 1`

#### Scenario: 启用规则数量统计排除溢出禁用
- **WHEN** 任何特性闸门或限额检查需要统计"用户当前启用规则数"
- **THEN** SHALL 调用 `count_user_active_rules(session, user_id)`,该 helper 过滤 `is_active = 1 AND disabled_by_overflow = 0`

#### Scenario: 公共物流池单条添加走 effective plan
- **WHEN** 真实套餐 `free`、`trial_expires_at > now` 的用户调用 `POST /api/logistics-pool/{pool_id}/add-to-my-logistics`，且当前已有 3 条启用规则、plans.professional.logistics_limit = -1
- **THEN** 系统允许添加（因 `get_effective_logistics_limit` 返回 -1 = 无上限），返回 HTTP 200

#### Scenario: 公共物流池批量添加走 effective plan
- **WHEN** 真实套餐 `efficiency`、`trial_expires_at > now` 的用户调用 `POST /api/logistics-pool/batch-add-to-my-logistics`，body `{"ids": [p1, p2, p3, p4, p5]}`，当前已有 0 条启用规则、plans.professional.logistics_limit = -1
- **THEN** 系统允许全部添加，返回 HTTP 200，`added=5`

#### Scenario: 试用过期后批量添加按真实计划限额拒绝
- **WHEN** 真实套餐 `free`、`trial_expires_at <= now` 的用户调用 batch-add，当前已有 1 条启用规则、plans.free.logistics_limit = 1
- **THEN** 系统拒绝，返回 HTTP 403 detail "已达到您当前方案的物流规则上限（1 条）"，零条插入

#### Scenario: 限额=-1 时不施加上限
- **WHEN** 任何用户的 `get_effective_logistics_limit` 返回 -1
- **THEN** `_check_logistics_limit` SHALL 直接通过，不做计数比较

#### Scenario: 错误文案不暴露内部 plan 标签
- **WHEN** 任何用户因物流规则配额超限被拒绝
- **THEN** 响应 detail SHALL 形如 "已达到您当前方案的物流规则上限（N 条）"，N 是实际限额数；SHALL NOT 包含 "免费版"/"效率版"/"专业版"/"试用" 等字样

#### Scenario: 试用期内的免费用户访问佣金品类管理
- **WHEN** 真实套餐 `free`、`trial_expires_at > now` 的用户调用 `commission_categories` 路由下任一端点
- **THEN** 系统允许访问（因 `get_effective_plan` 返回 `professional`，落在 `COMMISSION_ALLOWED_TIERS`={professional,enterprise,gratitude,test} 内）

#### Scenario: 试用过期后的免费用户访问佣金品类被拒
- **WHEN** 真实套餐 `free`、`trial_expires_at <= now` 的用户调用 `commission_categories` 路由
- **THEN** 系统返回 HTTP 403（因 `get_effective_plan` 返回 `free`，不在白名单内）

#### Scenario: 试用期内的免费用户使用精准模式定价
- **WHEN** 真实套餐 `free`、`trial_expires_at > now` 的用户调用 pricing 路由的精准模式入口端点
- **THEN** 系统允许进入精准模式（因 `get_effective_plan` 返回 `professional`，不在被拒名单 {free, efficiency} 内）

#### Scenario: 试用过期后的免费用户使用精准模式被拒
- **WHEN** 真实套餐 `free`、`trial_expires_at <= now` 的用户调用 pricing 路由的精准模式入口端点
- **THEN** 系统按现有契约拒绝（因 `get_effective_plan` 返回 `free`，落在被拒名单内）
