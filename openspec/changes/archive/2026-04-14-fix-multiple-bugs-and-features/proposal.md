## Why

系统存在多个功能缺陷影响核心业务流程：精准模式定价计算无结果显示、物流池管理操作失败（删除全部405错误）、Excel导入数据丢失（物流Smart识别不全、产品批量导入截断至10条）、物流详情弹窗样式与全站不一致。同时缺少前后端联合启动脚本，开发体验不佳。这些问题直接影响用户日常使用，需要立即修复。

## What Changes

- **精准模式定价结果不显示**：修复 `format_result()` 中 `suggested_price` 为0时被判定为不可用的逻辑（`not res.get("suggested_price")` 对0值为falsy），以及前端 `renderResult` 在grouped结果全部 `is_available=false` 时无回退显示逻辑
- **被淘汰物流出现不存在的物流名**：排查 "Tanais Standard Small" 为何出现在被淘汰物流中但不在用户物流列表 — 可能来自公共物流池数据混入计算流程，或是已删除物流的残留
- **公共物流池删除全部返回405**：`DELETE /api/logistics-pool/all` 路由已正确定义，需排查FastAPI路由注册顺序或前端请求路径问题
- **FBP Excel导入Smart物流识别不全**：`xlsx_import/parsers/fbp.py` 中 `is_smart` 判断仅检查 column C（service列）是否包含 "smart"，但Excel中Smart物流可能在其他列或使用不同格式标注
- **物流池详情弹窗样式不一致**：`LogisticsPoolPage.jsx` 中的 Dialog 使用了 `bg-slate-50/50`、`border-slate-200/60` 等硬编码颜色，与全站 shadcn/ui dark theme（globals.css 中定义的 HSL 变量）不一致
- **批量产品导入仅导入10条**：`api/routes/products.py` 的 preview 端点仅返回前10行（`rows[1:11]`），confirm 端点只处理前端发送的预览行数据，导致184条数据被截断
- **"货币"字段说明**：产品导入中的货币字段映射到product的currency属性，用于定价时的汇率换算
- **前后端联合启动脚本**：创建开发环境一键启动脚本，同时启动 FastAPI 后端和 Vite 前端
- **全面测试覆盖**：为所有修复添加单元测试、集成测试和E2E测试

## Capabilities

### New Capabilities
- `dev-startup-script`: 创建前后端联合启动脚本（PowerShell/BAT），同时启动 uvicorn 和 vite dev server
- `pricing-result-display-fix`: 修复精准模式定价计算结果显示逻辑（后端 format_result 和前端 renderResult）
- `logistics-pool-delete-all-fix`: 修复公共物流池删除全部的405错误
- `fbp-smart-detection-fix`: 修复FBP Excel导入中Smart物流识别逻辑
- `product-batch-import-fix`: 修复批量产品导入截断问题，支持导入全部行
- `logistics-pool-detail-style`: 物流池详情弹窗样式统一至全站主题
- `phantom-logistics-fix`: 修复被淘汰物流中出现不存在物流名的问题
- `bug-fix-tests`: 为所有修复编写全面的测试（单元、集成、E2E）

### Modified Capabilities

## Impact

- **后端文件**：`api/routes/pricing.py`（format_result）、`api/routes/products.py`（preview/confirm）、`api/routes/logistics_pool.py`（delete路由）、`xlsx_import/parsers/fbp.py`（Smart检测）、`pricing/calculate_pricing.py`（物流过滤）
- **前端文件**：`frontend/src/pages/PricingPage.jsx`（结果渲染）、`frontend/src/pages/LogisticsPoolPage.jsx`（删除调用 + 详情弹窗样式）、`frontend/src/pages/ProductImportPage.jsx`（导入流程）
- **新增文件**：`start_dev.ps1` 或 `start_dev.bat`（联合启动脚本）
- **测试文件**：新增/修改 `tests/` 下的后端测试、`frontend/src/__tests__/` 下的前端测试、`frontend/tests/` 下的E2E测试
- **API行为变更**：`POST /api/products/import/preview` 将返回全部行而非仅前10行；`POST /api/products/import/confirm` 需支持大批量数据；定价API返回结果中 `is_available` 判断逻辑变更
