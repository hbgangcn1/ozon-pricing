## 1. 后端 API 层修改

- [x] 1.1 修改 `api/routes/subscriptions.py` 中 `_to_plan_response` 的 features 分割逻辑：`features.split(",")` → `features.split("|")`，并对每个元素 `.strip()` 去除首尾空白
- [x] 1.2 修改 `api/routes/subscriptions.py` 中 `create_plan_route` 的 features 合并逻辑：`",".join(data["features"])` → `"|".join(data["features"])`
- [x] 1.3 修改 `api/routes/subscriptions.py` 中 `update_plan_route` 的 features 合并逻辑：`",".join(data["features"])` → `"|".join(data["features"])`

## 2. 前端方案管理页面修改

- [x] 2.1 修改 `PlanManagementPage.jsx` 中 `PlanEditForm.handleSubmit` 的 features 分割逻辑：`formData.features.split(',')` → `formData.features.split('|')`
- [x] 2.2 修改 `PlanManagementPage.jsx` 中 features textarea 的 placeholder 和 label 提示文字，从"用逗号分隔"改为"用 | 分隔"
- [x] 2.3 修改 `PlanManagementPage.jsx` 中加载已有 plan 到编辑表单时，features 数组的 join 逻辑从逗号改为 `|`（确保编辑时 textarea 中显示 `|` 分隔的文本）

## 3. 测试验证

- [x] 3.1 运行后端测试 `python -m pytest --tb=short` 确保全部通过
- [x] 3.2 运行前端测试 `npm run test` 确保全部通过
- [x] 3.3 本地启动验证：调用 `GET /api/subscriptions/plans` 确认 features 返回多元素数组

## 4. 生产部署

- [x] 4.1 提交代码并推送到生产服务器（git push + git pull）
- [x] 4.2 重启 Gunicorn 使后端变更生效
- [x] 4.3 构建前端并上传 dist 到生产服务器（先清理旧 assets）
- [x] 4.4 Playwright 验证生产环境订阅管理页面功能描述正确显示为多行带对号

---

## QA 证据

- 代码改动早已合入：commit `82c7fa01` "fix: use pipe separator for plan features instead of comma"（后端 + 前端一并完成）
- 后端：`api/routes/subscriptions.py:95` `features.split("|")` ✅、`:174,193` `"|".join()` ✅
- 前端：`PlanManagementPage.jsx:129` `join('|')`、`:161` `split('|')`、`:365` Label "（用 | 分隔）" ✅
- 测试：scoped pytest 132 passed (test_plan_api + test_db_plans + test_db_subscriptions, 30.38s)；vitest PlanManagementPage 7/7 passed
- 生产 API：`GET https://www.cbprice.cn/api/subscriptions/plans` 返回 4 plans，`features` 全部为多元素数组（free 3 项、efficiency 3 项、professional 5 项、enterprise 8 项）
- 生产 UI：Playwright 访问 `https://www.cbprice.cn/subscription` 验证 `pipeLinesCount: 0`（无任何 `|` 显示），4 张 plan 卡片 features 全部多行展开 → 截图 `pipe-separator-prod-verified.png`
