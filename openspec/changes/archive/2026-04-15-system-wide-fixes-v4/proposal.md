## Why

系统存在多处功能缺陷和未完成模块，影响核心业务流程和管理能力：

1. **定价计算结果缺失关键标注** — Smart 物流标记在后端到前端的传递链路断裂，用户无法区分 Smart 物流方案
2. **定价计算精度问题** — 饼图百分比使用错误的分母（总成本而非售价），利润率因迭代四舍五入产生 ~0.1% 偏差
3. **佣金类目缺少用户隔离** — 当前为全局数据且 Admin 独占，无法支撑多用户独立管理佣金的业务需求；同时缺少订阅等级的功能门控
4. **统计模块几乎完全失效** — 前端全部使用硬编码假数据，后端有 4 个端点返回假数据、多个端点存在逻辑错误，搜索/导出/分页等交互功能均未实现

## What Changes

### 定价引擎修复
- 修复 Smart 物流标记从数据库到前端的完整传递链路（`schemas.py` → `pricing.py` → 前端 Badge）
- 修复饼图百分比计算：分母从 `totalCost` 改为 `totalPrice`（售价）
- 调整定价公式使反推利润率严格等于用户设定的目标利润率

### 佣金类目用户隔离
- `CommissionCategory` 模型新增 `user_id` 字段，唯一约束改为 per-user
- 所有佣金类目 CRUD 操作增加用户级过滤
- API 权限从 `require_admin` 改为 `get_current_user_id`，允许非 admin 用户管理自己的佣金
- 定价引擎佣金获取增加用户上下文
- 免费版/效率版禁用佣金类目管理（订阅等级门控）
- 新用户佣金从空开始，Admin 也作为普通用户管理自己的佣金
- **BREAKING**: 现有全局佣金数据需要迁移归属到 admin 用户

### 订阅等级功能门控
- 新增 Excel 导入导出的订阅等级限制（免费版/效率版/专业版禁用）
- 新增佣金类目管理的订阅等级限制（免费版/效率版禁用）
- 在后端 API 层和前端 UI 层同步实施门控

### 统计模块全面重建
- 前端 StatisticsPage 从硬编码假数据改为真实 API 调用
- 实现真实的月度留存率计算（基于 user_login_logs）
- 实现真实的月度收入统计（基于 payment_orders 按月分组）
- 修复活跃用户计算（基于 last_login，而非等于总用户数）
- 修复活跃趋势为真实对比（今日 vs 昨日、本周 vs 上周）
- 修复登录日志字段映射（username 返回用户名而非 ID、action 显示操作类型、status 返回真实状态）
- 修复操作日志 admin 字段（返回用户名而非数字 ID）
- 实现搜索、导出、分页等交互功能
- 删除"异常监控" Tab
- 删除 5 个未使用且有逻辑错误的后端端点（funnel、user-groups、growth、feature-usage、plan-analysis）

## Capabilities

### New Capabilities
- `commission-user-isolation`: 佣金类目从全局数据改造为用户级隔离数据，包括模型变更、CRUD 过滤、API 权限调整、数据迁移
- `subscription-feature-gating`: 基于订阅等级的功能门控机制，控制 Excel 导入导出和佣金类目管理的访问权限
- `statistics-overhaul`: 统计模块全面重建，包括前端真实 API 集成、后端查询逻辑修复、搜索/导出/分页实现、无用端点清理

### Modified Capabilities
_(无现有 spec 需要修改)_

## Impact

### 后端代码
- `api/models/schemas.py` — PricingResultItem 增加 is_smart 字段
- `api/routes/pricing.py` — format_result() 传递 is_smart
- `pricing/final_price.py` — 定价公式调整确保利润率精确
- `pricing/profit.py` — 利润率反推逻辑
- `models/commission_category.py` — 新增 user_id 字段
- `db/commission_categories.py` — CRUD 增加用户过滤
- `api/routes/commission_categories.py` — 权限和过滤逻辑重构
- `pricing/commission.py` — 佣金获取增加用户上下文
- `api/routes/statistics.py` — 大规模重构（修复 6 个端点、删除 5 个端点）
- `db/statistics.py` — 新增留存/收入/活跃的真实查询函数
- `api/dependencies.py` — 可能需要新增订阅等级检查依赖

### 前端代码
- `frontend/src/components/charts/CostPieChart.jsx` — 百分比分母修正
- `frontend/src/pages/StatisticsPage.jsx` — 全面重写（mock 数据 → API 调用 + 搜索/导出/分页）
- `frontend/src/pages/CommissionCategoriesPage.jsx` — 移除 admin 限制，增加订阅等级门控
- `frontend/src/components/Sidebar.jsx` — 佣金类目菜单项的可见性逻辑

### 数据库
- Alembic 迁移：commission_categories 表新增 user_id 列 + 唯一约束变更
- 数据迁移：现有全局佣金数据归属到 admin 用户

### API 契约变更
- **BREAKING**: 佣金类目端点不再需要 admin 权限，改为用户级访问
- 统计端点删除 5 个（funnel、user-groups、growth、feature-usage、plan-analysis）
- 登录日志和操作日志的响应字段含义变更（username 从数字 ID 变为真实用户名）
