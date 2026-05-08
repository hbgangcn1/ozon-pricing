## Context

精准模式（mode=precise）下，所有物流候选都进入 `pricing/cost_filter.py::_process_one_logistic`，通过 `calculate_logistic_cost(logistic, product)` 计算运费。返回 `(None, debug_info)` 表示该物流被淘汰；返回有效 cost 则继续走利润 / 限价过滤。

本次 bug 暴露的根本问题：**两个独立函数对"重量"的定义不同**，但它们本应使用同一个值：

| 函数 | 用途 | 当前用的"重量" |
|---|---|---|
| `pricing/logistic_cost.py::calculate_logistic_cost`（行 282-294） | 早期淘汰判断 `min_weight/max_weight` | `actual_weight`（实重）|
| `pricing/logistic_cost.py::_calc_volume_weight + _calc_fee` | 计费金额计算 | calculated_weight（按 volume_mode）|
| `pricing/filter.py::_filter_check_weight` | 反推淘汰原因时的 `min_weight/max_weight` 重判 | calculated_weight（按 volume_mode）|

→ 抛货实重 2000g、体积重 11730g、ATC Big min_weight=2001g 的场景下：
- `calculate_logistic_cost` 用 2000g 判断 → 2000<2001 → 返回 None
- `_filter_check_weight` 用 11730g 判断 → 11730>2001 → 通过；后续检查也全过 → 反推得到 ""
- `_append_filtered` 写入 `{"name":"ATC Big","reason":""}` → 前端空白

业务侧：`volume_mode=max_actual_vs_volume` 的设计意图就是"按 max(实重, 体积重) 计费"，因此"接收判断"也应当对齐到同一个重量。这不只是 bug 修复，更是消除一个长期存在的语义漂移点。

### 相关文件
- [`pricing/logistic_cost.py`](file:///C:/Users/hbgan/OneDrive/Robert/learn/logistics/pricing/logistic_cost.py)
- [`pricing/filter.py`](file:///C:/Users/hbgan/OneDrive/Robert/learn/logistics/pricing/filter.py)
- [`pricing/cost_filter.py`](file:///C:/Users/hbgan/OneDrive/Robert/learn/logistics/pricing/cost_filter.py)
- [`frontend/src/pages/pricing/PricingResultPanel.jsx`](file:///C:/Users/hbgan/OneDrive/Robert/learn/logistics/frontend/src/pages/pricing/PricingResultPanel.jsx)

### 关键约束
- AGENTS.md：bugfix 不混重构、最小改动、零技术债务
- AGENTS.md：flake8 + Pylance + Pyright 三重检查必过
- AGENTS.md：所有测试必须并行通过（pytest 默认 `-n 4 --dist=loadscope`）
- `_calc_fee` 公开签名（被多处调用与测试 mock）必须不变

## Goals / Non-Goals

**Goals**
- 修复 *Big 物流 reason="" 的可见 bug（86/390 → 0/390 空白 reason）
- 修复对称的 max_weight 错放 bug
- 消除"重量定义"在 `logistic_cost.py` 与 `filter.py` 双实现的结构性漂移源
- 拒绝原因 debug 文案升级，含触发状态（"体积重，已触发" / "实重，未触发"）
- 100% 保持 `_calc_fee` 公开签名不变

**Non-Goals**
- 不重构 `_get_sides` / `_filter_get_sides` 的圆柱体兼容逻辑（保持现有错误路径优先）
- 不修改 `calculate_logistic_cost` 的返回类型 `(Optional[Decimal], List[str])`（避免大面积改测试）
- 不引入结构化错误对象（如 `CostResult` dataclass），保持 debug_info 为 `List[str]`
- 不处理 `weight_g == 0 → 返回 base_fee` 的历史边界（Oracle 提示但本次不混入）
- 不新增 `min_actual_weight` 字段（业务上若需要，留作后续 change）
- 不修改快速模式（`is_fast_mode=True`）的尺寸跳过逻辑

## Decisions

### D1: 抽 `_compute_billable_weight` 为纯函数，放新文件 `pricing/_weight.py`

**决策**：新建 `pricing/_weight.py`，提供 `_compute_billable_weight(logistic, sides, actual_weight) → (weight, label, triggered)`，让 `logistic_cost.py` 与 `filter.py` 共用。

**理由**：
- 不抽 → 留下"两个文件各自定义同一个东西"的隐患（这正是本次事故的根因类型）
- 放 `logistic_cost.py` → `filter.py` 反向 import "成本计算"语义错乱，未来易循环依赖
- 独立文件 `_weight.py` → 低耦合工具模块，未来 `_pricing_helpers.py` 等也可复用
- 函数纯：不接收 `product`，只接 `logistic + sides + actual_weight`，让圆柱/长方体 sides 由调用方负责生成

**替代方案**：
- A. 不抽，两文件各自实现 → 否决：违反"消除漂移源"目标
- B. 放 `logistic_cost.py` → 否决：循环依赖风险 + 语义反向
- C. 接收 `product` 并自己处理圆柱体 → 否决：函数变胖、语义不纯

### D2: `_calc_fee` 签名不变，仅 `_calc_volume_weight` 改造为 wrapper

**决策**：`_calc_fee(logistic, w, debug_info)` 完全不动；`_calc_volume_weight(logistic, sides, actual_weight, debug_info)` 内部改为 `weight, label, triggered = _compute_billable_weight(...)`，append debug 后返回 `weight`。

**理由**：
- `_calc_fee` 被多处调用 + 测试 mock，签名变更回归面爆炸
- "费用计算只需要数字重量"，label/triggered 只属于 debug/reason 层
- wrapper 模式让 `_calc_volume_weight` 的现有调用点零改动

### D3: `min_weight/max_weight` 校验时机移到 `_calc_volume_weight` 之后

**决策**：`calculate_logistic_cost` 内的判定顺序改为：
1. 输入校验（None / 类型 / actual_weight 负数 / actual_weight==0）
2. `_get_sides` + 尺寸/特殊检查（不变）
3. `_calc_volume_weight` 算出 calculated_weight（含 label, triggered）
4. **新位置**：用 calculated_weight 判 `min_weight/max_weight`
5. `_calc_fee` 计费

**理由**：
- 圆柱体的 sides 来自 `_get_sides`，必须先跑
- 尺寸/特殊检查是 vol_mode-independent 的硬限制，独立判
- 计费重量算出后，min/max 才有意义
- `actual_weight==0` 仍走 base_fee 早退路径（保留历史行为，Oracle 提示后续单独处理）

### D4: `_filter_check_weight` 调 `_compute_billable_weight`，错误路径保持原顺序

**决策**：`pricing/filter.py::_filter_check_weight` 内联实现替换为调 helper。`_filter_get_sides` 的圆柱体限制错误优先于重量判断（保持现有顺序）。

**理由**：
- 圆柱体尺寸不合规时应先返回尺寸原因，避免"圆柱体超尺寸但 reason 显示重量原因"的误导
- 与 `calculate_logistic_cost` 内部顺序保持一致

### D5: 兜底 `return ""` 改为 `"未识别的淘汰原因"`，三层防御

**决策**：
1. `pricing/filter.py::_debug_filter_reason` 末尾 `return ""` → `return "未识别的淘汰原因"`
2. `pricing/cost_filter.py::_process_one_logistic` cost is None 分支：`if not reason: reason = "未识别的淘汰原因"`
3. 前端 `PricingResultPanel.jsx`：`item.reason || '未提供原因'`

**理由**：
- D1-D4 修根因，但任何未来不一致都不应再传空 reason 给用户
- 后端必保非空（前端是 UI 防御，不是核心修复）
- 三层文案差异（"未识别的淘汰原因" vs "未提供原因"）可帮助定位未来问题在前后端哪一层

### D6: 拒绝文案按重量来源区分（按用户反馈 + Oracle 决策更新）

**决策**：reason 文案直接以 helper 返回的 `label`（仅 `"实重"` 或 `"体积重"`）开头，格式：
- `体积重 11730.00g 超过上限 10000g`
- `实重 500.00g 低于下限 1000g`

**理由**：
- 用户反馈："因为体积重超限被淘汰，原因应该单独写'体积重 xxxx g 高于上限 xxxx g'"
- helper label 收敛为单一展示词后（Oracle 方案 A），调用方零分支拼装
- 比"计费重量 xxx（体积重，已触发）"更短、更直接，用户一眼就懂"是哪种重量超了"
- helper 在 max 模式下根据 `volume vs actual` 直接选定 label，不再返回 `"max(实重,体积重)"`

**helper label 契约**：
| volume_mode | 比较结果 | label 输出 | triggered |
|---|---|---|---|
| none | - | "实重" | False |
| longest_side | - | "体积重" | True |
| sum_of_sides | - | "体积重" | True |
| max_actual_vs_volume | volume > actual | "体积重" | True |
| max_actual_vs_volume | actual >= volume | "实重" | False |
| 任何模式 | volume_coefficient ≤ 0 | "实重" | False |

## Risks / Trade-offs

| 风险 | 缓解 |
|---|---|
| 现有测试可能断言"实重低于 min_weight 必淘汰" → 改后失败 | 跑全量 pytest，按 volume_mode 区分预期：`none` 模式仍用实重；其它模式按计费重量 |
| 业务侧报价金额变化 → 用户感知"价格突变" | 加 release notes / 用户公告：精准模式抛货报价改按行业惯例（max 实重 vs 体积重） |
| `volume_coefficient=0` 触发 ZeroDivisionError | helper 里防御：`coefficient <= 0 → 视为 none 模式 + debug 警告` |
| 圆柱体 sides 在 `_get_sides` 与 `_filter_get_sides` 形状不一致 → helper 算错 | 契约测试：同 logistic+product 两边 weight 必相等 |
| `actual_weight==0 → base_fee` 早退绕过新逻辑 | 保留现有行为；测试断言此路径不变 |
| 缓存（`_make_cached_cost`）键基于 `(logistic, product)`，行为变化是否被缓存吃掉 | 函数级缓存按 lru_cache 处理；`logistic` / `product` 元组变就重算，本次不需要清缓存 |

## Migration Plan

无 schema 变更、无迁移、无新依赖。标准部署流程：

1. 本地 `python -m pytest -n0 tests/test_logic_pricing.py --tb=short` → 全绿
2. 本地 `python -m pytest --tb=short` → 全绿（并行模式）
3. 本地 `python -m flake8 pricing tests` → clean
4. Pylance / Pyright 警报 → 0
5. 前端 `cd frontend && npm run test` → 全绿
6. 前端 `npm run build` → 静态产物 commit
7. `git push origin main`
8. SSH 后台 deploy.sh + tail /tmp/deploy.log
9. 验证：用"测试计泡"重新计算 → 86 条 *Big 物流 reason 不再为空
10. 浏览器 Playwright 端到端验证 PricingResultPanel 渲染

### Rollback
- 出问题：`bash deploy/rollback.sh pre-deploy-<timestamp>`
- pre-deploy tag 自动由 deploy.sh 第 2 步创建

## Open Questions

无（Oracle 两轮决策已闭环；用户已确认方案）。
