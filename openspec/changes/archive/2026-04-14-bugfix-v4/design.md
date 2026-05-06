# Design: bugfix-v4

## Bug 1: 精准模式调试 — 添加诊断日志

### 问题
用户的所有物流在精准模式中被过滤掉，且出现未知物流"Tanais Standard Small"。这是数据相关问题，需要可观测性来定位。

### 方案
1. **`api/routes/pricing.py`** — 在 `/calculate-grouped` 端点中，加载用户物流后记录日志：加载了多少条物流、各物流名称
2. **`pricing/calculate_pricing.py`** — 在 `_run_filters` 中，当所有物流被过滤掉时记录 WARNING 日志，包含过滤原因汇总
3. **不修改计算逻辑** — 这是数据问题，不是代码 bug

### 影响范围
- `api/routes/pricing.py`: 添加 2-3 行日志
- `pricing/calculate_pricing.py`: 添加 3-5 行日志

---

## Bug 2.1: 公共物流池只显示100条 — 分页

### 问题
前端 `fetchLogistics()` 不传 limit/offset 参数，后端默认 `limit=100`。

### 方案
1. **前端 `LogisticsPoolPage.jsx`**:
   - 前端调用 `getAll()` 时传 `limit=1000`（物流池通常不超过几百条，全量加载合理）
   - 在 `fetchLogistics()` 中传递 `{ limit: 1000 }`
   - 后端已支持 `limit` 最大 1000

### 影响范围
- `frontend/src/pages/LogisticsPoolPage.jsx`: 修改 1 行（fetchLogistics 参数）

---

## Bug 2.2: 3个xlsx导入 Internal Server Error — 错误处理

### 问题
本地测试确认解析（parse_file）正常工作。导入失败发生在 DB 插入阶段（insert_row）。当前代码对单行插入失败只做了 try/catch 计数，但如果发生全局异常（如 session 级错误），整个 endpoint 会抛 500。

### 方案
1. **`api/routes/logistics_pool.py`** — import 端点添加外层 try/catch，捕获 DB 级异常并返回有意义的错误信息
2. 添加日志记录具体失败原因
3. 确保每行插入后 flush 错误被正确捕获（当前已有 per-row try/catch）

### 影响范围
- `api/routes/logistics_pool.py`: import 端点添加更好的异常处理

---

## Bug 2.3: 删除全部失败 — 错误诊断

### 问题
前端 `handleDeleteAll` catch 块统一显示"删除失败"，没有显示后端返回的具体错误信息。

### 方案
1. **前端 `LogisticsPoolPage.jsx`** — 在 catch 中提取并显示后端错误详情：`error?.response?.data?.detail`
2. **后端 `api/routes/logistics_pool.py`** — delete 端点添加 try/catch 包裹 `delete_all` 调用，捕获 DB 异常并返回 HTTP 500 + 具体错误信息

### 影响范围
- `frontend/src/pages/LogisticsPoolPage.jsx`: 修改 1 行（error toast）
- `api/routes/logistics_pool.py`: 添加 3-5 行异常处理

---

## Bug 3: 产品导入页面崩溃 — 过滤空列名

### 问题
- xlsx 有 144 列，最后一列列名为 None → 后端转为空字符串 `""`
- 空字符串作为 Radix UI `<SelectItem value="">` 导致组件内部错误
- 143 列全部渲染在 Select 和预览表中

### 方案

**后端 `api/routes/products.py`**:
1. 过滤空列名：`headers = [h for h in headers if h]`（排除空字符串）
2. `_safe_value` 增强：对 `float('nan')` 和 `float('inf')` 返回 `None`，对 datetime 对象返回 ISO 格式字符串

**前端 `ProductImportPage.jsx`**:
1. 添加防御性检查：过滤空列名 `columns.filter(c => c && c.trim())`
2. 预览表只显示前 20 列（避免 144 列撑爆页面），加提示文字

### 影响范围
- `api/routes/products.py`: 修改 headers 过滤 + _safe_value 增强（~5 行）
- `frontend/src/pages/ProductImportPage.jsx`: 防御性过滤 + 预览列限制（~8 行）
