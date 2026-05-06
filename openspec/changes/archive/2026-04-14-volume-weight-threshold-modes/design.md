## Context

物流定价系统支持三种体积重量计费模式：
- `"none"`: 不计算体积重量，使用实际重量
- `"max_actual_vs_volume"`: 取实际重量与体积重量较大者
- `"longest_side"`: 最长边超过阈值时按体积重量计费

当前问题：
1. 前端 Select 组件使用 `"threshold"` 值，后端 `_calc_volume_weight` 匹配 `"longest_side"`，两者不一致导致该模式从未生效
2. 前端选择"最长边超过阈值"后不显示阈值和系数输入框
3. `volume_coefficient` 不在 DEFAULT_FORM 中，编辑时丢失
4. 缺少"三边和超过阈值"模式
5. FBP XLSX 导入未解析 "Sum of sides" 格式

关键文件：
- 定价计算: `pricing/logistic_cost.py` `_calc_volume_weight` (L168-200)
- 过滤逻辑: `pricing/filter.py` `_filter_check_weight` (L24-51)
- DB 模型: `models/logistics.py`, `models/logistics_pool.py`
- API schema: `api/models/schemas.py`
- 前端: `frontend/src/pages/LogisticsPage.jsx`
- FBP 解析: `xlsx_import/parsers/fbp.py`

## Goals / Non-Goals

**Goals:**
- 修复 `longest_side` 模式：前端值改为 `"longest_side"`，添加条件字段渲染
- 新增 `sum_of_sides` 模式：完整的端到端支持（DB → API → 定价 → 前端 → 导入）
- FBP XLSX 导入正确解析 "Sum of sides ≤ X cm" 格式
- 从公共物流池添加到用户规则时正确传递所有字段
- E2E 测试覆盖所有模式的定价计算正确性

**Non-Goals:**
- 不修改其他 XLSX 格式（china_post、cis_rfbs、scoring_rfbs）的导入逻辑
- 不重构已有的 `none` 和 `max_actual_vs_volume` 模式
- 不做 volume_mode 枚举约束（保持现有 string 类型）

## Decisions

### 1. 前端 volume_mode 值命名
**决定**: 前端 Select 的 value 直接使用后端引擎识别的字符串：`"none"`, `"max_actual_vs_volume"`, `"longest_side"`, `"sum_of_sides"`
**理由**: 消除前后端映射层，form 提交的值直接写入数据库，定价引擎直接读取，减少 bug 面。当前 `"threshold"` vs `"longest_side"` 的不一致就是映射缺失造成的 bug。

### 2. 新增 sum_of_sides_threshold 字段 vs 复用 longest_side_threshold
**决定**: 新增 `sum_of_sides_threshold` (Integer, default 0) 字段到两个表
**理由**: 两种阈值语义完全不同（最长边 vs 三边和），复用同一字段会在同时使用时产生歧义。独立字段更清晰，也便于从公共物流池直接复制到用户规则。

### 3. FBP 导入 volume_mode 映射策略
**决定**: 在 FBP 解析器中，当 S 列匹配 "Sum of sides ≤ X cm" 模式时：
- `volume_mode` = `"sum_of_sides"`
- `sum_of_sides_threshold` = X（从文本中用正则提取）
- `volume_coefficient` = 从 T 列解析（现有 `parse_volume_coeff` 函数）
**理由**: 与 "Physical weight" → `"none"` 和 "Max weight between..." → `"max_actual_vs_volume"` 映射策略一致。

### 4. 条件字段渲染方案
**决定**: 在前端 LogisticsPage.jsx 中，volume_mode 的 Select 后面用条件渲染：
- `"longest_side"` → 显示"最长边阈值(cm)" + "体积重量系数"
- `"sum_of_sides"` → 显示"三边和阈值(cm)" + "体积重量系数"
- `"max_actual_vs_volume"` → 仅显示"体积重量系数"
- `"none"` → 不显示额外字段

### 5. 体积重量计算公式
- `sum_of_sides` 模式：当 `length + width + height > sum_of_sides_threshold` 时，`volume_weight = (length × width × height) / volume_coefficient`，使用 volume_weight 计费
- `longest_side` 模式（已有，不变）：当 `max(length, width, height) > longest_side_threshold` 时，同样公式

## Risks / Trade-offs

- **[已有数据不一致]** → 现有数据库中用前端创建的 `volume_mode="threshold"` 记录无法被定价引擎识别。迁移脚本需将所有 `volume_mode="threshold"` 更新为 `"longest_side"`。
- **[FBP 导入向后兼容]** → 已导入的 FBP 记录的 volume_mode 是原始英文字符串（如 "Physical weight"）。但这些是 logistics_pool 记录，添加到用户规则时需要映射。当前系统是直接复制字段不做映射，所以 FBP 解析器必须直接写入正确的 mode 值。已导入的旧数据需要重新导入。
- **[Alembic 迁移]** → 新增列有默认值 0，对已有数据无影响。但需确认 `volume_mode="threshold"` → `"longest_side"` 的数据迁移写入 Alembic 脚本。
