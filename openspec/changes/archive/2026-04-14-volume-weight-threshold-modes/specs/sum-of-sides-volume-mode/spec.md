## ADDED Requirements

### Requirement: 三边和超过阈值时按体积重量计费模式
系统 SHALL 支持 `"sum_of_sides"` 体积重量计费模式。当产品的 length_cm + width_cm + height_cm 超过物流规则配置的 `sum_of_sides_threshold` 时，系统 MUST 按体积重量计费。

体积重量计算公式：`volume_weight_g = (length_cm × width_cm × height_cm) / volume_coefficient × 1000`

当三边之和未超过阈值时，系统 MUST 使用产品实际重量计费。

#### Scenario: 三边和超过阈值按体积重量计费
- **WHEN** 物流规则 volume_mode = "sum_of_sides"，sum_of_sides_threshold = 90，volume_coefficient = 6000，产品 length=40, width=30, height=25（三边和=95 > 90）
- **THEN** 体积重量 = (40×30×25)/6000×1000 = 5000g，使用 5000g 作为计费重量

#### Scenario: 三边和未超过阈值使用实际重量
- **WHEN** 物流规则 volume_mode = "sum_of_sides"，sum_of_sides_threshold = 90，产品 length=30, width=20, height=15（三边和=65 ≤ 90），实际重量=2000g
- **THEN** 使用实际重量 2000g 作为计费重量

### Requirement: 三边和模式数据库字段
系统 MUST 在 logistics 和 logistics_pool 两张表中包含 `sum_of_sides_threshold` 字段（Integer, 默认 0）。

#### Scenario: 新增字段存在且有默认值
- **WHEN** 创建物流规则不指定 sum_of_sides_threshold
- **THEN** 该字段默认值为 0

### Requirement: 三边和模式前端 UI
前端物流规则编辑表单中，体积重量计费方式 MUST 包含"三边和超过阈值时按体积重量计费"选项（value="sum_of_sides"）。选中时 MUST 条件渲染"三边和阈值(cm)"和"体积重量系数"两个输入框。

#### Scenario: 选择三边和模式显示条件字段
- **WHEN** 用户在体积重量计费方式下拉中选择"三边和超过阈值时按体积重量计费"
- **THEN** 表单中出现"三边和阈值(cm)"输入框和"体积重量系数"输入框

#### Scenario: 切换到其他模式隐藏条件字段
- **WHEN** 用户从"三边和超过阈值"切换到"不计算体积重量"
- **THEN** "三边和阈值(cm)"和"体积重量系数"输入框消失

### Requirement: 三边和模式过滤逻辑
定价过滤阶段 `_filter_check_weight` MUST 使用与 `_calc_volume_weight` 相同的 `"sum_of_sides"` 逻辑计算计费重量，用于重量范围过滤。

#### Scenario: 过滤阶段正确计算三边和模式计费重量
- **WHEN** 过滤检查 volume_mode="sum_of_sides"，sum_of_sides_threshold=90，volume_coefficient=6000，产品三边和=95
- **THEN** 按体积重量计算后的重量与 `_calc_volume_weight` 结果一致

### Requirement: FBP XLSX 导入解析三边和模式
FBP 解析器 MUST 识别 S 列包含 "Sum of sides ≤ X cm" 格式的文本，将 volume_mode 设为 `"sum_of_sides"`，从文本中提取阈值 X 存入 `sum_of_sides_threshold`，从 T 列解析 volume_coefficient。

#### Scenario: 解析 "Sum of sides ≤ 90 cm" 格式
- **WHEN** S 列 = "Sum of sides ≤ 90 cm - physical weight,\nSum of sides > 90 cm - volumetric weight"，T 列 = "L × W × H (cm) ÷ 6000"
- **THEN** volume_mode = "sum_of_sides"，sum_of_sides_threshold = 90，volume_coefficient = 6000.0

#### Scenario: 解析 "Sum of sides ≤ 75 cm" 格式
- **WHEN** S 列 = "Sum of sides ≤ 75 cm - Physical weight,\nSum of sides > 75 cм - volume weight"，T 列 = "L × W × H (cm) ÷ 6000"
- **THEN** volume_mode = "sum_of_sides"，sum_of_sides_threshold = 75，volume_coefficient = 6000.0

### Requirement: 添加到用户规则时传递三边和字段
从公共物流池"添加到我的物流规则"时，MUST 传递 sum_of_sides_threshold 字段，确保用户规则中的 volume_mode、sum_of_sides_threshold、volume_coefficient 与源记录一致。

#### Scenario: 复制物流池记录到用户规则
- **WHEN** 物流池记录 volume_mode="sum_of_sides"，sum_of_sides_threshold=90，volume_coefficient=6000
- **THEN** 用户规则中对应字段值完全一致
