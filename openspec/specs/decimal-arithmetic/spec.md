## ADDED Requirements

### Requirement: Pricing 模块全链路使用 Decimal 进行货币计算

系统 SHALL 在 pricing 模块的所有货币计算中使用 Python `decimal.Decimal` 类型，禁止使用 `float` 类型进行任何价格、费用、成本、汇率、利润率的计算。

#### Scenario: float() 强制转换被替换为 Decimal 构造

- **WHEN** 从产品数据或物流数据中读取价格/费用字段时
- **THEN** 系统 SHALL 使用 `Decimal(str(value))` 或 `Decimal(int_value)` 进行类型转换，禁止使用 `float(value)`

#### Scenario: 浮点字面量被替换为 Decimal 字符串构造

- **WHEN** 代码中需要使用数值常量（如 `0.02`、`0.001`、`15`、`200`）时
- **THEN** 系统 SHALL 使用 `Decimal('0.02')`、`Decimal('0.001')`、`Decimal('15')`、`Decimal('200')` 等形式，禁止使用裸浮点字面量参与货币运算

#### Scenario: 函数签名使用 Decimal 类型注解

- **WHEN** pricing 模块中的函数接受或返回价格/费用/汇率/利润等货币相关参数时
- **THEN** 函数签名 SHALL 使用 `Decimal` 类型注解替代 `float`（例如 `price: Decimal` 替代 `price: float`）

#### Scenario: 混合类型运算被禁止

- **WHEN** 进行货币计算时
- **THEN** 系统 SHALL 确保运算双方均为 `Decimal` 类型，禁止 `Decimal` 与 `float` 混合运算（Python 会抛出 `TypeError`）

### Requirement: round() 替换为 Decimal.quantize()

系统 SHALL 使用 `Decimal.quantize()` 替代内置 `round()` 进行货币值舍入，并显式指定舍入模式。

#### Scenario: 佣金费率四舍五入到 4 位小数

- **WHEN** 计算佣金费率需要舍入到 4 位小数时
- **THEN** 系统 SHALL 使用 `value.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)` 替代 `round(value, 4)`

#### Scenario: 迭代收敛判断使用 Decimal 容差

- **WHEN** `floating_price.py` 和 `final_price.py` 中的迭代求解器判断收敛时
- **THEN** 系统 SHALL 使用 `abs(new_value - old_value) < Decimal('0.001')` 进行比较，禁止使用 float 容差

### Requirement: math.ceil 替换为 Decimal 安全实现

系统 SHALL 在物流费用计算中使用 Decimal 兼容的向上取整方式替代 `math.ceil()`。

#### Scenario: 物流费用单位数计算

- **WHEN** `logistic_cost.py` 和 `filter.py` 计算续重单位数 `units = math.ceil(w / continue_unit)` 时
- **THEN** 系统 SHALL 使用 `int((w / continue_unit).to_integral_value(rounding=ROUND_CEILING))` 或等效的 Decimal 向上取整实现

### Requirement: 汇率服务返回 Decimal

系统 SHALL 确保汇率服务（`exchange_service*.py`、`enhanced_exchange_service.py`）向 pricing 模块提供 `Decimal` 类型的汇率值。

#### Scenario: 外部 API 汇率转换

- **WHEN** 从外部汇率 API 获取 float 类型的汇率值后
- **THEN** 汇率服务 SHALL 在返回前使用 `Decimal(str(rate))` 将其转换为 Decimal

#### Scenario: 兜底汇率使用 Decimal

- **WHEN** 使用硬编码的兜底汇率（如 RUB/CNY = 0.0904, USD/CNY = 7.2）时
- **THEN** 系统 SHALL 使用 `Decimal('0.0904')` 和 `Decimal('7.2')` 表示

### Requirement: API 序列化保持向后兼容

系统 SHALL 确保 Decimal 值在 JSON 响应中序列化为数值类型（非字符串），保持与现有前端的兼容。

#### Scenario: Pydantic schema 序列化 Decimal 为 JSON number

- **WHEN** API 路由返回包含 Decimal 价格字段的响应时
- **THEN** Pydantic SHALL 将 Decimal 值序列化为 JSON `number` 类型（如 `12.34` 而非 `"12.34"`）

#### Scenario: 前端无需代码变更

- **WHEN** 前端接收到 API 响应中的价格字段时
- **THEN** 现有的 `toFixed(2)` 调用 SHALL 继续正常工作，无需修改

### Requirement: convert_decimals 桥函数移除

系统 SHALL 移除 `api/routes/_pricing_helpers.py` 中的 `convert_decimals` 函数，因为全链路 Decimal 后不再需要 Decimal→float 转换。

#### Scenario: 定价结果直接传递 Decimal

- **WHEN** pricing 模块返回计算结果给 API 层时
- **THEN** 结果 SHALL 以 Decimal 类型直接传递，无需经过 `convert_decimals` 转换

### Requirement: 非货币物理量保持原类型

系统 SHALL 不对非货币的物理量字段（如 `weight_kg`、`length_cm`、`width_cm`、`height_cm`）进行 Decimal 迁移。

#### Scenario: 重量和尺寸保持整数或 float

- **WHEN** 计算体积重量或实际重量时
- **THEN** 重量（克）和尺寸（厘米）字段 SHALL 保持使用整数类型，仅在与货币值运算时转换为 Decimal
