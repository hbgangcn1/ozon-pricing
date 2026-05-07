## Purpose

subscription-feature-gating capability spec.
## Requirements
### Requirement: 套餐升级按钮触发支付
订阅管理页面的套餐升级按钮 SHALL 触发真实的微信支付流程，而非显示"功能开发中"提示。升级按钮仅对高于当前套餐的计划显示。免费版与效率版用户若 `trial_used = 0` 且未在试用中,SHALL 在订阅管理页面同时看到"开始 7 天专业版试用"按钮(独立于升级按钮)。

#### Scenario: 点击升级按钮发起支付
- **WHEN** 用户在订阅管理页面点击某个套餐的"升级"按钮
- **THEN** 系统打开支付确认对话框，显示目标套餐名称、计费周期选择（月/年）、对应价格，用户确认后打开支付二维码弹窗

#### Scenario: 已是当前套餐不显示升级
- **WHEN** 用户当前套餐为专业版
- **THEN** 专业版卡片显示"当前套餐"标识，不显示升级按钮；效率版和免费版卡片不显示升级按钮（不允许降级）；企业版卡片显示升级按钮

#### Scenario: 支付成功后刷新订阅状态
- **WHEN** 支付二维码弹窗检测到支付成功
- **THEN** 系统自动刷新订阅管理页面的当前套餐信息，显示新套餐的权限和有效期;同时刷新 `GET /api/subscriptions/trial/status`(若用户在试用中,升级会立即关闭试用相关 UI)

#### Scenario: 免费版用户升级
- **WHEN** 免费版用户点击效率版/专业版/企业版的升级按钮
- **THEN** 系统显示支付确认对话框，金额为所选套餐的 actual_price（月/年），确认后进入支付流程

#### Scenario: 符合资格的用户看到试用按钮
- **WHEN** 真实套餐为 `free` 或 `efficiency` 且 `trial_used = 0` 的用户访问订阅管理页面
- **THEN** 页面在升级按钮之外另外显示"开始 7 天专业版试用"按钮,点击后调用试用领取接口

#### Scenario: 试用进行中的免费用户升级关闭试用 UI
- **WHEN** 试用期内的 `free` 用户成功完成升级支付,后端经由 `apply_subscription_change` 将其升至 `professional`
- **THEN** 前端轮询 `GET /api/subscriptions/trial/status` 后 `in_trial = false`,试用横幅消失;若该用户存在 `disabled_by_overflow = 1` 规则(理论上试用期内不会有,但兼容性场景),全部一次性恢复

### Requirement: 特性闸门基于 effective plan

所有依赖订阅级别决策的特性闸门 SHALL 基于 `services.plan_resolution.get_effective_plan(user)` 而非直接读 `users.subscription_type`。包括但不限于:物流规则数量限制、产品数量限制(如有)、定价计算入口、规则启用动作。试用期内 free/efficiency 用户 SHALL 享有与真实 professional 用户相同的能力闸门待遇。

#### Scenario: 试用期内的免费用户创建第 N 条物流规则
- **WHEN** 真实套餐 `free`、`trial_expires_at > now` 的用户尝试创建第 5 条物流规则
- **THEN** 系统允许创建(因 `get_effective_plan` 返回 `professional`,limit 为 -1)

#### Scenario: 试用过期后的免费用户被自动裁剪
- **WHEN** 已过期试用 + 真实套餐 `free` 的用户当前有 5 条启用规则
- **THEN** 自动裁剪逻辑保留 1 条最近使用,其余 4 条 `disabled_by_overflow = 1`

#### Scenario: 启用规则数量统计排除溢出禁用
- **WHEN** 任何特性闸门或限额检查需要统计"用户当前启用规则数"
- **THEN** SHALL 调用 `count_user_active_rules(session, user_id)`,该 helper 过滤 `is_active = 1 AND disabled_by_overflow = 0`

