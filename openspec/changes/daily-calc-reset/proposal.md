## Why

当前系统没有每日重置计算次数的机制。用户设置套餐的"计算次数"后，该次数永远不会自动重置，导致免费用户用完分配的次数后永久失去计算能力。此外，前端错误地显示"次/月"，但实际上根本没有按月重置的逻辑。

## What Changes

- **新增每日重置功能**：在用户登录时检查是否需要重置计算次数
- **新增重置日期跟踪字段**：`User.last_calculations_reset_date` 记录上次重置日期
- **重置逻辑**：仅对 `calc_limit != -1`（非无限）的套餐用户重置，重置值来自套餐的 `calc_limit`
- **修复前端显示**：`PlanManagementPage` 和 `SubscriptionPage` 的"次/月"改为"次/天"

## Capabilities

### New Capabilities

- `daily-calc-reset`: 用户登录时自动重置有限次数套餐的计算次数

### Modified Capabilities

- （无）

## Impact

- **数据库**：新增 `last_calculations_reset_date` 字段到 `users` 表
- **后端**：`db/subscriptions.py` 新增重置函数，`api/routes/auth.py` 登录流程接入
- **前端**：`PlanManagementPage.jsx` 和 `SubscriptionPage.jsx` 显示文本修复
- **迁移**：Alembic 迁移脚本在服务启动时自动执行