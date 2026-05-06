## 1. 后端 API 层修改

- [ ] 1.1 修改 `api/routes/subscriptions.py` 中 `_to_plan_response` 的 features 分割逻辑：`features.split(",")` → `features.split("|")`，并对每个元素 `.strip()` 去除首尾空白
- [ ] 1.2 修改 `api/routes/subscriptions.py` 中 `create_plan_route` 的 features 合并逻辑：`",".join(data["features"])` → `"|".join(data["features"])`
- [ ] 1.3 修改 `api/routes/subscriptions.py` 中 `update_plan_route` 的 features 合并逻辑：`",".join(data["features"])` → `"|".join(data["features"])`

## 2. 前端方案管理页面修改

- [ ] 2.1 修改 `PlanManagementPage.jsx` 中 `PlanEditForm.handleSubmit` 的 features 分割逻辑：`formData.features.split(',')` → `formData.features.split('|')`
- [ ] 2.2 修改 `PlanManagementPage.jsx` 中 features textarea 的 placeholder 和 label 提示文字，从"用逗号分隔"改为"用 | 分隔"
- [ ] 2.3 修改 `PlanManagementPage.jsx` 中加载已有 plan 到编辑表单时，features 数组的 join 逻辑从逗号改为 `|`（确保编辑时 textarea 中显示 `|` 分隔的文本）

## 3. 测试验证

- [ ] 3.1 运行后端测试 `python -m pytest --tb=short` 确保全部通过
- [ ] 3.2 运行前端测试 `npm run test` 确保全部通过
- [ ] 3.3 本地启动验证：调用 `GET /api/subscriptions/plans` 确认 features 返回多元素数组

## 4. 生产部署

- [ ] 4.1 提交代码并推送到生产服务器（git push + git pull）
- [ ] 4.2 重启 Gunicorn 使后端变更生效
- [ ] 4.3 构建前端并上传 dist 到生产服务器（先清理旧 assets）
- [ ] 4.4 Playwright 验证生产环境订阅管理页面功能描述正确显示为多行带对号
