## 1. 后端：`limit` 上限 200 → 1000

- [x] 1.1 修改 `api/routes/logistics_pool.py` 第 113 行：`limit: int = Query(100, ge=1, le=200)` → `limit: int = Query(100, ge=1, le=1000)`
- [x] 1.2 在 `api/routes/logistics_pool.py` 中给 `list_logistics_pool` 函数加一行 `# NOTE: le=1000 is a temporary ceiling; real pagination tracked in proposal "未来工作".` 注释，避免后人不知道为何放宽
- [x] 1.3 运行 `python -m flake8 api/routes/logistics_pool.py` 通过

## 2. 后端测试：`limit` 边界契约

- [x] 2.1 在 `tests/test_api_logistics_pool_limit.py` 末尾新增 `test_logistics_pool_list_accepts_limit_1000`，使用 `client` + `get_current_user_id` override，断言 `GET /api/logistics-pool?limit=1000` 返 200，且响应体 `limit == 1000`
- [x] 2.2 同文件新增 `test_logistics_pool_list_rejects_limit_1001`，断言 `GET /api/logistics-pool?limit=1001` 返 422 且错误指向 `limit` 字段
- [x] 2.3 同文件新增 `test_logistics_pool_list_empty_returns_200`，在空池场景下断言 `GET /api/logistics-pool` 返 200 + `{items:[], total:0, limit:100, offset:0}`，绝不返 404
- [x] 2.4 运行 `python -m pytest tests/test_api_logistics_pool_limit.py --tb=short` 全绿

## 3. 前端：合并 `fetchLogistics`，删除 404 豁免

- [x] 3.1 修改 `frontend/src/pages/LogisticsPoolPage.jsx` 第 63-98 行：把 `fetchLogistics` 重写为 `useCallback(async (signal) => { ... })`，签名接收可选 `AbortSignal`；内部所有 `setLogistics`/`setIsLoading` 调用都包 `if (!signal?.aborted)` 守卫；catch 分支用 `if (signal?.aborted || e?.name === 'CanceledError') return; toast.error('获取物流池数据失败')`
- [x] 3.2 同文件删除 `useEffect` 内联的 `loadLogistics` 异步函数定义，把 `useEffect` 简化为 `useEffect(() => { const c = new AbortController(); fetchLogistics(c.signal); return () => c.abort(); }, [fetchLogistics])`
- [x] 3.3 删除两处 `if (error?.response?.status !== 404)` 守卫——按 D3 决策，所有非取消错误都应弹 toast
- [x] 3.4 通读 `LogisticsPoolPage.jsx` 全文，确认所有 `fetchLogistics()` 调用点（`handleFileChange` 导入成功后、`handleDeleteAll` 删除全部后、批量添加成功后）仍然有效；这些调用点 **不传 signal**（设计如此）

## 4. 前端测试：空池 + 错误路径

- [x] 4.1 修改 `frontend/src/__tests__/LogisticsPoolPage.test.jsx` 第 153 行附近的测试：场景"`logisticsPoolAPI.getAll` resolves with `[]`" 时，断言 `toast.error` **从未被调用**（`expect(toast.error).not.toHaveBeenCalled()`）
- [x] 4.2 在同文件新增测试：`logisticsPoolAPI.getAll` resolves with `{items: [...mock 3 rows...], total: 3}` 时，断言 `toast.error` 不被调用，且页面渲染 3 行
- [x] 4.3 在同文件新增测试：`logisticsPoolAPI.getAll` rejects with `{response: {status: 500}}` 时，断言 `toast.error('获取物流池数据失败')` 被调用恰好一次
- [x] 4.4 在同文件新增测试：`logisticsPoolAPI.getAll` rejects with `{response: {status: 422, data: {detail: ...}}}` 时，断言 `toast.error('获取物流池数据失败')` 被调用恰好一次（保护未来回归）
- [x] 4.5 在同文件新增测试：`logisticsPoolAPI.getAll` rejects with `{name: 'CanceledError'}` 时，断言 `toast.error` **从未被调用**（验证取消静默路径）
- [x] 4.6 运行 `cd frontend; npm run test -- LogisticsPoolPage` 全绿

## 5. 前端 Lint

- [x] 5.1 运行 `cd frontend; npm run lint -- src/pages/LogisticsPoolPage.jsx src/__tests__/LogisticsPoolPage.test.jsx`（如项目配置 ESLint）通过；如未配置则跳过此项
- [x] 5.2 在编辑器 / IDE 中确认 `LogisticsPoolPage.jsx` 无 Pyright/Pylance 等价的 JS/TS 警告

## 6. 本地端到端 manual QA（agent 自验，不依赖用户）

- [x] 6.1 用 `scripts/start_backend_detached.ps1` + `scripts/start_frontend_detached.ps1` 启动本地服务（按 AGENTS.md 长程命令规则拆分 bash 调用）
- [x] 6.2 用 admin 账号（`.sisyphus/credentials.local.md`）登录拿 token，`Invoke-RestMethod` 调 `GET /api/logistics-pool?limit=1000` 验证 200 + 当前 408 行返回成功
- [x] 6.3 用 Playwright MCP 打开 `http://localhost:3001/logistics-pool`，登录 admin，截图首屏：**断言不弹 toast.error**，VirtualTable 正常渲染 408 行
- [x] 6.4 临时清空池（直接 SQL `TRUNCATE` 或调用 `DELETE /api/logistics-pool/all`），刷新页面，截图：**断言不弹 toast.error**，VirtualTable 显示空状态
- [x] 6.5 清空验证完毕后恢复池数据（从备份/快照），或留空（取决于本地是否有备份）。**注意：本步骤可能破坏本地开发数据，先确认或跳过本地清空验证，仅靠单元测试覆盖空池场景**
- [x] 6.6 stop 本地后端 + 前端

## 7. 全套回归

- [x] 7.1 `python -m flake8` 整库通过
- [x] 7.2 `python -m pytest --tb=short` 整库通过（至少不引入新失败；pre-existing 失败如有需在交付时声明）
- [x] 7.3 `cd frontend; npm run test` 整库通过

## 8. 提交 + 部署（仅在用户明确说"deploy"或"ship"时执行）

- [x] 8.1 `git add` 涉及的所有文件 + OpenSpec change 目录
- [x] 8.2 `git commit` 用单段中文消息描述 bugfix（用户明确要求才创建 commit）
- [x] 8.3 `git push origin main`（用户明确要求才 push）
- [x] 8.4 SSH 拉 + 后台跑 `deploy/deploy.sh` + 30s 后看 `/tmp/deploy.log`（按 AGENTS.md 部署流程，且仅在用户明确要求才执行）
- [x] 8.5 生产 manual QA：admin 登录 `https://www.cbprice.cn/logistics-pool`，验证不弹 toast，截图留证

## 9. OpenSpec 归档

- [x] 9.1 用户验收通过后，运行 `/opsx-archive fix-logistics-pool-empty-toast` 把 change 归档到 `openspec/changes/archive/`，把 delta spec 合并到 `openspec/specs/logistics-pool-list/spec.md`
