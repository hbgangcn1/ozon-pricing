## ADDED Requirements

### Requirement: 佣金类目读取端点闸门

`GET /api/commission-categories` 与同路由下的任何只读子端点 SHALL 通过 `Depends(get_user_with_subscription)` 取 user dict，并在请求处理早期调用 helper `_ensure_commission_access(user)`（该 helper 内部调 `services.plan_resolution.get_effective_plan(user)`）；若 effective plan 不在 `COMMISSION_ALLOWED_TIERS = {professional, enterprise, gratitude, test}` 内 SHALL 返回 HTTP 403。错误 detail SHALL NOT 暴露内部 plan 标签或 trial 状态字段。`_ensure_commission_access` 同款 helper SHALL 同时被 POST/PATCH/DELETE 端点复用（替代历史 `_ensure_commission_write_access`，语义合并覆盖读写）。

#### Scenario: 试用期内 free 用户读取佣金类目成功
- **WHEN** 真实套餐 `free`、`trial_expires_at > now`、`trial_used = 1` 的用户调用 `GET /api/commission-categories`
- **THEN** 系统返回 HTTP 200 与该用户的佣金类目列表（因 `get_effective_plan` 返回 `professional`，落在白名单内）

#### Scenario: 试用过期后 free 用户读取佣金类目被拒
- **WHEN** 真实套餐 `free`、`trial_expires_at <= now`、`trial_used = 1` 的用户调用 `GET /api/commission-categories`
- **THEN** 系统返回 HTTP 403，错误 detail 不包含 "免费版" / "试用" / "trial" / 数据库内部字段名

#### Scenario: 真实免费用户从未试用读取佣金类目被拒
- **WHEN** 真实套餐 `free`、`trial_used = 0`、`trial_expires_at = 0` 的用户调用 `GET /api/commission-categories`
- **THEN** 系统返回 HTTP 403

#### Scenario: 真实专业版用户读取佣金类目成功
- **WHEN** 真实套餐 `professional` 的用户调用 `GET /api/commission-categories`
- **THEN** 系统返回 HTTP 200

### Requirement: 前端佣金管理整页拦截与请求阻断

前端 `CommissionCategoriesPage` SHALL 通过 `authStore.hasProfessionalAccess()`（trial-aware）作为单一闸门：

- 当 `hasProfessionalAccess()` 返回 false 时，整页 SHALL 替换为**页面内本地** `UpgradePrompt` 函数（`CommissionCategoriesPage.jsx:16-27` 既有定义，非共享组件），SHALL NOT 渲染表格、表单、按钮，SHALL NOT 渲染本地缓存的旧佣金数据。
- 当 `hasProfessionalAccess()` 返回 false 时，页面所有 fetch 入口（`useCallback fetchCategories` + 初始 `useEffect`）SHALL 在函数体最开头守卫 `if (!canManage) { setCategories([]); return }`，确保 `GET /api/commission-categories` 不被触发。
- 当用户在试用过期后通过外部方式（升级订阅 / 服务端写入新 trial_expires_at）让 `hasProfessionalAccess()` 重新返回 true，整页 SHALL 在用户下次刷新或重新登录后自动恢复管理界面（**不**要求实时 polling）。

#### Scenario: 试用期内进入页面正常渲染
- **WHEN** `hasProfessionalAccess()` 返回 true 的用户访问 `/commission-categories`
- **THEN** 页面渲染佣金类目表格，正常发起 `GET /api/commission-categories`

#### Scenario: 试用过期访问页面整页拦截
- **WHEN** `hasProfessionalAccess()` 返回 false 的用户访问 `/commission-categories`
- **THEN** 页面只渲染**页面内本地** `UpgradePrompt` 升级提示卡片；浏览器网络面板中 SHALL NOT 出现 `/api/commission-categories` 请求

#### Scenario: 试用过期但本地 state 残留旧数据时不复显
- **WHEN** 用户在试用期内浏览过页面（categories state 已加载），随后试用过期再次访问
- **THEN** 由于守卫立即 `setCategories([])` 且整页替换为**页面内本地** `UpgradePrompt`，旧数据 SHALL NOT 显示

### Requirement: PricingPage 周边 commission API 调用闸门

`frontend/src/pages/pricing/usePricingCalculation.js` 中所有 `commissionCategoriesAPI.getAll()` 调用入口（`refreshCommissionCategories` callback + 初始 `useEffect` 内的 `Promise.all`）SHALL 通过 `useAuthStore.getState().hasProfessionalAccess()` 守卫；返回 false 时 SHALL 跳过 API 调用，将 `commissionCategories` state 设为 `[]`，避免非专业版用户加载 PricingPage 时触发 GET 403 噪音。

#### Scenario: 非专业版用户加载 PricingPage 不触发 commission GET
- **WHEN** `hasProfessionalAccess()` 返回 false 的用户挂载 PricingPage（触发 `usePricingCalculation` 初始化）
- **THEN** `commissionCategoriesAPI.getAll` SHALL 0 次被调用；`commissionCategories` state SHALL 等于 `[]`

#### Scenario: 试用期内 free 用户加载 PricingPage 正常拉取 commission
- **WHEN** 真实套餐 `free`、`trial_expires_at > now` 的用户挂载 PricingPage
- **THEN** `commissionCategoriesAPI.getAll` SHALL 被调用 1 次；commission 数据正常用于精准模式定价

## MODIFIED Requirements

### Requirement: 特性闸门基于 effective plan

所有依赖订阅级别决策的特性闸门 SHALL 基于 `services.plan_resolution.get_effective_plan(user)` 而非直接读 `users.subscription_type`。包括但不限于:物流规则数量限制（含公共物流池单条/批量添加端点 `_check_logistics_limit` 与 `_get_user_subscription`）、佣金品类访问权限（`commission_categories` 路由的**读和写所有端点**）、定价计算精准模式入口门禁（`pricing` 路由两处入口）、规则启用动作。试用期内 free/efficiency 用户 SHALL 享有与真实 professional 用户相同的能力闸门待遇。

前端特性闸门（`authStore.hasProfessionalAccess()` 等 selector）SHALL 与后端 `get_effective_plan` 等价：admin 短路保留**在 trial 检查之前**；真实套餐 ∈ PROFESSIONAL_TIERS 直接返回 true；否则按 `isInTrial()` 兜底（`u.trial_expires_at > Math.floor(Date.now()/1000)`，与后端 `int(time.time())` 对齐 epoch 秒）。前端 SHALL 通过 `/api/auth/me` / `/api/auth/login` / `/api/auth/register` 三处响应与 `get_current_user` / `get_user_with_subscription` 两处 dep 返回的 trial 字段判断试用状态，SHALL NOT 依赖单独的 `/api/subscriptions/trial/status` 调用。

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

#### Scenario: 试用期内的免费用户访问佣金品类管理（写）
- **WHEN** 真实套餐 `free`、`trial_expires_at > now` 的用户调用 `commission_categories` 路由下任一写端点
- **THEN** 系统允许访问（因 `get_effective_plan` 返回 `professional`，落在 `COMMISSION_ALLOWED_TIERS`={professional,enterprise,gratitude,test} 内）

#### Scenario: 试用过期后的免费用户访问佣金品类管理（写）被拒
- **WHEN** 真实套餐 `free`、`trial_expires_at <= now` 的用户调用 `commission_categories` 路由的任一写端点
- **THEN** 系统返回 HTTP 403（因 `get_effective_plan` 返回 `free`，不在白名单内）

#### Scenario: 试用期内的免费用户使用精准模式定价
- **WHEN** 真实套餐 `free`、`trial_expires_at > now` 的用户调用 pricing 路由的精准模式入口端点
- **THEN** 系统允许进入精准模式（因 `get_effective_plan` 返回 `professional`，不在被拒名单 {free, efficiency} 内）

#### Scenario: 试用过期后的免费用户使用精准模式被拒
- **WHEN** 真实套餐 `free`、`trial_expires_at <= now` 的用户调用 pricing 路由的精准模式入口端点
- **THEN** 系统按现有契约拒绝（因 `get_effective_plan` 返回 `free`，落在被拒名单内）

#### Scenario: 前端 hasProfessionalAccess admin 短路优先级
- **WHEN** 前端 user 对象 `role='admin'` 且 `subscription_type='free'`、`trial_expires_at=0`
- **THEN** `authStore.hasProfessionalAccess()` 返回 true（admin 检查在 trial 之前）

#### Scenario: 前端 hasProfessionalAccess 试用期内放行
- **WHEN** 前端 user 对象 `subscription_type='free'`、`role='user'` 且 `trial_expires_at` 大于当前 epoch 秒
- **THEN** `authStore.hasProfessionalAccess()` 返回 true

#### Scenario: 前端 hasProfessionalAccess 试用过期阻断
- **WHEN** 前端 user 对象 `subscription_type='free'`、`role='user'`、`trial_used=1`、`trial_expires_at` 小于等于当前 epoch 秒
- **THEN** `authStore.hasProfessionalAccess()` 返回 false
