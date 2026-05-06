# Proposal: bugfix-v4

## 概述

修复 bugfix-and-polish-v3 完成后用户报告的 3 组遗留/新发现 bug。

## Bug 列表

### Bug 1: 精准模式"无可用方案" + 神秘物流 "Tanais Standard Small"

**用户描述**: 精准模式中，所有模式都显示"无可用方案"。被淘汰物流中出现了"Tanais Standard Small"，但用户的物流列表中并没有这条物流。

**根因分析**:
- 定价流程只使用用户物流（`db/logistics_crud.py` → `get_logistics_list`），不混入公共物流池。
- "Tanais Standard Small" 必定来自数据库中该用户的物流记录（可能是之前通过公共物流池添加的、或历史数据）。
- "无可用方案"意味着所有物流都被 `pricing/filter.py` 或 `pricing/cost_filter.py` 过滤掉了。
- **需要在用户的真实数据库环境中调试** — 这是数据相关问题，不是代码逻辑错误。
- 需要添加调试日志以定位具体过滤原因。

### Bug 2: 公共物流池 — 只显示100条 + 3个xlsx导入失败 + 删除全部失败

**用户描述**:
1. `China_scoring_ENG_CN_25_03_2026_1773650328.xlsx` 导入成功但只显示100条（实际有174条）
2. 其它3个xlsx（FBP、China Post、CIS）导入显示 "Internal Server Error"
3. 点击"删除全部"显示"删除失败"

**根因分析**:
1. **只显示100条**: 前端 `fetchLogistics()` 调用 `logisticsPoolAPI.getAll()` 时没有传参数，后端 `GET /api/logistics-pool` 默认 `limit=100`。数据库中实际有174条，只是 list 请求只返回了100条。**修复**: 前端需要实现分页，或者后端增大默认 limit。
2. **3个xlsx导入失败**: 本地测试验证：格式检测（detector.py）对3个文件都能正确识别格式，各parser也能正确解析所有行。`parse_file()` 返回正常。问题可能在 `insert_row()` 的 DB 插入环节 — 可能是某些字段值不符合数据库约束（如 NULL 值插入 NOT NULL 列），或者是整个事务超时。**需要在 import 端点添加更好的错误处理和日志**。
3. **删除全部失败**: `delete_all()` 代码已有 `synchronize_session=False`，`get_db()` 自动 commit。可能的原因：(a) 前端未获得 admin 权限导致 403/401 错误被统一显示为"删除失败"；(b) 数据库外键约束阻止删除；(c) 超时。**需要在前端改善错误信息展示**。

### Bug 3: 产品导入页面崩溃

**用户描述**: 导入"定价与物流表不计抛.xlsx"时，弹出"文件解析成功，请确认列映射"后，页面显示"页面发生了意外错误，请尝试重新加载"。

**根因分析**:
- API 端点 `/api/products/import/preview` 成功返回了数据（否则不会弹出成功 toast）
- 该 xlsx 有 **144 列**（包含1个空列名）和 199 行数据
- React 在渲染 Step 2 时崩溃，触发 ErrorBoundary
- **根本原因**: 后端返回的 `columns` 数组包含空字符串 `""`（来自 xlsx 中 None 列名）。当前端将空字符串传给 Radix UI 的 `<SelectItem value="">` 时，与 `<SelectItem value="none">` 冲突，Radix 内部 invariant 检查失败导致 React 崩溃
- 次要原因: 143 个列全部渲染在 Select 下拉和预览表中，体验很差

## 修复范围

| Bug | 修复文件 | 复杂度 |
|-----|---------|-------|
| Bug 1 | `api/routes/pricing.py`, `pricing/calculate_pricing.py` | 中 — 添加调试日志 |
| Bug 2.1 | `frontend/src/pages/LogisticsPoolPage.jsx`, `api/routes/logistics_pool.py` | 中 — 分页实现 |
| Bug 2.2 | `api/routes/logistics_pool.py` | 低 — 错误处理改善 |
| Bug 2.3 | `frontend/src/pages/LogisticsPoolPage.jsx`, `db/logistics_pool.py` | 低 — 错误信息改善 |
| Bug 3 | `api/routes/products.py`, `frontend/src/pages/ProductImportPage.jsx` | 中 — 过滤空列名 + 限制预览列数 |

## 约束

- `pricing/commission.py` 不得修改
- 所有界面文字保持中文
- 代码修改保持最小化和聚焦
