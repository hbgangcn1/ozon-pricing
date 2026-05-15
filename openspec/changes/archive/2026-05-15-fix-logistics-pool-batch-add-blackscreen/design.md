## Context

`/logistics-pool` 页"全部添加到我的物流"按钮触发后端 422，前端崩溃卸载整棵 React root，用户看到纯黑屏。Playwright 实测三层因果链已闭合：
- 前端 `BATCH_SIZE=200` × 后端 `Field(...,max_length=50)` → 必然 422。
- FastAPI 422 `detail` 是 `[{type, loc, msg, input, ctx}, ...]`；前端 `toast.error(detail)` 把对象数组传 sonner → React Error #31。
- `<Toaster>` 在 `App.jsx` L85 渲染，**位于** `<ErrorBoundary>` (L91) **之外**，崩溃逃出兜底。

已发布 spec `logistics-pool-batch-add` line 16 明文规定 ">200 才返回 400 + `单次最多添加 200 条`"——即后端实现是 spec drift，spec 才是契约权威。Oracle (会话 `ses_1df3c78d6ffeeiGvYsuRAkFOdh`) 双轮咨询确认：
- batch size 路径选 **B**（后端放宽到 200，前端保持 200/批，408 行 = 3 批）。
- 跨批 quota 语义选 **A**（部分成功，403 即停，聚合 toast，统一 fetchLogistics）。

## Goals / Non-Goals

**Goals:**
- 修复黑屏：任何 API 错误（含 422 数组 detail）都不能卸载 React root。
- 对齐契约：后端 schema、route 校验、前端 BATCH_SIZE、capability spec 四者一致到 200。
- 跨批 quota 语义清晰：用户能看到"成功 X 条 / 因额度未添加 Y 条"。
- 提供共享 `getApiErrorMessage` 工具，根除全仓 toast 对象渲染隐患。

**Non-Goals:**
- 不引入后台任务/队列/聚合接口（200 inserts 远低于该量级）。
- 不改 quota 业务规则（仍走 `_check_logistics_limit` + advisory lock）。
- 不实现 undo / 跨批原子事务（spec 已定义"单请求原子、跨请求独立"边界）。
- 不在 loop 内逐行 re-check quota（破坏请求级原子语义且增锁开销）。
- 不重写 `LogisticsPoolPage` 选择态架构（仅微调以保留未成功 ids）。

## Decisions

### 1. Batch size 选 200（不是 50）
- **选择**：后端 `max_length=50` → `max_length=200`，前端 `BATCH_SIZE=200` 不动。
- **替代**：50/批（9 批）、单次 1000（单事务长锁）。
- **理由**：(a) spec 已写 200，反向修 spec 是退步；(b) 50 制造 9 倍 RTT 与 quota 分批面；(c) 200 inserts × SAVEPOINT 在 PostgreSQL 不构成实际内存压力，已用 `_check_logistics_limit` advisory lock 兜底竞态。

### 2. 显式 400 校验，不依赖 Pydantic 422
- **选择**：handler 入口 `if len(body.ids) == 0: 400`、`if len(body.ids) > 200: 400 "单次最多添加 200 条"`。Schema `max_length=200` 仅做兜底防御。
- **替代**：纯依赖 Pydantic max_length → 422 数组。
- **理由**：spec line 16 显式 "intentionally NOT 422"；显式 400 + 字符串 detail 既符合契约又避免数组 detail 灾难复发。

### 3. 跨批 quota 语义：部分成功 + 403 即停
- **选择**：前端顺序发批；某批 403 → 立即停止后续批；聚合 toast `"已添加 X 条，剩余 Y 条因物流规则上限未添加"`；任意结局都 `fetchLogistics()`；选择态清掉成功批 ids，保留剩余。
- **替代**：原子 undo（高复杂度）、preview 接口（多一跳）、聚合 endpoint（最大改动）。
- **理由**：保持现有"单请求原子、跨请求独立"事务边界；不引入 undo/新接口；UI 透明告知用户结果；用户升级或清理后可重试剩余项。

### 4. 共享 `getApiErrorMessage` 工具
- **选择**：`frontend/src/lib/api-error.js` 导出纯函数：
  ```js
  export function getApiErrorMessage(error, fallback = '操作失败') {
    const detail = error?.response?.data?.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0];
      return typeof first?.msg === 'string' ? first.msg : fallback;
    }
    return fallback;
  }
  ```
- **替代**：在 `LogisticsPoolPage` 局部归一化（其他页面隐患不修）；axios interceptor 全局注入（侵入性强，破坏其他需要 raw error 的代码）。
- **理由**：纯函数易测、零副作用；本变更只强制改 `LogisticsPoolPage`，但工具就位为后续跨页面统一替换铺路。

### 5. `<Toaster>` 移入 `<ErrorBoundary>`
- **选择**：把 `App.jsx` L85 `<Toaster richColors position="top-right" />` 整块挪到 L91 `<ErrorBoundary>` 内的 `<Suspense>` 兄弟节点位置。
- **替代**：包独立 boundary、给 Toaster 加 try-catch（React 类组件 ErrorBoundary 才能捕子树渲染异常，try-catch 无效）。
- **理由**：ErrorBoundary 兜底 toast 渲染异常 → 显示降级 UI，而非整树卸载；现有 boundary 已实现"出错提示+重新加载"。Sibling-of-Suspense 不影响 Suspense 行为。

## Risks / Trade-offs

- **风险 R1**：把后端 max_length 从 50 → 200 可能让历史"客户端意外发 51-200 条" 从 422 变成 200 + 部分成功，行为变更对其他调用方不透明 → **缓解**：grep 确认 `batchAddToMyLogistics` 仅 `LogisticsPoolPage` 一处调用；OpenAPI 已 ≤200 契约。
- **风险 R2**：`<Toaster>` 移入 ErrorBoundary 后，若 boundary 自身渲染降级 UI 时调用 toast，可能死循环 → **缓解**：现有 ErrorBoundary 不调 toast，只渲染静态文本+按钮。
- **风险 R3**：跨批顺序发可能因网络抖动出现"批 1 成功、批 2 网络超时、批 3 又成功" → **缓解**：toast 文本区分"额度中止" vs "网络失败"；网络失败也立即停止后续批次，避免乱序写入。
- **风险 R4**：`getApiErrorMessage` 误判 nested object detail（少见非 422 错误）→ **缓解**：fallback 兜底；单元测试覆盖 string/array/null/undefined/object 五分支。
- **风险 R5**：本变更与活动变更 `fix-logistics-pool-empty-toast` 在 `LogisticsPoolPage.jsx` 同文件相邻区域 → **缓解**：本变更只改 L155-193 + 顶部 import；那个变更聚焦首屏 toast，区域不重叠；apply 时按字典序先做 `fix-logistics-pool-batch-add-blackscreen` 即可，否则后做者负责 rebase。

## Migration Plan

1. 后端先 deploy（`max_length` 放宽是向后兼容；显式 400 校验不破任何现有正确请求）。
2. 前端 deploy（依赖后端已放宽）。
3. 验证：admin 选 408 条 → 3 批全成功 → 列表刷新 → 无黑屏；额度不足账户 → toast 显示部分成功+中止数。
4. 回滚：仅前端可独立回滚（后端放宽不影响旧前端）；后端回滚需先回滚前端，否则前端再次 422。

## Open Questions

- 无（Oracle 双轮咨询已闭合；本变更范围与现有 `fix-logistics-pool-empty-toast` 不重叠）。
