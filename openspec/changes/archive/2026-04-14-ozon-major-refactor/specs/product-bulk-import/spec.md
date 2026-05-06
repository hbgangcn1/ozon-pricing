## ADDED Requirements

### Requirement: 上传 xlsx 并映射列到产品字段
系统 SHALL 支持用户上传 xlsx 文件，后端解析表头行并返回列名列表，前端展示列映射界面让用户将 xlsx 列对应到产品字段（name、unit_price、weight_g、length_cm、width_cm、height_cm 等）。

#### Scenario: 上传 xlsx 获取列名
- **WHEN** 用户上传一个 xlsx 文件到 POST /api/products/import/preview
- **THEN** 系统解析第一行（表头），返回列名列表和前5行预览数据，HTTP 200

#### Scenario: 用户提交列映射
- **WHEN** 用户在前端完成列映射并点击"导入"，提交包含列映射关系和文件引用的请求
- **THEN** 系统按映射关系读取数据行，执行数据清洗后返回导入预览（含冲突列表）

#### Scenario: 文件格式不支持
- **WHEN** 用户上传非 xlsx 文件
- **THEN** 系统返回 400 错误，提示仅支持 .xlsx 格式

### Requirement: 自动数据清洗
系统 SHALL 在导入时自动将字符串类型的数值字段转换为对应数值类型，忽略空行，跳过无法解析的行并记录。

#### Scenario: 字符串数值自动转换
- **WHEN** xlsx 单元格中 unit_price 为字符串 "29.99"
- **THEN** 系统将其转换为 Float 29.99 后存储

#### Scenario: 无法转换的字段
- **WHEN** xlsx 单元格中 weight_g 为非数值字符串 "重量不明"
- **THEN** 系统将该行标记为解析错误，记录到错误报告，跳过该行

#### Scenario: 空行跳过
- **WHEN** xlsx 文件中存在全空行
- **THEN** 系统自动跳过，不计入导入统计

### Requirement: 重复产品手动处理
系统 SHALL 在导入时检测与现有产品名称重复的条目，返回冲突列表供用户逐条选择覆盖或跳过，不自动处理。

#### Scenario: 检测到重复产品
- **WHEN** 导入数据中某产品名称与当前用户已有产品重名
- **THEN** 系统在预览响应中标记该条目为 conflict，包含现有产品信息和新导入数据

#### Scenario: 用户选择覆盖
- **WHEN** 用户对某冲突条目选择 "overwrite"，提交最终确认请求
- **THEN** 系统用新数据覆盖现有产品记录

#### Scenario: 用户选择跳过
- **WHEN** 用户对某冲突条目选择 "skip"，提交最终确认请求
- **THEN** 系统保留现有记录不变，跳过该条目

#### Scenario: 批量确认导入
- **WHEN** 用户提交含所有冲突处理决策的最终确认请求到 POST /api/products/import/confirm
- **THEN** 系统执行批量入库，返回最终结果：成功条数、覆盖条数、跳过条数、错误条数
