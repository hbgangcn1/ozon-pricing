## ADDED Requirements

### Requirement: 计费重量统一计算

系统 SHALL 在精准模式定价的两个阶段（淘汰过滤 `pricing.filter._filter_check_weight`、成本计算 `pricing.logistic_cost.calculate_logistic_cost`）使用同一个共享 helper `pricing._weight._compute_billable_weight(logistic, sides, actual_weight)` 计算计费重量，确保两阶段结果完全一致。

helper 的输出 SHALL 包含三个字段：
- `weight`：最终计费重量（克，float）
- `label`：**最终生效重量来源的展示标签**（字符串，仅取值 `"实重"` 或 `"体积重"`），调用方可直接拼入用户可见文案，无需再判断 `volume_mode`
- `triggered`：是否使用了体积重计算（布尔）。语义等价于 `label == "体积重"`，保留为冗余字段方便调用方做布尔分支判断

helper SHALL 根据 `logistic.volume_mode` 实现以下分支：
- `none`：返回 `(actual_weight, "实重", False)`
- `longest_side`：体积重 = `(longest_side³ / volume_coefficient) * 1000`，返回 `(volume_weight, "体积重", True)`
- `sum_of_sides`：体积重 = `((L+W+H)³ / volume_coefficient) * 1000`，返回 `(volume_weight, "体积重", True)`
- `max_actual_vs_volume`：体积重 = `(L*W*H / volume_coefficient) * 1000`，再比较：
  - 若 `volume > actual`：返回 `(volume, "体积重", True)`
  - 若 `actual >= volume`：返回 `(actual, "实重", False)`

helper MUST NOT 返回 `"max(实重,体积重)"` 之类的复合 / 算法描述字符串作为 label。label 必须是单一展示词。

#### Scenario: none 模式仅用实重
- **WHEN** logistic.volume_mode == "none"，actual_weight=2000g
- **THEN** helper 返回 `(2000.0, "实重", False)`

#### Scenario: max_actual_vs_volume 体积重大于实重
- **WHEN** logistic.volume_mode == "max_actual_vs_volume"，sides=(60,51,46)，volume_coefficient=12000，actual_weight=2000g
- **THEN** 体积重 = (60*51*46/12000)*1000 = 11730g，helper 返回 `(11730.0, "体积重", True)`

#### Scenario: max_actual_vs_volume 实重大于体积重
- **WHEN** logistic.volume_mode == "max_actual_vs_volume"，sides=(10,10,10)，volume_coefficient=12000，actual_weight=5000g
- **THEN** 体积重 = (10*10*10/12000)*1000 ≈ 83.3g，helper 返回 `(5000.0, "实重", False)`

#### Scenario: longest_side 模式始终使用体积重
- **WHEN** logistic.volume_mode == "longest_side"，sides=(60,51,46)，volume_coefficient=6000
- **THEN** 体积重 = (60³/6000)*1000 = 36000g，helper 返回 `(36000.0, "体积重", True)`

#### Scenario: sum_of_sides 模式始终使用体积重
- **WHEN** logistic.volume_mode == "sum_of_sides"，sides=(60,51,46)，volume_coefficient=6000
- **THEN** 体积重 = ((60+51+46)³/6000)*1000 = 619691.16g，helper 返回 `(619691.16, "体积重", True)`

#### Scenario: 两阶段结果一致（契约）
- **WHEN** 同一个 logistic + product 同时输入 `_filter_check_weight` 和 `calculate_logistic_cost`
- **THEN** 两个调用路径内部计算出的 `(weight, label, triggered)` 三元组完全相等（weight 精度 0.01g）

### Requirement: 体积系数异常防御

helper SHALL 在 `volume_coefficient <= 0` 时退化为 `none` 模式，返回 `(actual_weight, "实重", False)`，并通过 `logger_config` 输出 WARNING 级日志（包含 logistic_id），不抛异常。

#### Scenario: volume_coefficient 为 0
- **WHEN** logistic.volume_mode == "max_actual_vs_volume"，logistic.volume_coefficient == 0，actual_weight=2000g
- **THEN** helper 返回 `(2000.0, "实重", False)` 并打印 WARNING 日志

#### Scenario: volume_coefficient 为负数
- **WHEN** logistic.volume_coefficient == -1
- **THEN** helper 返回 `(actual_weight, "实重", False)` 并打印 WARNING 日志

### Requirement: 重量上下限校验时机

`pricing.logistic_cost.calculate_logistic_cost` SHALL 在调用 helper 计算出最终计费重量**之后**再校验 `min_weight` / `max_weight` 边界，禁止使用未经体积重换算的 `actual_weight` 直接判断 min/max。

`pricing.filter._filter_check_weight` 同样 SHALL 基于 helper 输出的最终计费重量判断 min/max 边界。

两处的边界判定结果 MUST 完全一致。

#### Scenario: 体积重满足 min_weight 但实重不满足
- **WHEN** logistic.min_weight=2001，actual_weight=2000g，体积重计算结果=11730g（max_actual_vs_volume 模式）
- **THEN** `_filter_check_weight` 不淘汰该 logistic，`calculate_logistic_cost` 返回非 None 的 cost，且两者基于的计费重量都是 11730g

#### Scenario: 体积重超过 max_weight 上限
- **WHEN** logistic.max_weight=30000，最终计费重量=36000g（longest_side 模式，label="体积重"）
- **THEN** `_filter_check_weight` 淘汰该 logistic 并返回 reason `"体积重 36000.00g 超过上限 30000g"`

#### Scenario: 实重低于 min_weight 下限
- **WHEN** logistic.min_weight=5000，最终计费重量=2000g（none 模式，label="实重"）
- **THEN** `_filter_check_weight` 淘汰该 logistic 并返回 reason `"实重 2000.00g 低于下限 5000g"`

### Requirement: 淘汰原因文案按重量来源区分

`pricing.filter._filter_check_weight` 在因 `min_weight` / `max_weight` 边界淘汰 logistic 时，reason 文案 MUST 直接使用 helper 返回的 `label` 字段作为重量来源前缀，格式严格如下：

- 上限超限：`f"{label} {weight:.2f}g 超过上限 {max_weight:g}g"`
- 下限不足：`f"{label} {weight:.2f}g 低于下限 {min_weight:g}g"`

其中 `label` 必须直接是 helper 返回的 `"实重"` 或 `"体积重"`，禁止再添加"（已触发）"、"（来源：...）"等修饰词；禁止使用 `"计费重量"` 这种通用前缀。

`pricing.cost_filter._process_one_logistic` 在因重量边界导致 `cost is None` 时，写入的 reason 同样 MUST 使用此格式。

#### Scenario: 体积重导致超上限
- **WHEN** helper 返回 `(11730.0, "体积重", True)`，max_weight=10000g
- **THEN** reason 字符串等于 `"体积重 11730.00g 超过上限 10000g"`

#### Scenario: 实重导致超上限（max 模式实重>体积重）
- **WHEN** helper 返回 `(50000.0, "实重", False)`，max_weight=30000g
- **THEN** reason 字符串等于 `"实重 50000.00g 超过上限 30000g"`

#### Scenario: 实重导致不足下限
- **WHEN** helper 返回 `(500.0, "实重", False)`，min_weight=1000g
- **THEN** reason 字符串等于 `"实重 500.00g 低于下限 1000g"`

#### Scenario: 体积重导致不足下限
- **WHEN** helper 返回 `(800.0, "体积重", True)`，min_weight=1000g
- **THEN** reason 字符串等于 `"体积重 800.00g 低于下限 1000g"`

### Requirement: 淘汰原因兜底完整性

`pricing.filter._debug_filter_reason` SHALL 在所有可达分支（包括重量超限、特性不匹配、价格区间未命中、运输方式过滤等）都返回非空字符串。当函数走到结尾兜底分支时，SHALL 返回 `"未识别的淘汰原因"` 而非空字符串。

`pricing.cost_filter._process_one_logistic` 在 `cost is None` 分支 SHALL 兜底设置 reason 为 `"未识别的淘汰原因"`，当 `_debug_filter_reason` 返回空字符串时（防御性兜底）。

#### Scenario: 兜底分支返回固定文案
- **WHEN** `_debug_filter_reason` 走到所有 if 分支都不命中
- **THEN** 返回字符串 `"未识别的淘汰原因"`，不返回 `""`

#### Scenario: cost_filter 兜底防御
- **WHEN** `calculate_logistic_cost` 返回 None 且 `_debug_filter_reason` 返回 `""`
- **THEN** `_process_one_logistic` 写入 `filtered_logistics[i].reason = "未识别的淘汰原因"`

### Requirement: 前端淘汰原因兜底渲染

前端 `frontend/src/pages/pricing/PricingResultPanel.jsx` 渲染 `filtered_logistics[i].reason` 时 SHALL 在 reason 为空字符串、`null` 或 `undefined` 时显示 `"未提供原因"`，而非显示空白单元格。

#### Scenario: reason 为空字符串
- **WHEN** filtered_logistics[i].reason === ""
- **THEN** UI 表格该单元格显示文本 `"未提供原因"`

#### Scenario: reason 字段缺失
- **WHEN** filtered_logistics[i] 不包含 reason 字段
- **THEN** UI 表格该单元格显示文本 `"未提供原因"`

#### Scenario: reason 有正常内容
- **WHEN** filtered_logistics[i].reason === "体积重 11730.00g 超过上限 10000g"
- **THEN** UI 表格该单元格显示原文，不做改写
