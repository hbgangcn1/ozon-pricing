# Tasks: bugfix-v4

## Group 1: 精准模式诊断日志

- [x] 1.1 在 `api/routes/pricing.py` 的 `/calculate` 和 `/calculate-grouped` 端点添加物流加载日志（记录加载数量和名称列表）
- [x] 1.2 在 `pricing/calculate_pricing.py` 的 `_run_filters` 结束后，当结果为空时输出 WARNING 日志（含过滤原因汇总）

## Group 2: 公共物流池修复

- [x] 2.1 修改 `frontend/src/pages/LogisticsPoolPage.jsx` 的 `fetchLogistics()`，传 `{ limit: 1000 }` 参数
- [x] 2.2 改善 `api/routes/logistics_pool.py` import 端点的错误处理：添加外层 try/except，记录日志，确保部分成功不丢失
- [x] 2.3 改善 `frontend/src/pages/LogisticsPoolPage.jsx` 的 `handleDeleteAll` 错误提示，显示后端具体错误信息
- [x] 2.4 改善 `api/routes/logistics_pool.py` delete 端点错误处理：添加 try/except，返回详细错误

## Group 3: 产品导入崩溃修复

- [x] 3.1 修改 `api/routes/products.py`：过滤 headers 中的空字符串，增强 `_safe_value` 处理 NaN/Inf/datetime
- [x] 3.2 修改 `frontend/src/pages/ProductImportPage.jsx`：防御性过滤空列名、预览表限制20列、行 key 用 index

## Group 4: 验证

- [x] 4.1 运行 `python -m flake8` 确认 clean（修改的4个文件全部通过；项目级别仅有根目录临时脚本的既有警告）
- [x] 4.2 运行 `python -m pytest --tb=short` 确认通过（1333 passed, 8 failed — 8个失败均为既有问题，与本次修改无关）
- [x] 4.3 运行前端 `npx vitest run` 确认通过（187 passed, 3 failed — 3个失败均在 CommissionCategoriesPage，与本次修改无关）
