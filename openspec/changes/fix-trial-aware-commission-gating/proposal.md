## Why

免费版与效率版用户领取 7 天专业版试用后，佣金类目管理页仍显示"升级到专业版"拦截页，无法新增/编辑/查看佣金规则。`subscription-feature-gating` 规约要求所有特性闸门基于 `get_effective_plan(user)`，但当前实现存在两处偏离：(1) 后端 `GET /api/commission-categories` 用 `Depends(get_current_user_id)` 仅做用户隔离，**完全跳过**任何 plan 闸门——不仅试用过期不挡，连真实免费用户也能 GET 自己的历史数据；(2) 前端 `authStore.hasProfessionalAccess()` 仅看 `subscription_type` 字段，完全忽略试用状态，且 `/api/auth/me` / `/login` / `/register` 三处 `UserResponse` 与 `get_current_user` / `get_user_with_subscription` 两处 dep 都没把 `trial_*` 字段下发，前端缺少判断试用的数据源。结果：试用领取后，前端在路由层就把整页拦下来，根本走不到后端。

## What Changes

- 后端 `UserResponse` schema、`get_current_user` 与 `get_user_with_subscription` 两处 dep、`/api/auth/me` + `/login` + `/register` 三处响应构造点 SHALL 携带 `trial_used` / `trial_started_at` / `trial_expires_at` / `trial_plan_at_start` 四字段（非 Optional，零值默认；与 ORM 非空 server defaults 对齐），作为前端判断试用状态的单一数据源。
- 后端 `GET /api/commission-categories` SHALL 改用 `Depends(get_user_with_subscription)` 并复用 helper `_ensure_commission_access`（由 `_ensure_commission_write_access` 重命名而来，语义统一覆盖读写）；非专业版及试用过期用户返回 HTTP 403。POST/PATCH/DELETE 现有行为保持不变，仅替换 helper 名。
- 前端 `authStore.hasProfessionalAccess()` SHALL 改为 trial-aware：admin 短路保留**在 trial 检查之前**；真实套餐 ∈ PROFESSIONAL_TIERS 直接返回 true；否则返回 `isInTrial()`（新增 selector，用 `Math.floor(Date.now()/1000)` 与后端 `int(time.time())` 对齐秒级）。`buildPersistedUser` SHALL 持久化新增的 trial 4 字段。
- 前端 `CommissionCategoriesPage` SHALL 在 `!hasProfessionalAccess()` 时整页替换为**页面内本地** `UpgradePrompt` 函数（`CommissionCategoriesPage.jsx:16-27` 既有定义，**非**共享组件，**不**新建 UpgradeBlocker、**不** import 外部组件）；两处 fetch 入口（`useCallback fetchCategories` + 初始 `useEffect`）SHALL 在 `!canManage` 时立即 `setCategories([])` 并 return，避免触发 GET。
- 前端 `frontend/src/pages/pricing/usePricingCalculation.js` 初始 useEffect 与 `refreshCommissionCategories` 两处 SHALL 按 `hasProfessionalAccess()` 短路 commission API 调用，避免非专业版用户加载 PricingPage 时触发 403 噪音。
- 前端 `PricingPage.jsx:12` 现状已用常量 `'efficiency'`（已现场核验，非 bug），本次 NOT 改动。
- 试用过期模拟方式（QA + 自动化测试统一）：直接将 `users.trial_expires_at` 改为过去时间戳。pytest 通过 SQLAlchemy fixture 写入；Manual QA 通过 `psql` 同等 SQL 写入，**强制双护栏** `WHERE is_test_user=1 AND email='qa-trial@cbprice.cn'` + `\conninfo` 验证 DB 名。**不**新增 `/api/dev/*` 端点。
- **范围边界**：本次 NOT 涉及 `hasEnterpriseAccess()`（Excel 导入仍为企业版专属，与试用无关）；NOT 涉及 `LogisticsPoolPage` 与 `ProductImportPage`；NOT 涉及任何数据库迁移（`trial_*` 字段已在 `users` 表）；NOT 改 `services/plan_resolution.py`（单一真实来源已就绪）。

## Capabilities

### New Capabilities
（无）

### Modified Capabilities
- `subscription-feature-gating`: 补齐 `commission_categories` GET 端点的 `get_effective_plan` 校验；新增前端特性闸门 SHALL 与后端 `get_effective_plan` 等价、SHALL 在拦截时阻止数据请求；PricingPage 周边 `usePricingCalculation` 初始化 fetch SHALL 按相同闸门短路。
- `pro-trial`: `/api/auth/me`、`/login`、`/register` 响应 SHALL 携带 trial 四字段；`get_current_user` 与 `get_user_with_subscription` 两处 dep 返回 dict SHALL 携带 trial 四字段。

## Impact

- **后端代码**：`api/models/schemas.py`（UserResponse 新增 4 trial 字段，非 Optional 默认 0/""）、`api/routes/auth.py`（login + register + /me 三处 UserResponse 序列化）、`api/dependencies.py`（`get_current_user` + `get_user_with_subscription` 两处 dict）、`api/routes/commission_categories.py`（rename helper + GET 改 dep + 接入 gate）。
- **前端代码**：`frontend/src/stores/authStore.js`（`buildPersistedUser` 加 4 字段、新增 `isInTrial`、`hasProfessionalAccess` 接 trial overlay）、`frontend/src/pages/CommissionCategoriesPage.jsx`（两处 fetch 守卫 + UpgradePrompt 渲染）、`frontend/src/pages/pricing/usePricingCalculation.js`（两处 fetch 守卫）。
- **测试**：pytest 新增 commission GET trial-期 200 / 过期 403 / professional 200 / plain-free 403 共 4 case；Vitest 新增 authStore.trial（isInTrial + hasProfessionalAccess 三态 + buildPersistedUser 持久化）+ CommissionCategoriesPage（非 canManage 时 0 GET 调用）+ usePricingCalculation（非 canManage 时 0 commission GET 调用）。
- **依赖**：无新增。
- **数据库**：无迁移。
- **API 契约**：`/api/auth/me`、`/login`、`/register` 响应新增 4 字段（向后兼容增量）；`GET /api/commission-categories` 新增 403 响应（针对未授权用户，原本任何已登录用户都返回 200 + 自己的数据）。
- **跨端一致性**：完成后前端、后端 GET、后端写操作、`get_effective_plan` 四处对"谁能访问佣金管理"的判断完全一致。
