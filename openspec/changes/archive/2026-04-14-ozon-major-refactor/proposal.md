## Why

当前系统的佣金为固定值、物流规则缺乏FBP/rFBS区分和目的地维度、定价结果无分组展示，导致系统无法准确计算发往俄罗斯及独联体国家（KZ、BY）的跨境电商定价，严重制约了Ozon卖家的实际使用场景。随着Ozon平台规则复杂化（多履约方式、多目的地、多佣金层级），现有架构已不能满足需求。

## What Changes

- **佣金体系改造**：固定佣金率 → 按类目分层级佣金（3个价格层级，rFBS=FBP+1%）；精准模式新增类目下拉选择；新增佣金类目管理页面（增删改）
- **物流履约方式扩展**：所有物流记录新增 `fulfillment_type`（rfbs/fbp）、`destination`（目的地国家代码）、`fbp_service_level`、`fbp_company`、`is_smart` 字段；取消自提/送货上门区分
- **物流批量导入与物流池**：Admin 可批量导入4种xlsx格式，系统自动解析所有字段；用户从全局物流池选择并管理自己的物流规则
- **定价计算结果分组展示**：结果按 rFBS-Russia、rFBS-各独联体国家（KZ/BY/KGZ/UZ/GE/AZ）、FBP-仅Russia、FBP-Russia+CIS 分Tab页展示；保留陆运/空运区分
- **产品批量导入**：上传xlsx，用户列映射到产品字段，自动数据清洗，重复产品手动处理
- **订阅管理功能增强**：Admin 可调整用户订阅时长、当日剩余计算次数、用户类型

## Capabilities

### New Capabilities

- `commission-categories`: 佣金类目管理 — 维护类目列表及各类目在3个价格层级（≤1500/1500-5000/>5000卢布）下的FBP佣金率；rFBS佣金率 = FBP + 1%，不单独存储
- `logistics-fulfillment`: 物流履约类型扩展 — 为每条物流记录添加 fulfillment_type、destination、fbp_service_level、fbp_company、is_smart 字段；支持 rFBS（7个目的地国家）和 FBP（Russia/KZ/BY）
- `logistics-pool`: 物流池与批量导入 — Admin 批量导入4种xlsx格式到全局物流池（logistics_pool表），系统自动解析时效、尺寸、重量、称重方式等字段；用户从池中选择并管理个人物流规则
- `pricing-result-groups`: 定价结果分组展示 — 计算结果按 rFBS-Russia、rFBS-CIS各国、FBP-Russia、FBP-Russia+CIS 分Tab页展示，保留陆运/空运维度
- `product-bulk-import`: 产品批量导入 — 上传xlsx、列映射、数据自动清洗（字符串转数值）、重复产品手动选择处理方式
- `subscription-admin`: 订阅管理增强 — Admin 可调整用户订阅到期时间、当日剩余次数、用户类型（免费版/效率版/专业版/企业版/测试版/感谢版）

### Modified Capabilities

（无已有 spec 需要修改）

## Impact

**后端**：
- `models/logistics.py` — 新增5个字段（fulfillment_type, destination, fbp_service_level, fbp_company, is_smart）
- `models/product.py` — `commission_rate` 替换为 `commission_category_id`（外键）
- 新增 `models/commission_category.py` — CommissionCategory ORM 模型
- 新增 `models/logistics_pool.py` — LogisticsPool ORM 模型
- `db/logistics_crud.py` — 扩展以支持新字段
- 新增 `db/commission_categories.py`、`db/logistics_pool.py` CRUD 层
- `pricing/logistic_cost.py` — 按 fulfillment_type + destination 过滤物流方式
- `pricing/calculate_pricing.py` — 计算结果按分组返回
- `api/routes/logistics.py` — 新增物流池导入端点
- 新增 `api/routes/commission_categories.py` 路由
- `api/routes/admin.py` — 新增订阅管理端点（调整时长/次数/类型）
- Alembic 迁移：新增3张表，修改2张表
- xlsx 解析脚本（4种格式）

**前端**：
- `PricingPage.jsx` — 精准模式佣金改为类目下拉；结果区域改为Tab分组
- `LogisticsPage.jsx` — 新增 fulfillment_type/destination/fbp_service_level 字段展示与编辑
- 新增 `CommissionCategoriesPage.jsx` — 佣金类目管理页面
- 新增 `LogisticsPoolPage.jsx` — 物流池浏览与导入页面
- `UserManagementPage.jsx` — 新增订阅时长/次数/类型调整UI

**数据库**：
- 新增表：`commission_categories`、`logistics_pool`
- 修改表：`logistics`（+5列）、`products`（commission_rate→commission_category_id）
- Alembic 迁移文件
