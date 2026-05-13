## Why

公共物流池页面（`/logistics-pool`）打开时无条件弹出 "获取物流池数据失败" 的错误提示，无论池为空还是有数据都触发。根因不是池为空，而是前端写死 `limit:1000` 但后端 `GET /api/logistics-pool` 用 `Query(limit, ge=1, le=200)`，所有打开此页的请求都会被 FastAPI 校验拒成 422。物流池数据已 408 行（超过 200 上限）且会持续增长，意味着这个 bug 一直存在且会越来越频繁触发。

## What Changes

- 后端 `GET /api/logistics-pool` 的 `limit` 上限从 200 提到 1000（容纳当前 408 + 未来增长），承认这是临时方案。
- 前端 `LogisticsPoolPage.jsx` 合并 `useEffect` 内联加载逻辑与 `fetchLogistics` 回调（消除"完全相同请求写两遍"的 AI slop），统一保留 AbortController 竞态保护。
- 前端删除死代码 `if (error?.response?.status !== 404)` 错误豁免——`GET /api/logistics-pool` 列表端点正常情况只返 200（空数据返回 `{items:[], total:0}`），404 豁免会掩盖未来真正的路由配错或鉴权错。
- 测试：后端新增 limit=1000 应返 200 的契约测试；前端更新空池场景下不应弹 toast.error 的断言。

## Capabilities

### New Capabilities
- `logistics-pool-list`: 公共物流池列表端点 `GET /api/logistics-pool` 的契约（分页参数边界、空池行为、错误码语义）以及对应的前端页面加载行为契约（不允许在 200 OK 响应路径上弹错误 toast）。

### Modified Capabilities
（无——本次涉及的列表端点与前端加载行为此前未被任何现存 spec 覆盖。`logistics-pool-batch-add` 只覆盖 `POST /batch-add-to-my-logistics`，范围不重叠。）

## Impact

- **后端**：`api/routes/logistics_pool.py` 第 113 行 `limit: int = Query(100, ge=1, le=200)` → `le=1000`。
- **前端**：`frontend/src/pages/LogisticsPoolPage.jsx` 第 63-98 行（合并加载路径，删除 404 豁免）。`frontend/src/__tests__/LogisticsPoolPage.test.jsx` 第 153 行附近测试用例同步更新。
- **测试**：后端 `tests/test_api_logistics_pool.py`（如不存在则新建）增 limit=1000 → 200 的契约测试。
- **未来工作（本次不实现，仅登记）**：物流池真分页/无限滚动。本次将上限提到 1000 是延期付款，物流池涨到 1500 时同样 bug 会复活，下一次扩容前必须做基于 offset/cursor 的真分页。
