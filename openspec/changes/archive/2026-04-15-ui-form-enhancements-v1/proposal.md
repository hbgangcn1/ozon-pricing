## Why

探索模式审查中发现多个前端页面存在功能缺失和体验问题：套餐管理页面使用硬编码 mock 数据未对接后端；物流定价页面在无物流规则时缺乏引导；精准模式产品列表弹窗无法批量管理产品；物流编辑表单缺少 5 个关键业务字段的编辑控件。这些问题直接影响系统的可用性和数据完整性，需要统一修复。

## What Changes

- **套餐管理对接后端 CRUD**：PlanManagementPage 从硬编码 `initialPlans` 改为调用后端 `db/plans.py` 已有的完整 CRUD API（get/create/update/delete/toggle_active），SubscriptionPage 的套餐列表也从 mock 改为从 API 读取
- **新增订阅相关 API 端点**：当前 `api/routes/subscriptions.py` 只有只读端点（GET /plans, GET /current），需要新增 Plan 的写入端点（POST/PUT/DELETE）供套餐管理页面调用
- **物流定价空状态提示**：当用户尚未添加任何物流规则时，在定价页面用醒目文字提示"请先添加物流规则"，引导用户操作
- **精准模式产品列表批量删除**：在精准模式点击"打开产品列表"弹窗中，为每条产品添加选择框（支持单选、全选），选中后显示删除按钮，二次确认后删除选中产品
- **物流编辑表单字段补全**（✅ 已实现）：在物流规则编辑表单中新增 `is_smart`（Switch）、`delivery_method`（Select）、`scoring_group`（Input）、`fbp_service_level`（Select）、`fbp_company`（Input）5 个控件，FBP 相关字段仅在 `fulfillment_type === 'fbp'` 时显示

## Capabilities

### New Capabilities
- `plan-management-api`: 套餐管理后端写入 API — 为 PlanManagementPage 提供 Plan 的 CRUD 端点，前端页面对接真实后端数据
- `pricing-empty-state`: 定价页面空状态引导 — 无物流规则时显示引导提示，改善新用户首次使用体验
- `product-batch-delete`: 精准模式产品批量删除 — 在产品列表弹窗中支持多选和批量删除操作

### Modified Capabilities
- `subscription-feature-gating`: SubscriptionPage 的套餐列表数据源从 mock 改为 API 读取，与 PlanManagementPage 的 Plan CRUD 联动

## Impact

- **后端**：`api/routes/subscriptions.py` 新增 Plan 写入端点；可能需要新建 `api/routes/plans.py` 或在 subscriptions 路由中扩展
- **前端页面**：`PlanManagementPage.jsx`（重构数据层）、`SubscriptionPage.jsx`（替换 mock）、`PricingPage.jsx`（新增空状态）、精准模式产品弹窗（新增批量操作）
- **前端 services**：需要新增 Plan API 调用方法
- **数据库**：无 schema 变更，`db/plans.py` CRUD 已完整实现
- **已完成项**：`LogisticsPage.jsx` 物流编辑表单 5 个字段控件已实现，本次 change 中标记为 done
