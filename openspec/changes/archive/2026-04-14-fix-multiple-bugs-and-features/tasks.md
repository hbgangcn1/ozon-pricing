## 1. 精准模式定价结果不显示修复

- [x] 1.1 修改 `api/routes/pricing.py` 第141行 `format_result()` 中的判断条件：将 `not res.get("suggested_price")` 改为 `res.get("suggested_price") is None`，使 `suggested_price=0` 的结果正确标记为 `is_available=True`
- [x] 1.2 检查前端 `frontend/src/pages/PricingPage.jsx` 中 `renderResult` 的 grouped 结果渲染逻辑，确保当存在 `is_available=true` 的结果时正确显示结果卡片
- [x] 1.3 编写后端单元测试：测试 `format_result()` 在 `suggested_price=0`、`None`、正数三种情况下的 `is_available` 返回值
- [x] 1.4 编写后端集成测试：通过 TestClient 发送精准模式定价请求，验证返回结果中包含 `is_available=true` 的组合

## 2. 被淘汰物流出现不存在物流名修复

- [x] 2.1 在运行环境中检查 `get_user_logistics()` 查询是否正确过滤 `is_active=1`，确认 "Tanais Standard Small" 是否存在于用户物流表中
- [x] 2.2 检查 `pricing/calculate_pricing.py` 和 `pricing/cost_filter.py` 中物流过滤逻辑，确认被淘汰物流列表的数据来源是否仅为用户自有物流
- [x] 2.3 如发现数据来源问题（如公共物流池混入），修复物流数据获取逻辑
- [x] 2.4 编写单元测试：验证被淘汰物流列表中的每个物流名均存在于输入的用户物流列表中

## 3. 公共物流池删除全部405错误修复

- [x] 3.1 将 `api/routes/logistics_pool.py` 中 `@router.delete("/all")` 路由定义移到 `@router.patch("/{pool_id}")` 之前，确保静态路径 `/all` 优先于参数化路径 `/{pool_id}` 被匹配
- [x] 3.2 编写后端集成测试：通过 TestClient 发送 `DELETE /api/logistics-pool/all`，验证返回200和正确删除数量
- [x] 3.3 编写前端单元测试：验证 `logisticsPoolAPI.deleteAll()` 调用正确的 HTTP 方法和路径
- [x] 3.4 编写 Playwright E2E 测试：管理员登录 → 物流池页面 → 点击删除全部 → 验证操作成功

## 4. FBP Excel 导入 Smart 物流识别修复

- [x] 4.1 分析实际 Excel 文件 `FBP_List_of_services_5_03_26_1772704547.xlsx` 的数据结构，确认 Smart 物流在哪些列/行标注
- [x] 4.2 修改 `xlsx_import/parsers/fbp.py` 中 `is_smart` 检测逻辑：扩展到同时检查 service 列（column C）和 name 列（column G），以及 carry 机制传播的值
- [x] 4.3 验证修复后导入该 Excel 文件，Smart 物流识别数量从 3 增至 18
- [x] 4.4 编写单元测试：使用 mock Excel 数据测试 Smart 检测在 service 列、name 列、合并单元格三种场景下均正确

## 5. 批量产品导入截断修复

- [x] 5.1 修改 `api/routes/products.py` 的 `preview_product_import` 端点：移除 `rows[1:11]` 限制，返回全部行数据
- [x] 5.2 修改前端 `frontend/src/pages/ProductImportPage.jsx`：预览表格仍显示前 N 行，但在界面显示"共 M 条数据"总数提示，confirm 时发送全部行
- [x] 5.3 验证修复后导入 `定价与物流表不计抛.xlsx`，导入产品数量从 10 增至 184
- [x] 5.4 编写后端单元测试：测试 preview 端点返回 Excel 全部行
- [x] 5.5 编写后端集成测试：通过 TestClient 上传 Excel → preview → confirm 全流程
- [x] 5.6 编写 Playwright E2E 测试：上传 Excel → 预览显示总数 → 确认导入 → 验证产品列表数量

## 6. 物流池详情弹窗样式统一

- [x] 6.1 使用 impeccable audit 技能审计 `LogisticsPoolPage.jsx` 中 Dialog 组件的样式问题
- [x] 6.2 将硬编码 slate 颜色（`bg-slate-50/50`、`border-slate-200/60`、`bg-slate-50/80`）替换为 shadcn/ui CSS 变量（`bg-background`、`border-border`、`bg-card`、`bg-muted` 等）
- [x] 6.3 使用 impeccable polish 技能进行最终样式微调
- [x] 6.4 视觉验证：确认弹窗在 dark theme 下与全站风格一致

## 7. 前后端联合启动脚本

- [x] 7.1 创建 `start_dev.ps1` PowerShell 脚本：检查环境（.venv、Node.js）→ 激活虚拟环境 → 并行启动 uvicorn（port 8003）和 vite（port 3001）→ Ctrl+C 终止全部
- [x] 7.2 创建 `start_dev.bat` CMD 脚本：实现相同功能
- [x] 7.3 测试两个脚本的启动和终止流程
- [x] 7.4 更新 README.md 中的启动说明，添加新脚本用法

## 8. 移除产品导入中的"货币"字段

- [x] 8.1 从产品批量导入的前端预览界面中移除"货币"字段选项，因为所有价格均为人民币，无需选择货币

## 9. 全面测试验证

- [x] 9.1 运行全部后端测试 `python -m pytest tests/ --tb=short`：1349 passed, 11 failed（其中5个为预存 `TestGetAuditLogs` 失败，6个为预存 DB 约束冲突，均非本次改动引入）
- [x] 9.2 运行全部前端单元测试 `cd frontend && npm run test`：199 passed, 0 failed ✅
- [x] 9.3 运行 Playwright E2E 测试 `cd frontend && npm run test:e2e`：288 tests, 287 passed, 1 skipped, 0 failed ✅
- [x] 9.4 运行 flake8 检查 `python -m flake8`：核心代码无 lint 错误（仅项目根目录临时脚本 fix_*.py 等有风格警告，非核心代码）
