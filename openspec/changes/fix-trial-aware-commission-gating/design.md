## Context

`subscription-feature-gating` 与 `pro-trial` 规约已经规定：所有特性闸门 SHALL 基于 `services.plan_resolution.get_effective_plan(user)`，试用期内的 free/efficiency 用户应享有与真实 professional 相同的能力。但当前实现存在两处偏差，叠加后导致用户报告的 bug：

1. **后端 `commission_categories` GET 端点未做闸门校验**——POST/PATCH/DELETE 已通过 `_ensure_commission_write_access`（`commission_categories.py:21-34`，已用 `SimpleNamespace(**user)` 包装 dict 喂给 `get_effective_plan`）走 plan gate，但 GET 路径用的是 `Depends(get_current_user_id)`（仅返回 int user_id），完全跳过任何 plan 校验——不仅试用过期不挡，连从未试用的真实免费用户也能 GET 自己的历史数据。
2. **前端 `authStore.hasProfessionalAccess()` 完全忽略试用字段**——只检查 `subscription_type ∈ PROFESSIONAL_TIERS`，且 `get_current_user` / `get_user_with_subscription` 两处 dep 与 `/api/auth/me` / `/login` / `/register` 三处响应构造点都没把 `trial_*` 字段下发。`buildPersistedUser` 白名单也无对应字段，前端缺少判断试用的数据源。结果：试用领取后，前端在路由层就把整页拦下来，根本走不到后端闸门。

User ORM (`models/user.py:11,17,22,40,54,89-108`) 的 trial 四字段 (`trial_used`、`trial_started_at`、`trial_expires_at`、`trial_plan_at_start`) 已存在并是 NOT NULL 列（server defaults 0/0/0/''），且在 `db/users.py` 已被 SELECT。本次只做 schema/路由/前端的最小修改。

## Goals / Non-Goals

**Goals:**
- 修复试用期内 free/efficiency 用户访问佣金管理整页拦截的 bug；试用期内可正常 view/create/edit/delete。
- 试用过期后呈现完整拦截页（无读、无写），DB 数据保留；升级到 professional/enterprise 后历史数据立即可见。
- 前端、后端 GET、后端写、`get_effective_plan` 四处对"谁能访问佣金管理"判断完全等价。
- 同一套"试用过期模拟"机制覆盖 pytest fixture 与 Playwright/Manual QA。
- 顺手修复 PricingPage 周边 `usePricingCalculation` 初始化 fetch 触发 commission 403 噪音的问题。

**Non-Goals:**
- 不改 `hasEnterpriseAccess()`（Excel 导入是企业版专属，与试用无关，产品规则未变）。
- 不改 `LogisticsPoolPage`、`ProductImportPage`。
- 不改 `PricingPage.jsx:12`（已现场核验，常量 `'efficiency'` 是 truthy 已正确，非 bug；`usePricingCalculation` 才是真实问题源）。
- 不做 DB 迁移、不引入新依赖、不新增 `/api/dev/*` 测试端点。
- 不改 `apply_subscription_change` chokepoint 与试用领取流程本身。
- 不改 `services/plan_resolution.py`（单一真实来源已就绪，0 改动）。

## Decisions

### Decision 1: trial 字段下发渠道 = `/api/auth/me` + `/login` + `/register` + 两处 dep，单一数据源

**选择**：在 `UserResponse` schema 与 `get_current_user` + `get_user_with_subscription` 两处 dep 返回 dict 中追加 `trial_used`、`trial_started_at`、`trial_expires_at`、`trial_plan_at_start` 四字段。`/api/auth/me`、`/api/auth/login`、`/api/auth/register` 三处 UserResponse 构造同步透传。前端在登录与路由切换刷新 user 时即可拿到 trial 状态，无需额外调用 `/api/subscriptions/trial/status`。

**字段类型**：非 Optional，默认 `trial_used=0`、`trial_started_at=0`、`trial_expires_at=0`、`trial_plan_at_start=""`，与 ORM 非空 server defaults 完全对齐，避免 None/0 二义性。

**替代方案**：让前端每次判断 `hasProfessionalAccess()` 都先调用 `trial/status`。否决理由：(1) 显著增加请求量；(2) Zustand selector 必须是同步函数，异步获取破坏组件渲染契约；(3) `/me` 已有调用点，叠加字段是零成本扩展。

### Decision 2: 后端 GET commission gating = 复用同款 helper（rename for semantic clarity）

**选择**：将 `_ensure_commission_write_access` rename 为 `_ensure_commission_access`（语义不再仅限"写"），POST/PATCH/DELETE 现有调用同步替换名字、行为不变。GET 端点 `list_categories` 改用 `Depends(get_user_with_subscription)`（取代当前 `get_current_user_id`），开头调用 `_ensure_commission_access(user)`；不在 `COMMISSION_ALLOWED_TIERS = {professional, enterprise, gratitude, test}` 内则 raise HTTPException(403)。**HTTPException detail 必须从历史 "此功能需要专业版或更高订阅等级" 改为中性 "当前方案暂不支持此功能"**——遵循 `subscription-feature-gating` 规约不暴露内部 plan 标签 / trial 状态。删除 `commission_categories.py` 顶部 `get_current_user_id` import。

**替代方案**：写一个新 helper `_ensure_commission_read_access`。否决理由：读写规则相同，引入单独 helper 制造重复语义。

### Decision 3: 前端 `hasProfessionalAccess()` = trial-aware 单函数（admin 优先级保留）

**选择**：
```js
isInTrial: () => {
  const u = get().user
  if (!u || typeof u.trial_expires_at !== 'number') return false
  return u.trial_expires_at > Math.floor(Date.now() / 1000)
},

hasProfessionalAccess: () => {
  if (get().isAdmin()) return true                          // admin 短路保留在最前
  const subscriptionType = get().getSubscriptionType()
  if (PROFESSIONAL_TIERS.includes(subscriptionType)) return true
  return get().isInTrial()                                  // trial overlay 兜底
}
```
`buildPersistedUser` 白名单必须把 trial 四字段一并 persist，否则 reload 后丢失。

**关键顺序约束**：admin 检查 MUST 在 trial 检查之前，否则若 trial 实现出 bug，admin 会被错误降级。

**替代方案**：新增 `hasCommissionAccess()` 与 `hasProfessionalAccess()` 并存。否决理由：用户已确认 PricingPage 与 CommissionCategoriesPage 都给试用用户放行，单函数语义正确；引入双函数制造长期维护陷阱。

### Decision 4: 拦截时前端不发 GET = 两处 fetch 入口守卫（不依赖 React Query）

**选择**：CommissionCategoriesPage 是手写 `useEffect` + `useCallback fetchCategories` + `AbortController`（**非 React Query**，已现场核验 `CommissionCategoriesPage.jsx:44-79`）。在两处 fetch 入口都加 `if (!canManage) { setCategories([]); return }` 守卫；`!canManage` 时整页渲染**页面内本地 `UpgradePrompt` 函数**（已存在 `CommissionCategoriesPage.jsx:16-27`，**非**共享组件、**无** import；本次复用该本地函数，不创建新文件）；后端 GET 仍返回 403 作为 defense-in-depth。

**usePricingCalculation 同样处理**：`frontend/src/pages/pricing/usePricingCalculation.js:39,61-84` 的 `refreshCommissionCategories` 与初始 useEffect 两处都用 `useAuthStore.getState().hasProfessionalAccess()` 守卫——不通过则 `Promise.resolve([])` 替代 `commissionCategoriesAPI.getAll()`，避免非专业版用户加载 PricingPage 时触发 403 噪音。

**替代方案 A**：让前端发请求拿 403。否决理由：(1) 控制台 403 噪音；(2) 浪费请求；(3) 既然产品规则是"完全不能查看"，连请求也不应发。
**替代方案 B**：引入 React Query。否决理由：架构变更超出本次范围；现有手写 fetch + 短路守卫足够。
**替代方案 C**：新建 `UpgradeBlocker` 组件。否决理由：项目无此组件，且 `UpgradePrompt` 已满足需求；新增组件制造维护负担。

### Decision 5: 试用过期模拟方式 = 直接改 `trial_expires_at`（含安全双护栏）

**选择**：统一通过修改 `users.trial_expires_at` 为过去 unix 时间戳模拟过期，保持 `trial_used=1`、`trial_started_at` 不变。
- pytest：fixture 用 SQLAlchemy `await session.execute(update(User).where(User.id == uid).values(trial_expires_at=int(time.time()) - 86400))`
- Playwright Manual QA：`psql -h localhost -U postgres -d logistics_dev -c "UPDATE users SET trial_expires_at = EXTRACT(epoch FROM now())::int - 3600 WHERE is_test_user=1 AND email='qa-trial@cbprice.cn'"`，**强制双护栏**：(1) `WHERE is_test_user=1 AND email='qa-trial@cbprice.cn'`；(2) 执行前必须 `psql ... -c "\conninfo"` 确认 DB 名包含 `dev` 或 `test`，禁止纯 `logistics` 生产名。

**替代方案**：(A2) 新增 `POST /api/dev/expire-trial` 由 `E2E_TEST` 守卫；(A3) 双轨。否决理由：A2 增加 prod-shape 代码与安全风险（即便 env 守卫，新端点是攻击面）；A3 重复定义"过期"语义。直接 SQL 是事实层面的"过期"，确定性最强。

### Decision 6: PricingPage 入口闸门维持现状

**选择**：`PricingPage.jsx:12` 现状已是常量 `'efficiency'`（非用户表达式 `user?.user_type === 'efficiency'`），属于 truthy 静态判断，行为正确。本次 NOT 改 PricingPage 入口；真实问题在 `usePricingCalculation` 初始化 fetch 触发 403 噪音，已在 Decision 4 处理。

## Risks / Trade-offs

- **Risk: Pydantic v2 与 schema 序列化差异** → Mitigation: README 已确认 Pydantic v2；`UserResponse` 已用 `model_config = ConfigDict(from_attributes=True)`；新增字段为非 Optional + 默认值，与 ORM NOT NULL 列直接对齐。
- **Risk: `buildPersistedUser` 漏带 trial 字段导致 reload 后 `hasProfessionalAccess()` 误判 false** → Mitigation: tasks.md 显式列出 persist 字段清单 + Vitest 断言 reload 后字段保留。
- **Risk: 试用刚过期的 1 秒边界** → Mitigation: `trial_expires_at > now` 严格大于；后端 `is_in_trial` 已用同样语义；前端 `Math.floor(Date.now()/1000)` 与后端 `int(time.time())` 对齐 epoch 秒。客户端时钟偏移属于已知容忍范围，不在本次范围。
- **Risk: 修改 `hasProfessionalAccess` 影响其他未审计页面** → Mitigation: 已审计——目前仅 CommissionCategoriesPage、`usePricingCalculation`、SubscriptionPage 引用；其他页面不受影响。tasks.md 包含 ripgrep 二次审计步骤。
- **Risk: GET 闸门改动破坏现有前端缓存逻辑** → Mitigation: 试用/专业版用户路径不变；只对真正不该看的用户加 403。Vitest + Playwright 覆盖正反场景。
- **Risk: helper rename 漏改 POST/PATCH/DELETE 调用点导致 NameError** → Mitigation: tasks.md 强制 grep `_ensure_commission_write_access` 必须 0 命中作为 acceptance 门。
- **Risk: auth.py 三处 UserResponse 构造点的 user 形态不同（dict / ORM）** → Mitigation: tasks.md 要求逐个核对取值路径，acceptance 用 grep 校验 `trial_expires_at` 在 auth.py 出现 ≥3 次。
- **Trade-off**：试用过期模拟用直接 SQL 而非 API，意味着 pytest fixture 直接操作 DB 行；本项目其他测试已大量这么做，符合既有风格。Manual QA 同款 SQL 通过双护栏抵消生产误伤风险。
