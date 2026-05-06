## ADDED Requirements

### Requirement: FBP Excel 导入正确识别所有 Smart 物流
系统 SHALL 在解析 FBP Excel 文件时，正确识别所有标注为 Smart 的物流条目。`is_smart` 标记 MUST 检查 service 列（column C）和 name 列（column G）中是否包含 "smart"（大小写不敏感）。

#### Scenario: service 列包含 Smart 关键词
- **WHEN** FBP Excel 的某行 column C 包含 "Smart" 或 "smart"
- **THEN** 该物流的 `is_smart` 设为 1

#### Scenario: name 列包含 Smart 关键词
- **WHEN** FBP Excel 的某行 column G（物流名称）包含 "Smart"
- **THEN** 该物流的 `is_smart` 设为 1

#### Scenario: 合并单元格值正确传播
- **WHEN** FBP Excel 中 column C 为合并单元格，上方单元格值包含 "Smart"
- **THEN** carry 机制正确传播值到后续空行，`is_smart` 设为 1

### Requirement: 导入结果数量与 Excel 源文件一致
导入结果中的 Smart 物流数量 SHALL 与 Excel 源文件中实际 Smart 物流数量一致。导入接口返回的 `imported` + `skipped` 数量 SHALL 等于 Excel 中有效数据行数。

#### Scenario: 18个 Smart 物流全部被识别
- **WHEN** 导入包含 18 个 Smart 物流的 FBP Excel 文件
- **THEN** 导入结果中 Smart 物流（`is_smart=1`）数量为 18
