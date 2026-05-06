## 1. 后端 — Plan 写入 API 端点

- [ ] 1.1 在 `api/routes/subscriptions.py` 中添加 Pydantic 请求模型 `PlanCreateRequest` 和 `PlanUpdateRequest`，包含 plan_code、plan_name、prices、limits、description、features、sort_order 等字段
- [ ] 1.2 添加 admin 角色校验辅助函数 `_require_admin(user_id, session)`，检查 user.role == 'admin'，非 admin 返回 HTTP 403
- [ ] 1.3 实现 `POST /api/subscriptions/plans` 端点，调用 `db.plans.create_plan`，features 字段做 list→string 转换，返回创建的 plan 数据（HTTP 201）
- [ ] 1.4 实现 `PUT /api/subscriptions/plans/{plan_id}` 端点，调用 `db.plans.update_plan`，plan 不存在返回 HTTP 404
- [ ] 1.5 实现 `DELETE /api/subscriptions/plans/{plan_id}` 端点，调用 `db.plans.delete_plan`，plan 不存在返回 HTTP 404
- [ ] 1.6 实现 `PATCH /api/subscriptions/plans/{plan_id}/toggle` 端点，调用 `db.plans.toggle_plan_active`，返回新的 is_active 状态
- [ ] 1.7 为 4 个写入端点编写 pytest 测试用例（admin 成功、非 admin 403、plan 不存在 404）

## 2. 前端 — Plan API Service 方法

- [ ] 2.1 在 `frontend/src/services/api.js` 中添加 `plansAPI` 对象，包含 `getAll()`、`create(data)`、`update(id, data)`、`delete(id)`、`toggleActive(id)` 方法，分别调用后端对应端点

## 3. 前端 — PlanManagementPage 对接后端

- [ ] 3.1 移除 `PlanManagementPage.jsx` 中的 `initialPlans` 硬编码数组
- [ ] 3.2 页面挂载时调用 `plansAPI.getAll()` 获取套餐列表，添加 loading 和 error 状态
- [ ] 3.3 创建套餐操作改为调用 `plansAPI.create(data)`，成功后刷新列表
- [ ] 3.4 编辑套餐操作改为调用 `plansAPI.update(id, data)`，成功后刷新列表
- [ ] 3.5 删除套餐操作改为调用 `plansAPI.delete(id)`，成功后刷新列表
- [ ] 3.6 启停套餐操作改为调用 `plansAPI.toggleActive(id)`，成功后更新对应行状态
- [ ] 3.7 所有 API 操作失败时显示 toast 错误提示

## 4. 前端 — SubscriptionPage 套餐数据源替换

- [ ] 4.1 移除 `SubscriptionPage.jsx` 中的 `mockPlans` 硬编码数组
- [ ] 4.2 页面挂载时调用 `plansAPI.getAll()` 或 `GET /api/subscriptions/plans` 获取套餐数据
- [ ] 4.3 将 API 返回字段映射到现有 UI 卡片布局（code→plan_code, name→plan_name, features→array 等）
- [ ] 4.4 API 失败或返回空数组时显示合适的空状态/错误提示，不再 fallback 到 mock 数据

## 5. 前端 — PricingPage 空状态提示

- [ ] 5.1 在 `PricingPage.jsx` 组件挂载时调用物流规则列表 API（`GET /api/logistics`）检查是否有物流规则
- [ ] 5.2 当物流规则为空时，在页面顶部（Tabs 组件之前）渲染醒目的 Alert 提示组件，文案为"请先添加物流规则"，包含跳转到物流管理页面的链接
- [ ] 5.3 API 调用失败时不显示空状态提示（fail-open），不阻塞用户正常使用
- [ ] 5.4 当物流规则非空时，不渲染提示组件

## 6. 前端 — 精准模式产品列表批量删除

- [ ] 6.1 在产品列表弹窗中为每个产品行添加 Checkbox 组件，维护 `selectedProductIds` state（Set 类型）
- [ ] 6.2 在弹窗 header 区域添加"全选" Checkbox，支持全选/全不选切换，部分选中时显示 indeterminate 状态
- [ ] 6.3 当 selectedProductIds 非空时，在 DialogFooter 中显示"删除选中 (N)"按钮（destructive variant）
- [ ] 6.4 点击批量删除按钮时弹出 AlertDialog 二次确认，文案包含选中数量
- [ ] 6.5 确认删除后使用 `Promise.allSettled` 并发调用 `DELETE /api/products/{id}`，完成后刷新产品列表、清空选择、显示成功/部分失败 toast
- [ ] 6.6 关闭产品列表弹窗时清空选择状态

## 7. 物流编辑表单字段补全（已完成）

- [x] 7.1 在 LogisticsPage.jsx 物流编辑表单中新增 is_smart Switch、delivery_method Select、scoring_group Input、fbp_service_level Select、fbp_company Input 共 5 个控件
