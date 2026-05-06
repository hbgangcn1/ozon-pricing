## MODIFIED Requirements

### Requirement: 最长边超过阈值时按体积重量计费前端值
前端体积重量计费方式 Select 组件中，"最长边超过阈值时按体积重量计费"选项的 value MUST 为 `"longest_side"`（原为 `"threshold"`），与后端定价引擎 `_calc_volume_weight` 匹配的字符串一致。

#### Scenario: 前端提交值与后端一致
- **WHEN** 用户选择"最长边超过阈值时按体积重量计费"并保存
- **THEN** 数据库中 volume_mode 存储为 `"longest_side"`

### Requirement: 最长边模式条件字段渲染
当 volume_mode 为 `"longest_side"` 时，前端 MUST 条件渲染"最长边阈值(cm)"和"体积重量系数"两个输入框。

#### Scenario: 选择最长边模式显示阈值和系数
- **WHEN** 用户在体积重量计费方式选择"最长边超过阈值时按体积重量计费"
- **THEN** 表单中出现"最长边阈值(cm)"（绑定 longest_side_threshold）和"体积重量系数"（绑定 volume_coefficient）输入框

#### Scenario: 选择不计算体积重量隐藏字段
- **WHEN** 用户选择"不计算体积重量"
- **THEN** 不显示阈值和系数输入框

### Requirement: volume_coefficient 包含在表单默认值中
`DEFAULT_FORM` 和 `handleEdit` MUST 包含 `volume_coefficient` 字段，确保编辑已有规则时不丢失该值。

#### Scenario: 编辑已有规则加载 volume_coefficient
- **WHEN** 用户编辑一条 volume_coefficient=6000 的规则
- **THEN** 表单中体积重量系数输入框显示 6000

### Requirement: 取实际重量与体积重量较大者模式显示系数
当 volume_mode 为 `"max_actual_vs_volume"` 时，前端 MUST 显示"体积重量系数"输入框（无需阈值字段）。

#### Scenario: 选择取较大者模式显示系数字段
- **WHEN** 用户选择"取实际重量与体积重量较大者"
- **THEN** 表单中出现"体积重量系数"输入框

## ADDED Requirements

### Requirement: 历史数据迁移 threshold → longest_side
Alembic 迁移 MUST 将数据库中所有 `volume_mode = 'threshold'` 的记录更新为 `'longest_side'`，覆盖 logistics 和 logistics_pool 两张表。

#### Scenario: 迁移后无 threshold 值残留
- **WHEN** 执行 Alembic 迁移后
- **THEN** 两张表中不存在 volume_mode = 'threshold' 的记录
