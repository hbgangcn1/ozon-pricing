## 1. 物流规则编辑器 — 精度与电池字段

- [x] 1.1 在 `LogisticsPage.jsx` 中将 `price_limit_cny` 和 `price_min_cny` 的 Input 组件添加 `step="0.01"` 属性，并在 onBlur 时 `parseFloat(value).toFixed(2)` 强制 2 位小数
- [x] 1.2 在 `LogisticsPage.jsx` 中当 `allow_battery` 被勾选时，隐藏 `battery_capacity_limit_wh` 字段（条件渲染），并在提交时排除该字段

## 2. 产品编辑器 — 移除冗余字段

- [x] 2.1 在 `PricingPage.jsx` 精准模式区域（约 line 970-1023）移除 `battery_capacity_type` radio、`battery_wh`/`battery_mah`/`battery_v` 输入框、`has_msds` 复选框
- [x] 2.2 在 `PricingPage.jsx` 产品编辑弹窗（约 line 1208-1266）移除相同的电池详情字段和 MSDS 字段
- [x] 2.3 确保产品保存时不再发送 battery_capacity_type、battery_wh、battery_mah、battery_v、has_msds 字段

## 3. 公共物流池 — 查看详情

- [x] 3.1 在 `LogisticsPoolPage.jsx` 每条记录上添加"查看"按钮
- [x] 3.2 创建只读详情 Dialog 组件，展示物流规则所有字段（name, type, delivery_method, fulfillment_type, destination, min/max_days, 价格限制, 重量限制, 尺寸限制, 费用配置, 电池/液体, 体积模式, 优先组, Smart, fbp_service_level, fbp_company, source_file）

## 4. 物流池导入 — Bug 修复与追加模式

- [x] 4.1 在 `db/logistics_pool.py` 中新增 `insert_row` 函数（纯 INSERT，不做 upsert 匹配）
- [x] 4.2 修改 `api/routes/logistics_pool.py` 的 import endpoint，将 `upsert` 调用替换为 `insert_row`
- [x] 4.3 改进 `xlsx_import/detector.py` 的 `detect_format`：捕获失败时返回已找到的 sheet titles 列表和支持的格式关键词
- [x] 4.4 在 `api/routes/logistics_pool.py` import endpoint 中捕获 `ValueError`，返回 HTTP 400 + 结构化错误信息（含 sheet titles）

## 5. 物流池 — 删除全部

- [x] 5.1 在 `db/logistics_pool.py` 中新增 `delete_all` 函数（执行 `DELETE FROM logistics_pool`）
- [x] 5.2 在 `api/routes/logistics_pool.py` 中新增 `DELETE /api/logistics-pool/all` endpoint，admin-only
- [x] 5.3 在 `frontend/src/services/api.js` 中新增 `logisticsPoolAPI.deleteAll` 方法
- [x] 5.4 在 `LogisticsPoolPage.jsx` 中添加"删除全部"按钮（仅管理员可见），点击后弹二次确认对话框

## 6. 产品批量导入 — 崩溃修复

- [x] 6.1 在后端 product import 相关的 API route 中，对 `detect_format` 和 parser 调用包裹 try/except，返回结构化 HTTP 400 错误（后端已有 try/except，无需修改）
- [x] 6.2 在 `ProductImportPage.jsx` 中改进错误处理，捕获 API 返回的错误信息并展示，避免页面级崩溃（修复字段名不匹配：preview_rows, rows, conflict_action + 错误提示显示 API detail）
- [x] 6.3 使用 `定价与物流表不计抛.xlsx` 文件手动验证不再崩溃（字段名修复后前端不再崩溃）

## 7. 佣金管理 — rFBS 默认值

- [x] 7.1 创建 Alembic 迁移：在 `commission_category` 表中新增 `rfbs_tier1_rate`、`rfbs_tier2_rate`、`rfbs_tier3_rate` 字段，数据迁移 `rfbs = fbp + 1`
- [x] 7.2 修改 `models/commission_category.py` ORM 模型，新增 rfbs 字段
- [x] 7.3 修改 `api/routes/commission_categories.py`：`CategoryBody`/`CategoryPatch` schema 改为接收 rfbs 字段，`CategoryOut` 返回 rfbs + computed fbp
- [x] 7.4 修改 `db/commission_categories.py` CRUD 函数，存储 rfbs 字段
- [x] 7.5 修改 `CommissionCategoriesPage.jsx`：编辑表单改为 rFBS 输入，FBP 显示为只读（rfbs - 1%），添加说明文字

## 8. 计算结果页面 — 合并展示重构

- [x] 8.1 修改 `PricingPage.jsx` 的 `renderResult` 函数，移除独立的"价格优先方案"和"速度优先方案" section
- [x] 8.2 将价格/速度优先结果嵌入每个分组 tab 内部展示
- [x] 8.3 修改 `ResultCard` 组件标题格式为 `{物流名称} {Smart标志} {陆运/空运}`，移除"自提/送货上门"区分

## 9. rFBS-CIS 国家细分

- [x] 9.1 修改 `pricing/calculate_pricing.py` 的 `calculate_pricing_grouped`：将 `rfbs_cis` 拆分为 `rfbs_KZ`、`rfbs_BY`、`rfbs_KGZ`、`rfbs_UZ`、`rfbs_GE`、`rfbs_AZ` 六个独立计算
- [x] 9.2 修改前端 `PricingPage.jsx` 的 rFBS-独联体 tab，增加 6 个国家子 tab，每个子 tab 展示对应国家的计算结果
- [x] 9.3 处理某国家无匹配物流规则时的空状态显示

## 10. FBP 二次筛选逻辑

- [x] 10.1 新建 `pricing/fbp_secondary_filter.py` 模块：按 (fbp_company, fbp_service_level) 分组 → 每组取最高成本候选 → 候选集按用户优先级排序选最优
- [x] 10.2 在 `calculate_pricing_grouped` 的 `fbp_ru` 和 `fbp_cis` 结果上应用二次筛选
- [x] 10.3 确保筛选结果包含分组调试信息

## 11. 物流陆运/空运切换

- [x] 11.1 在 `api/routes/logistics.py` 中新增 `PATCH /api/logistics/{id}/toggle-transport` endpoint，切换 type 字段（land ↔ air）
- [x] 11.2 在 `frontend/src/services/api.js` 中新增 `logisticsAPI.toggleTransport(id)` 方法
- [x] 11.3 在 `LogisticsPage.jsx` 物流列表中每条记录添加条件按钮："转为空运"（陆运规则）/ "转为陆运"（空运规则），点击后调用 API 并刷新列表

## 12. 测试与验证

- [x] 12.1 运行后端 `python -m pytest --tb=short` 确保全部通过
- [x] 12.2 运行 `python -m flake8` 确保无 lint 错误
- [x] 12.3 运行前端 `npm run test` 确保前端测试通过
- [x] 12.4 手动验证 Alembic 迁移 `alembic upgrade head` 成功
