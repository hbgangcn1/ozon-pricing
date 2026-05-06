## Context

本次变更覆盖 4 项前端/后端改进，均源于探索模式审查：

1. **套餐管理对接后端（plan-management-api）**：`PlanManagementPage` 当前使用硬编码 `initialPlans` 数组，编辑仅更新本地 state，刷新即丢。后端 `db/plans.py` 已有完整 CRUD（get_plans / create_plan / update_plan / delete_plan / toggle_plan_active），但 `api/routes/subscriptions.py` 仅暴露只读端点（GET /plans, GET /current）。`SubscriptionPage` 同样使用 `mockPlans` 硬编码。
2. **物流定价空状态提示（pricing-empty-state）**：`PricingPage` 在用户无物流规则时直接展示空表单，新用户无引导。
3. **产品列表批量删除（product-batch-delete）**：精准模式"产品列表"弹窗仅支持逐条编辑/删除，无法批量管理。
4. **物流编辑表单字段补全**：已在上一轮实现（LogisticsPage.jsx 新增 5 个控件），本次标记为 done。

技术栈：后端 FastAPI + SQLAlchemy async + PostgreSQL；前端 React 18 + shadcn/ui + Tailwind + Zustand。

## Goals / Non-Goals

### Goals
- 为 Plan CRUD 新增 REST 写入端点（POST / PUT / DELETE / PATCH），仅 admin 可操作
- `PlanManagementPage` 从 mock 切换为调用真实 API，支持创建、编辑、删除、启停套餐
- `SubscriptionPage` 的套餐列表从 `mockPlans` 改为调用 `GET /api/subscriptions/plans`
- `PricingPage` 在无物流规则时展示醒目的空状态提示文案
- 精准模式产品列表弹窗支持 Checkbox 多选 + 全选 + 批量删除 + AlertDialog 二次确认

### Non-Goals
- 不修改 Plan 数据库 schema（`models/user.py` 的 Plan 模型不变）
- 不新增前端路由或页面
- 不重新设计 UI 风格——保持现有深色主题 + indigo 主色 + shadcn/ui 组件
- 不实现产品批量编辑（仅批量删除）
- 不实现套餐的订阅/支付流程

## Decisions

### D1: Plan 写入端点放在 `api/routes/subscriptions.py` 还是新建 `api/routes/plans.py`？
**决定**：在 `api/routes/subscriptions.py` 中扩展。
**理由**：现有 `GET /api/subscriptions/plans` 已在此文件，保持路由前缀一致性（`/api/subscriptions/plans/{id}`）。Plan 端点数量仅 4 个，不值得拆分独立文件。

### D2: Plan 写入端点的权限控制
**决定**：所有写入端点（POST / PUT / DELETE / PATCH toggle）均要求 admin 角色。
**理由**：套餐管理是系统级配置，仅管理员可修改。使用现有 `get_current_user_id` + 检查 `user.role == 'admin'` 的模式。

### D3: 产品批量删除——前端循环调用 vs 新增后端批量端点
**决定**：前端循环调用现有 `DELETE /api/products/{id}` 端点。
**理由**：产品数量通常较少（<100），循环调用延迟可接受。避免后端新增端点的额外复杂度。如果未来需要支持大量产品批量操作，再考虑后端批量端点。

### D4: `PlanManagementPage` 的 features 字段存储格式
**决定**：在 API 层做 string ↔ array 转换，与现有 `get_plans_route` 的 features 处理保持一致。
**理由**：Plan 模型的 features 字段是逗号分隔的字符串（`String` 类型），前端使用 array。现有 GET 端点已有 `features.split(",")` 转换逻辑，写入端点做反向 `",".join()` 即可。

### D5: 物流定价空状态检测方式
**决定**：在 `PricingPage` 组件挂载时调用现有的物流规则列表 API，若返回空数组则展示空状态提示。
**理由**：复用现有 API，无需新增端点。空状态仅为 UI 提示，不阻塞页面其他功能。

## Risks / Trade-offs

### R1: 产品批量删除的并发请求
**风险**：选中 N 个产品后，前端发 N 个 DELETE 请求，可能触发限流。
**缓解**：使用 `Promise.allSettled` 并发执行，对失败项 toast 提示。产品数量通常较少，实际触发限流概率极低。

### R2: PlanManagementPage 迁移期间的数据一致性
**风险**：如果数据库中无初始 Plan 数据，迁移后页面为空。
**缓解**：假设 Alembic 迁移已 seed 默认套餐数据（从上一轮 system-wide-fixes-v4 完成）。如果数据库为空，admin 可通过新增端点创建。

### R3: SubscriptionPage 调用 API 失败时的 fallback
**风险**：API 不可用时页面空白。
**缓解**：保留 loading/error 状态展示，但移除 mock fallback 数据——显示真实错误比假数据更好。
