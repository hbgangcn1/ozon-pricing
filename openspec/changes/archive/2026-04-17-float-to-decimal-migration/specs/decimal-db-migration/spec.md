## ADDED Requirements

### Requirement: 数据库价格列从 Float 迁移至 Numeric(12,4)

系统 SHALL 将所有存储价格、费用、汇率的数据库列从 `Float` 类型迁移至 `Numeric(12, 4)` 类型，确保数据库层面的精确存储。

#### Scenario: products 表价格列迁移

- **WHEN** Alembic 迁移脚本执行时
- **THEN** `products` 表的 `unit_price`、`labeling_fee`、`shipping_fee`、`target_profit_margin` 等价格相关列 SHALL 从 `Float` 变更为 `Numeric(12, 4)`

#### Scenario: logistics 表费用列迁移

- **WHEN** Alembic 迁移脚本执行时
- **THEN** `logistics` 表的 `base_fee`、`first_fee`、`continue_fee` 等费用相关列 SHALL 从 `Float` 变更为 `Numeric(12, 4)`

#### Scenario: logistics_pool 表费用列迁移

- **WHEN** Alembic 迁移脚本执行时
- **THEN** `logistics_pool` 表中对应的费用列 SHALL 从 `Float` 变更为 `Numeric(12, 4)`

#### Scenario: exchange_rates 表汇率列迁移

- **WHEN** Alembic 迁移脚本执行时
- **THEN** `exchange_rates` 表的汇率列 SHALL 从 `Float` 变更为 `Numeric(12, 6)`（汇率需要更高小数精度）

### Requirement: ORM 模型使用 Numeric 映射

系统 SHALL 将 SQLAlchemy ORM 模型中所有价格/费用相关列的类型从 `Float` 更新为 `Numeric(12, 4)`，使 ORM 自动将数据库值映射为 Python `Decimal`。

#### Scenario: Product 模型列类型更新

- **WHEN** ORM 读取 products 表数据时
- **THEN** 价格相关字段 SHALL 返回 `Decimal` 类型值（而非 `float`），无需手动类型转换

#### Scenario: Logistics 模型列类型更新

- **WHEN** ORM 读取 logistics 表数据时
- **THEN** 费用相关字段 SHALL 返回 `Decimal` 类型值

### Requirement: Alembic 迁移脚本可回滚

系统 SHALL 提供可回滚的 Alembic 迁移脚本，支持 `upgrade` 和 `downgrade` 操作。

#### Scenario: 升级迁移

- **WHEN** 执行 `alembic upgrade head` 时
- **THEN** 所有目标列 SHALL 从 `Float` 变更为 `Numeric`，现有数据保持完整（四舍五入至目标精度）

#### Scenario: 回滚迁移

- **WHEN** 执行 `alembic downgrade` 回退此次迁移时
- **THEN** 所有目标列 SHALL 恢复为 `Float` 类型

### Requirement: 现有数据完整性保障

迁移过程 SHALL 保持现有数据的完整性，不丢失有效数据。

#### Scenario: Float 数据转换为 Numeric 无精度丢失

- **WHEN** 现有 Float 列数据被转换为 Numeric(12, 4) 时
- **THEN** 原始值（已通过 `round(x, 2)` 存入的数据）SHALL 被精确保留，4 位小数空间足以容纳 2 位小数数据

#### Scenario: 迁移前数据备份

- **WHEN** 在生产环境执行迁移前
- **THEN** SHALL 先执行完整数据库备份，确保可在迁移失败时恢复

### Requirement: Pydantic Schema 字段类型更新

系统 SHALL 将 API 层 Pydantic schema 中所有价格/费用相关字段从 `float` 更新为 `Decimal`。

#### Scenario: 请求 Schema 接受 Decimal

- **WHEN** API 接收包含价格字段的请求体时
- **THEN** Pydantic SHALL 将输入值解析为 `Decimal` 类型

#### Scenario: 响应 Schema 输出 JSON number

- **WHEN** API 返回包含 Decimal 价格字段的响应时
- **THEN** Pydantic SHALL 通过 `json_encoders` 配置将 Decimal 序列化为 JSON number（如 `12.34`），保持前端兼容
