## Context

公共物流池页面 `/logistics-pool` 是 admin/企业用户管理全局物流规则的入口。当前架构：

```
┌────────────────────────┐         ┌────────────────────────┐
│ LogisticsPoolPage.jsx  │         │ api/routes/            │
│                        │         │   logistics_pool.py    │
│ useEffect → 拉一次       │         │                        │
│   limit:1000           │  GET    │ list_logistics_pool()  │
│                        │ ──────▶ │   limit: Query(100,    │
│ fetchLogistics() 也拉    │         │     ge=1, le=200)      │
│   limit:1000           │         │                        │
│   （手动操作后用）        │         │ → FastAPI 422 一律拒    │
└────────────────────────┘         └────────────────────────┘
       │                                    │
       │          422 Unprocessable         │
       │  ◀──────────────────────────────────
       │
       ▼
catch(e) {
  if (e?.response?.status !== 404)   ← 只豁免 404，422 漏网
     toast.error('获取物流池数据失败')
}
```

实测：
- `GET /api/logistics-pool?limit=1000` → 422
- `GET /api/logistics-pool?limit=200` → 200 `{items:[], total:0}`
- 当前物流池真实行数：408（已超过原上限 200）

约束：
- 物流池数据持续增长，不会缩
- 不能让"页面只能装下 200 条"成为隐性限制——admin 看不到完整池就无法管理
- 修复必须能立刻 ship，不能拖到等真分页方案落地

## Goals / Non-Goals

**Goals:**
- 让"打开公共物流池页面"这个核心动作不再无故弹错。
- 无论池为空还是有数据（408 / 999 / 1000 条），首屏加载在 200 OK 路径上不弹 toast.error。
- 真正的错误（5xx、网络断开、401/403 鉴权失败、400 业务错）仍然弹 toast.error。
- 消除 `useEffect` 与 `fetchLogistics` 重复请求逻辑，源代码单一来源。
- 删除死代码 `if (status !== 404)` 豁免分支。
- 留下书面提醒：1000 是临时上限，未来必须做真分页。

**Non-Goals:**
- 不做真分页/无限滚动（这是下一个 change 的事，登记在 proposal "未来工作"段）。
- 不动 `LogisticsPoolPage.jsx` 中其他业务逻辑（新增、批量添加、详情面板、删除全部等保持原貌）。
- 不动 `logistics-pool-batch-add` 已固化的批量添加 spec。
- 不收紧前端"limit 上限"的客户端校验——前端透明，由后端契约保证。

## Decisions

### D1: 后端 `limit` 上限改 200 → 1000，而不是改前端 limit 或做真分页

**选项对比：**

| 选项 | 改动 | 优点 | 缺点 |
|---|---|---|---|
| A. 前端 `limit:200` | 1 行 | 改动最小 | admin 看不到 408 条全量，业务上不可接受 |
| **B. 后端 `le=1000`** | 1 行 | 立刻能装下当前 408 + 一倍裕量 | 临时方案，1500 时复发 |
| C. 真分页 | 大改 | 永久解决 | 改 VirtualTable + 状态管理 + 后端分页协议，超出本次 bugfix 范围 |

**选 B**。用户已确认数据已 408 且会增长，A 直接出局。C 是大动作不在本次 scope，但必须在 proposal 留下"未来工作"标记，避免遗忘。1000 这个数字给出 ~2.5x 当前体量的裕量，按当前增长曲线足够支撑下一次真分页迭代落地前的窗口。

**副作用边界（已审视）：**
- 后端单查 1000 行：`get_all` 查询有 limit + offset，PostgreSQL 单表 1000 行 scan 可控（毫秒级）。
- payload 体积：单条物流规则 JSON 估算 ~500B，1000 条 ~500KB，单次 HTTP 可接受（gzip 后更小）。
- 前端：`VirtualTable` 已就位，渲染 1000 行不会卡。
- 首屏白屏：从拉数据到 setLogistics 期间用户面对 loading spinner（`isLoading=true`），非黑屏，可接受。

### D2: 前端合并 `useEffect` 与 `fetchLogistics`，保留 AbortController

**问题**：当前代码里这两段几乎完全相同：

```jsx
// L63-75 fetchLogistics —— 没有 AbortController
const fetchLogistics = useCallback(async () => {
  setIsLoading(true)
  try { ... await logisticsPoolAPI.getAll({ limit: 1000 }) ... }
  catch (error) { if (status !== 404) toast.error(...) }
  finally { setIsLoading(false) }
}, [])

// L77-98 useEffect 内联 loadLogistics —— 有 AbortController
useEffect(() => {
  const controller = new AbortController()
  const loadLogistics = async () => {
    setIsLoading(true)
    try { ... { signal: controller.signal } ... }
    catch (error) { if (!aborted && name !== 'CanceledError' && status !== 404) ... }
    finally { if (!aborted) setIsLoading(false) }
  }
  loadLogistics()
  return () => controller.abort()
}, [])
```

**两条路径风险不对称**：
- `useEffect` 路径有 abort 保护，避免页面快速卸载/重渲染时旧请求 setState 到已卸载组件。
- `fetchLogistics` 路径没有保护，被手动操作（导入成功、删除成功、批量添加成功）调用，理论上同样存在用户快速点击触发并发请求的风险。

**决策**：合并为单一 `fetchLogistics(signal?)`，签名接收可选 `AbortSignal`。`useEffect` 创建 controller 并传 signal；其他调用点不传 signal（操作后刷新通常是显式动作，不需要竞态保护，但代码上保留扩展点）。

```
┌────────────────────────────────────────────────────┐
│ 合并后形态                                          │
├────────────────────────────────────────────────────┤
│ const fetchLogistics = useCallback(                │
│   async (signal) => {                              │
│     setIsLoading(true)                             │
│     try {                                          │
│       const data = await logisticsPoolAPI          │
│         .getAll({ limit: 1000 }, { signal })       │
│       if (!signal?.aborted) setLogistics(...)      │
│     } catch (e) {                                  │
│       if (signal?.aborted) return                  │
│       if (e?.name === 'CanceledError') return      │
│       toast.error('获取物流池数据失败')              │
│     } finally {                                    │
│       if (!signal?.aborted) setIsLoading(false)    │
│     }                                              │
│   }, [])                                           │
│                                                    │
│ useEffect(() => {                                  │
│   const c = new AbortController()                  │
│   fetchLogistics(c.signal)                         │
│   return () => c.abort()                           │
│ }, [fetchLogistics])                               │
└────────────────────────────────────────────────────┘
```

**替代方案放弃**：完全去掉 AbortController 更简洁，但用户已选风格 ①（保留），尊重决策。

### D3: 删除 `if (error?.response?.status !== 404)` 豁免

**当前死代码**：两处 catch 都豁免 404。但 `GET /api/logistics-pool` 的实际行为：
- 路由确实注册（`api/routes/logistics_pool.py:107` `@router.get("")`），不会 404。
- 空池返回 200 + `{items:[], total:0}`（已实测）。
- 鉴权失败返 401，参数错返 422，业务错返 400。

**结论**：404 在正常运行中根本不会出现。豁免逻辑是死代码，存在反而**有害**：
- 未来如果有人把路由 prefix 改错（比如改成 `/api/logistics_pool` 下划线），404 会被静默吞掉，bug 无声无息。
- 未来如果有人把这个端点改成 RESTful 风格（按 ID 取详情，不存在返 404），同样会被静默掉。

**删除**。让所有非取消错误都正常弹 `toast.error('获取物流池数据失败')`。

### D4: 测试覆盖

新增 / 修改测试：

1. **后端**（`tests/test_api_logistics_pool.py`，已存在的话直接加用例）：
   - `test_list_limit_1000_ok`：`GET /api/logistics-pool?limit=1000` 返 200。
   - `test_list_limit_1001_rejected`：`GET /api/logistics-pool?limit=1001` 返 422（守住新上限边界）。
   - `test_list_empty_pool_returns_200`：池清空后调用返 200 + `{items:[], total:0}`，**不**返 404。

2. **前端**（`frontend/src/__tests__/LogisticsPoolPage.test.jsx`）：
   - 更新原 L153 附近的测试：mock 返回空数组时**不应**调用 `toast.error`。
   - 新增：mock 返回 422/500 时**应**调用 `toast.error`（保护错误处理路径不被无意中删掉）。
   - 不删任何已有覆盖率，仅扩。

## Risks / Trade-offs

| 风险 | 缓解 |
|---|---|
| **R1：1000 是延期付款，物流池涨到 1500 时同样 bug 复活** | proposal "未来工作"段已登记真分页/无限滚动 TODO；`design.md` D1 已标注边界。下一次扩容前必须做真分页，不再加 limit。|
| **R2：单次返 1000 行 JSON ~500KB，慢网络下首屏慢** | 接受。前端有 isLoading spinner，非黑屏。VirtualTable 渲染本身无压力。真分页会一并解决此问题。|
| **R3：删除 404 豁免后，万一未来真有人把这个端点改成 RESTful 详情风格（ID 不存在返 404）会出现误报** | 这正是预期行为——那种重构必然伴随完整调用方更新，正好需要这个 toast 暴露问题。|
| **R4：合并 fetchLogistics 时漏掉某个调用点导致行为回归** | tasks.md 列出所有调用点（`handleFileChange` 导入后、`handleDeleteAll` 删除全部后、批量添加成功后），逐个核对。前端测试覆盖空池场景，回归会被测试捕获。|
| **R5：后端 `le=1000` 改完忘了同步 `tests/`，CI 看不出区别** | tasks.md 强制要求新增 `test_list_limit_1000_ok` 与 `test_list_limit_1001_rejected`，测试本身就是上限契约的可执行文档。|

## Migration Plan

1. 后端 `le=200 → le=1000`（单行）+ pytest 新增 limit=1000/1001 契约测试。
2. 前端合并加载逻辑 + 删 404 豁免 + vitest 测试同步。
3. 本地 manual QA：admin 登录打开 `/logistics-pool`，验证不弹 toast。空池场景与 408 行场景都验。
4. 本地三件套：`python -m flake8`、`python -m pytest --tb=short`、`cd frontend && npm run test`。
5. commit + push + 生产部署走 `deploy/deploy.sh` 标准流程。
6. 生产 manual QA：admin 登录 cbprice.cn 打开物流池验证。

**回滚**：单提交，`git revert` 即可。如生产已部署，走 `deploy/rollback.sh pre-deploy-<timestamp>`。
