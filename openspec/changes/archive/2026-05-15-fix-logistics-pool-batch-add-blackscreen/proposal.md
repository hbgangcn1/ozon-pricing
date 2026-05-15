## Why

公共物流池"全选 → 全部添加到我的物流"导致整页黑屏（root 卸载）。Playwright 实测确认三层因果：(1) 后端 `BatchAddBody.ids` 当前 `max_length=50`，与已发布 spec `logistics-pool-batch-add` 第 16 行明文契约 "200 才返回 400 + `单次最多添加 200 条`" 矛盾，前端 `BATCH_SIZE=200` 必然触发 422；(2) 前端 catch 直接把 422 的 Pydantic `detail` 数组传给 `toast.error()`，sonner 渲染对象时 React 抛 "Objects are not valid as a React child"；(3) `<Toaster>` 在 `App.jsx` L85 渲染，位于 `<ErrorBoundary>` 兄弟节点之外，崩溃逃出兜底 → 整树卸载 → 黑屏。生产用户复现率 100%（任何选超 50 条就炸）。

## What Changes

- **后端**：把 `BatchAddBody.ids: List[int] = Field(..., max_length=50)` 改为 `Field(..., max_length=200)`，对齐已发布 spec 与前端实际批大小。
- **后端**：route 入口显式校验 `len(body.ids) == 0` → 400 `"ids 不能为空"`、`len(body.ids) > 200` → 400 `"单次最多添加 200 条"`（spec 已要求，目前依赖 Pydantic 422 是契约违反）。
- **前端**：新增共享工具 `src/lib/api-error.js` 导出 `getApiErrorMessage(error, fallback)`，归一化 axios 错误：(a) `detail` 是字符串 → 直接返回；(b) `detail` 是 FastAPI 422 数组 → 取首条 `msg` 或拼接；(c) 其他 → fallback。
- **前端**：所有 `toast.error(error?.response?.data?.detail || ...)` 调用切换到 `toast.error(getApiErrorMessage(error, ...))`。先做 `LogisticsPoolPage.jsx`，再扫全仓批量替换。
- **前端**：在 `App.jsx` 把 `<Toaster>` 移入 `<ErrorBoundary>` 内部（或单独包一层 boundary）——toast 渲染异常永不卸载根节点。
- **前端**：`handleBatchAddToMyLogistics` 跨批 quota 语义遵循 Oracle 决策 A（部分成功）：某批 403 立即停止后续批次，toast `"已添加 X 条，剩余 Y 条因物流规则上限未添加"`；任意结局都调 `fetchLogistics()` 刷新；选择态保留未发送+失败批次 ids。
- **前端**：每批必须依赖后端 `_check_logistics_limit` 重检（已存在 `pg_advisory_xact_lock(user_id)`），前端无需做额外预检。
- **测试**：Vitest 覆盖批量路径（200 分批顺序、422 数组 detail 不传对象给 toast、403 中止 + 部分成功 toast 文本、成功后调 fetchLogistics）。

**BREAKING**: 无（前端契约已 200，后端放宽兼容；422 用户原本就拿不到任何成功响应）。

## Capabilities

### New Capabilities
- `frontend-error-resilience`: 跨页面共享的 axios 错误归一化工具 + Toaster 容错拓扑要求，防止 toast 渲染崩溃卸载根节点。

### Modified Capabilities
- `logistics-pool-batch-add`: 后端 `BatchAddBody.ids` `max_length` 从隐含 50 显式改为 200，并补显式 400 校验；新增"分批 quota 部分成功"前端契约（每批独立、403 中止、聚合 toast）。

## Impact

- **代码**：
  - `api/routes/logistics_pool.py` L103-104（schema）、L242-299（显式长度校验早 return 400）。
  - `frontend/src/pages/LogisticsPoolPage.jsx` L155-193。
  - `frontend/src/App.jsx` L85（Toaster 位置）。
  - 新增 `frontend/src/lib/api-error.js` + 单元测试。
  - 新增 `frontend/src/__tests__/LogisticsPoolPage.batch.test.jsx`（或扩 existing）。
- **API 行为**：批 ids ≤200 不再 422；51-200 不再被拒。
- **UX**：408 行全选 = 3 批 RTT；额度不足时清晰中止+提示。
- **依赖**：无新依赖。
- **风险**：现有调用方（仅 `LogisticsPoolPage`）若依赖 422 拒 51+ 的副作用——审阅确认无。
