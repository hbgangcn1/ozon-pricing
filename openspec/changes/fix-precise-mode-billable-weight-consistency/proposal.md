## Why

精准模式下，体积重显著大于实重的"抛货"产品（如"测试计泡" 2kg 实重 / 11.73kg 体积重）会被 **错误地从所有 *Big 后缀物流中淘汰**，且淘汰列表中显示 **空白的淘汰原因**，用户无法定位问题。

根因不是 reason 反推失败，而是 `pricing/logistic_cost.py::calculate_logistic_cost` 在判断 `min_weight/max_weight` 时使用了 **实重 (actual_weight)**，而 `pricing/filter.py::_filter_check_weight` 反推淘汰原因时使用了 **计费重量 (calculated_weight, 含体积重)**，两者语义不一致。同时，`_calc_fee` 内部已经按 `_calc_volume_weight()` 计费，意味着"接收判断"与"计费判断"使用的重量定义本就应当一致。

对称问题同时存在：实重小但体积重大于 `max_weight` 的包裹会被错误放行进入计费流程。

### 影响样本
- 产品 `测试计泡` (id=13948, weight_g=2000, 60×51×46cm)
- 390 条物流候选，86 条 (22%) reason 为空白，全部为 *Big 后缀物流
- 业务侧表现：精准模式"无任何计算结果，全部淘汰"

## What Changes

- 新增纯函数 `pricing/_weight.py::_compute_billable_weight(logistic, sides, actual_weight) → (weight, label, triggered)`，作为 4 种 `volume_mode` 计费重量计算的**唯一来源**
- 修改 `pricing/logistic_cost.py::calculate_logistic_cost`：将 `min_weight/max_weight` 校验从函数开头（基于实重）移到 `_get_sides()` + 尺寸/特殊检查 + 计费重量计算**之后**，使用计费重量进行校验
- 修改 `pricing/logistic_cost.py::_calc_volume_weight`：改为薄 wrapper，调用 `_compute_billable_weight()` 后追加 debug
- 修改 `pricing/filter.py::_filter_check_weight`：复用 `_compute_billable_weight()`，消除重量定义双实现
- 修改 `pricing/filter.py::_debug_filter_reason` 末尾兜底：`return ""` → `return "未识别的淘汰原因"`
- 修改 `pricing/cost_filter.py::_process_one_logistic` cost is None 分支：reason 为空时设为 `"未识别的淘汰原因"`
- 修改前端 `frontend/src/pages/pricing/PricingResultPanel.jsx`：`item.reason || ''` → `item.reason || '未提供原因'`（UI 防御）
- 拒绝原因 debug 文案升级：`计费重量 11730.00g（体积重，已触发）超过上限 30000g`，含 label / triggered 信息
- **BREAKING（业务行为）**：所有 `volume_mode != "none"` 且体积重 ≠ 实重的物流候选的过滤结果可能变化。具体：
  - "实重低、体积重达标" 的抛货：原本被错误淘汰，修复后进入计费流程
  - "实重达标、体积重超 max_weight"：原本错误放行，修复后被正确淘汰

## Capabilities

### New Capabilities
- `pricing-billable-weight`: 物流计费重量计算与重量上下限校验的统一规则。覆盖 4 种 `volume_mode` 的计费重量定义、触发条件、与 `min_weight/max_weight` 校验时机；以及淘汰原因 debug 文案的可读性约束。

### Modified Capabilities
（无 — 现有 spec 中没有已声明的"物流过滤 / 重量计算"capability，此次为新建）

## Impact

### 后端代码
- `pricing/_weight.py`（新建）
- `pricing/logistic_cost.py`（重排 `calculate_logistic_cost` 内部判定顺序，改造 `_calc_volume_weight` 为 wrapper）
- `pricing/filter.py`（`_filter_check_weight` 复用 helper，`_debug_filter_reason` 兜底改文案）
- `pricing/cost_filter.py`（cost is None 分支 reason 兜底）

### 前端代码
- `frontend/src/pages/pricing/PricingResultPanel.jsx`（UI 兜底文案）

### 测试
- `tests/test_logic_pricing.py`（新增 5+ 测试用例：4 种 volume_mode 的 helper 输出、min/max 计费重量校验、never-blank 契约、双调用点一致性契约）

### 业务影响
- 精准模式与快速模式的过滤结果均会发生变化（两个模式都走 `calculate_logistic_cost`）
- 已估算的产品定价缓存 / 历史报价**不会自动重算**，仅新计算受影响
- 用户可见：原本"全部淘汰"的抛货可能出现可用物流；原本"按实重报价"的抛货可能改按体积重报价（金额上升符合行业惯例）

### 数据库
- 无 schema 变更
- 无迁移

### API
- `/api/pricing/calculate-grouped` 响应 `filtered_logistics[*].reason` 不再为空字符串
- 字段类型不变；前端无需 schema 调整

### 部署
- 标准 deploy.sh 流程，无特殊步骤
- 无 alembic 迁移
