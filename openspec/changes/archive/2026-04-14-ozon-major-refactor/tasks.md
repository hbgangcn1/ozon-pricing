## 1. 数据库迁移

- [x] 1.1 创建 `models/commission_category.py` — CommissionCategory ORM 模型（id, name, fbp_tier1_rate, fbp_tier2_rate, fbp_tier3_rate, is_active）
- [x] 1.2 创建 `models/logistics_pool.py` — LogisticsPool ORM 模型（与 logistics 字段集相同，额外含 source_file, imported_at, is_active，无 user_id）
- [x] 1.3 在 `models/logistics.py` 新增5个字段：fulfillment_type（默认'rfbs'）、destination（默认'RU'）、fbp_service_level（可空）、fbp_company（可空）、is_smart（默认0）
- [x] 1.4 在 `models/product.py` 新增 `commission_category_id`（Integer，可空，外键指向 commission_categories.id）
- [x] 1.5 在 `models/__init__.py` 注册新模型
- [x] 1.6 生成 Alembic 迁移文件并验证（`alembic revision --autogenerate -m "ozon-major-refactor"`）
- [x] 1.7 本地执行 `alembic upgrade head`，确认迁移成功，旧数据无损

## 2. 后端 CRUD 层

- [x] 2.1 创建 `db/commission_categories.py` — get_all、get_by_id、create、update、soft_delete CRUD 函数
- [x] 2.2 创建 `db/logistics_pool.py` — get_all（分页）、get_by_id、upsert（按 source_file+delivery_method+destination）、set_active CRUD 函数
- [x] 2.3 扩展 `db/logistics_crud.py` — 查询/创建/更新支持新5个字段；添加按 fulfillment_type 和 destination 过滤的查询函数
- [x] 2.4 扩展 `db/products.py` — 支持 commission_category_id 字段的读写；添加按名称查重函数（用于产品导入）
- [x] 2.5 在 `db/admin.py` 新增3个管理函数：extend_subscription(user_id, days)、adjust_calculations(user_id, delta)、set_user_type(user_id, user_type)

## 3. xlsx 批量导入解析器

- [x] 3.1 创建 `xlsx_import/` 包目录及 `__init__.py`
- [x] 3.2 创建 `xlsx_import/detector.py` — 自动识别4种格式（按 Sheet 名称关键词）
- [x] 3.3 创建 `xlsx_import/parsers/china_post.py` — 解析中国邮政 rFBS 格式（Sheet: Russia-China CP，行4起）
- [x] 3.4 创建 `xlsx_import/parsers/scoring_rfbs.py` — 解析评分 rFBS 格式（Sheet: CHINA rFBS，含向上填充逻辑，解析 `¥X + ¥Y/1 g` 费率格式）
- [x] 3.5 创建 `xlsx_import/parsers/cis_rfbs.py` — 解析 CIS rFBS 格式（Sheet: KZ & BY ENG + Other CIS，多国 destination）
- [x] 3.6 创建 `xlsx_import/parsers/fbp.py` — 解析 FBP 格式（Sheet: CHINA FBP，3PL/Service 列向上填充，Smart 识别，destination 从 E 列，fbp_service_level 从 Service 名称提取）
- [x] 3.7 创建 `xlsx_import/common.py` — 公共解析工具：时效解析（`"11-15"` → min/max_days）、费率解析（`¥X + ¥Y/1 g`）、VolumeWeight 系数解析（`L×W×H÷6000` → 6000）

## 4. API 路由层

- [ ] 4.1 创建 `api/routes/commission_categories.py` — GET /api/commission-categories（列表）、POST（创建，Admin）、PATCH /{id}（更新，Admin）、DELETE /{id}（软删除，Admin）
- [ ] 4.2 创建 `api/routes/logistics_pool.py` — GET /api/logistics-pool（列表，分页）、POST /api/logistics-pool/import（上传xlsx，Admin）、PATCH /{id}（set_active，Admin）、POST /{id}/add-to-my-logistics（用户添加到个人规则）
- [ ] 4.3 扩展 `api/routes/logistics.py` — 创建/更新请求 schema 支持5个新字段；添加 fulfillment_type 和 destination 查询参数过滤；验证 FBP Express/SuperExpress 不能发 CIS
- [ ] 4.4 扩展 `api/routes/admin.py` — 新增 POST /api/admin/users/{id}/subscription/extend、POST /api/admin/users/{id}/calculations/adjust、POST /api/admin/users/{id}/type 三个端点
- [ ] 4.5 扩展 `api/routes/products.py` — 新增 POST /api/products/import/preview（上传xlsx解析表头+预览）、POST /api/products/import/confirm（提交映射+冲突决策批量入库）
- [ ] 4.6 在 `api/main.py` 注册新路由（commission_categories_router、logistics_pool_router）
- [ ] 4.7 在 `api/models/schemas.py` 新增相关 Pydantic schemas（CommissionCategoryCreate/Update、LogisticsPoolItem、ProductImportPreview/Confirm 等）

## 5. 定价计算改造

- [ ] 5.1 扩展 `pricing/calculate_pricing.py` — 新函数 `calculate_pricing_grouped(product, all_logistics, mode, priority)` 接收全量物流列表，内部按4个分组分别调用现有 calculate_pricing，返回 `{rfbs_ru, rfbs_cis, fbp_ru, fbp_cis}` 字典
- [ ] 5.2 扩展 `pricing/logistic_cost.py` — 无需修改（物流成本计算不感知 fulfillment_type）
- [ ] 5.3 修改 `pricing/` 佣金计算部分 — 新增 `get_commission_rate(price_rub, category_id, fulfillment_type, db_session)` 函数，按 D1 设计从数据库查类目费率，rFBS 自动 +0.01
- [ ] 5.4 修改 `api/routes/pricing.py` — 调用 `calculate_pricing_grouped`，将4组结果返回给前端

## 6. 前端改造 — 核心页面

- [ ] 6.1 `PricingPage.jsx` — 精准模式佣金字段：将 commission_rate 输入框替换为 commission_category 下拉菜单（调用 GET /api/commission-categories），旁边添加"管理佣金类目"链接/按钮
- [ ] 6.2 `PricingPage.jsx` — 计算结果区域：将现有 best_land/best_air 展示改为4个 Tab（rFBS-俄罗斯、rFBS-独联体、FBP-仅俄罗斯、FBP-俄罗斯+CIS），各 Tab 内保留陆运/空运展示
- [ ] 6.3 `PricingPage.jsx` — Smart 标注：结果中 is_smart=1 的物流方式显示"Smart"醒目标签
- [ ] 6.4 `LogisticsPage.jsx` — 新增 fulfillment_type 选择器（rfbs/fbp）、destination 下拉（按 fulfillment_type 联动选项）、fbp_service_level 下拉（仅 fbp 时显示）、is_smart 显示（只读，从物流池导入时自动赋值）
- [ ] 6.5 `UserManagementPage.jsx` — 为每个用户新增"订阅管理"入口（弹窗或侧边面板），含到期时间调整、当日次数调整、用户类型下拉

## 7. 前端改造 — 新页面

- [ ] 7.1 创建 `CommissionCategoriesPage.jsx` — 佣金类目管理页面（Admin 专属）：表格展示所有类目（名称、Tier1/2/3费率）、新增/编辑弹窗、删除确认
- [ ] 7.2 创建 `LogisticsPoolPage.jsx` — 物流池页面：表格展示全量物流池条目（支持按 fulfillment_type/destination/fbp_service_level 筛选）、"导入xlsx"按钮（Admin）、"添加到我的物流"按钮（用户）
- [ ] 7.3 创建 `ProductImportPage.jsx`（或作为 ProductsPage 内的模态流程）— 上传xlsx → 列映射界面 → 预览+冲突处理 → 确认导入
- [ ] 7.4 在 `App.jsx` 注册新路由，在 `SideMenu.jsx` 添加"佣金管理"和"物流池"导航项（Admin 可见）

## 8. 后端测试

- [ ] 8.1 `tests/test_db_commission_categories.py` — commission_categories CRUD 测试（≥15个测试，含唯一名称校验）
- [ ] 8.2 `tests/test_db_logistics_pool.py` — logistics_pool CRUD + upsert 逻辑测试（≥15个测试）
- [ ] 8.3 `tests/test_xlsx_import.py` — 4种格式解析器测试，含费率/时效/Smart识别/destination解析（≥20个测试）
- [ ] 8.4 `tests/test_routes_commission_categories.py` — API 路由测试（≥10个测试，含权限校验）
- [ ] 8.5 `tests/test_routes_logistics_pool.py` — API 路由测试（≥10个测试，含 Admin 导入、用户添加）
- [ ] 8.6 `tests/test_pricing_grouped.py` — calculate_pricing_grouped 测试（≥15个测试，含4组各种物流组合）
- [ ] 8.7 `tests/test_routes_admin_subscription.py` — 3个新管理端点测试（≥10个测试，含权限、边界值）
- [ ] 8.8 `tests/test_routes_products_import.py` — 产品导入API测试（≥10个测试，含列映射、冲突处理）
- [ ] 8.9 全套件验证 — `python -m pytest --tb=short` 全部通过，flake8 零错误

## 9. 前端测试

- [ ] 9.1 `CommissionCategoriesPage.test.jsx` — 佣金类目页面测试（≥8个测试）
- [ ] 9.2 `LogisticsPoolPage.test.jsx` — 物流池页面测试（≥8个测试）
- [ ] 9.3 更新 `PricingPage.test.jsx` — 新增类目下拉和4 Tab 结果展示的测试（≥5个新增测试）
- [ ] 9.4 更新 `LogisticsPage.test.jsx` — 新增 fulfillment_type/destination 字段测试（≥5个新增测试）
- [ ] 9.5 更新 `UserManagementPage.test.jsx` — 新增订阅管理弹窗测试（≥5个新增测试）
- [ ] 9.6 全套件验证 — `npx vitest run` 全部通过，`npm run build` 成功
