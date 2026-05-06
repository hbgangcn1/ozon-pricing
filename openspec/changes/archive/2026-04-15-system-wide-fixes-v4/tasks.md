# 任务清单 (system-wide-fixes-v4)

## 1. 定价引擎修复 (Smart标注与显示)

- [x] 1.1 修改 `api/models/schemas.py`: 在 `PricingResultItem` 中添加 `is_smart: int = 0` 字段
- [x] 1.2 修改 `api/routes/pricing.py`: 优化 `format_result()` 函数，确保从 `best_log` 中正确提取并返回 `is_smart` 状态
- [x] 1.3 修改 `frontend/src/components/charts/CostPieChart.jsx`: 将饼图计算的分母从 `totalCost` 修正为 `totalPrice`
- [x] 1.4 修改 `pricing/final_price.py`: 调整定价计算公式，确保反推利润率严格等于用户设定的目标值

## 2. 佣金类目用户隔离 (后端)

- [x] 2.1 修改 `models/commission_category.py`: 为 `CommissionCategory` 模型添加 `user_id` 字段，并建立 `(user_id, name)` 的唯一性约束
- [x] 2.2 修改 `db/commission_categories.py`: 更新所有 CRUD 函数（创建、查询、更新、删除），注入 `user_id` 过滤逻辑
- [x] 2.3 修改 `api/routes/commission_categories.py`: 将 `require_admin` 限制更改为 `get_current_user_id`，允许普通用户管理自己的类目
- [x] 2.4 修改 `pricing/commission.py`: 在获取佣金配置的逻辑中加入当前用户的上下文（user_id）
- [x] 2.5 创建 Alembic 迁移脚本: 添加 `user_id` 列，执行数据迁移（将现有存量数据默认归属于 admin 用户）

## 3. 佣金类目用户隔离 (前端)

- [x] 3.1 修改 `frontend/src/pages/CommissionCategoriesPage.jsx`: 调整权限检查逻辑，允许非管理员用户访问并管理其私有佣金类目
- [x] 3.2 更新前端菜单组件: 确保普通用户在侧边栏中能看到“佣金类目管理”入口

## 4. 订阅等级门控 (权限控制)

- [x] 4.1 后端权限拦截: 在 `api/routes/commission_categories.py` 添加订阅检查，限制免费版/效率版用户使用该功能
- [x] 4.2 Excel 导入导出限制: 在相关 API 中添加权限校验，仅允许企业版 (Enterprise+) 使用 Excel 导入导出功能
- [x] 4.3 前端 UI 门控: 在佣金管理页面和 Excel 导入导出按钮上添加锁定提示或条件渲染，引导低等级用户升级订阅

## 5. 统计模块清理与基础建设

- [x] 5.1 后端端点清理: 删除 `api/routes/statistics.py` 中未使用的端点（funnel, user-groups, growth, feature-usage, plan-analysis）
- [x] 5.2 前端页面清理: 从 `StatisticsPage` 中移除"异常监控" Tab 页
- [x] 5.3 统计模块架构调整: 统一统计模块的 API 调用入口，废弃 mock 数据

## 6. 统计模块后端 API 修复

- [x] 6.1 修复总览 (Overview) API: 对接真实数据库查询，并修复活跃用户统计逻辑
- [x] 6.2 修复留存分析 API: 基于 `user_login_logs` 表新建月度留存查询算法
- [x] 6.3 修复用户活跃 API: 修正趋势计算逻辑，实现“今日 vs 昨日”的真实数据对比
- [x] 6.4 修复充值与收入 API: 优化月度分组统计逻辑，确保收入报表准确

## 7. 统计模块前端集成与交互

- [x] 7.1 前端页面对接: 将 `StatisticsPage` 的 6 个核心 Tab（总览、留存、活跃、收入、操作日志、登录记录）全部切换为真实 API
- [x] 7.2 强化管理日志功能: 修正 `admin-logs` 和 `login-logs` 的字段映射，确保用户名正确显示
- [x] 7.3 实现交互增强: 为操作日志和登录记录添加搜索、日期筛选、导出 Excel 以及服务器端分页功能

## 8. 质量保证与回归测试

- [x] 8.1 编写后端测试: 针对佣金隔离和订阅门控编写 pytest 测试用例，确保权限控制无漏洞
- [x] 8.2 编写前端测试: 更新 vitest 用例，验证统计图表和权限提示的渲染逻辑
- [x] 8.3 运行全量测试: 执行 `python -m pytest` 和 `npm test`，确保全量测试通过
- [x] 8.4 代码规范检查: 运行 `flake8` 检查并修复所有 Python 代码风格问题
