## Why

pricing 模块全链路使用 IEEE 754 双精度浮点数（`float`）进行货币计算——从数据库 `Float` 列，经 ORM、业务逻辑层 30+ 处 `float()` 强转，到 API 响应序列化。虽然当前通过 `round(x, 2)` 和前端 `toFixed(2)` 掩盖了精度问题，但这是一个深层技术债务：迭代求解器（`floating_price.py`、`final_price.py`）的误差会跨轮次累积，`profit.py` 中 `actual_revenue - total_cost` 存在灾难性消去风险，且系统未来若扩展至支付/结算场景将无法容忍任何精度损失。根据项目"绝不留技术债务"的核心原则，现在彻底迁移到 `decimal.Decimal`。

## What Changes

- **BREAKING**: 数据库层所有价格/费用/汇率相关列从 `Float` 迁移至 `Numeric(precision, scale)`，需 Alembic 迁移脚本
- **BREAKING**: pricing/ 模块全部 16 个文件的算术运算从 `float` 切换到 `Decimal`，包括 `float()` → `Decimal()`、浮点字面量 → `Decimal('...')`
- **BREAKING**: ORM 模型（`models/product.py`、`models/logistics.py`）列类型从 `Float` 改为 `Numeric`
- **BREAKING**: Pydantic schemas 中价格字段从 `float` 改为 `Decimal`，配置 JSON 序列化
- 移除 `api/routes/_pricing_helpers.py` 中的 `convert_decimals` 桥函数（不再需要 Decimal→float 转换）
- 汇率服务（`exchange_service*.py`）返回值类型从 `float` 改为 `Decimal`
- 全部相关测试更新：断言值从 `float` 改为 `Decimal`，新增精度验证测试
- 前端无代码变更（JSON `number` 类型兼容 Decimal 序列化的字符串/数值表示）

## Capabilities

### New Capabilities

- `decimal-arithmetic`: pricing 模块全链路 Decimal 货币计算——覆盖数据库存储、ORM 映射、业务逻辑运算、API 序列化的完整 Decimal 管道
- `decimal-db-migration`: 数据库 Float→Numeric 列迁移——Alembic 迁移脚本、数据类型转换、回滚策略

### Modified Capabilities

_(无现有 spec 需要修改——本次变更是内部实现层面的类型迁移，不改变任何现有功能的外部行为契约)_

## Impact

- **数据库**: PostgreSQL 列类型变更，需 Alembic 迁移脚本（`models/product.py` ~8 列、`models/logistics.py` ~6 列、`models/` 其他可能涉及的表）
- **后端代码**: pricing/ 全部 16 文件、db_utils.py 相关函数、db/ 模块、exchange_service*.py、api/routes/ 中的定价相关路由
- **API 契约**: JSON 响应中价格字段可能从 `1.23` 变为 `"1.23"`（字符串）或保持数值（取决于序列化策略），需确保前端兼容
- **依赖**: 无新增外部依赖（`decimal` 为 Python 标准库）
- **测试**: tests/ 中 ~15+ 个测试文件涉及 float 定价断言，需更新为 Decimal
- **性能**: Decimal 运算比 float 慢 ~10-100x，但 pricing 模块非高频热路径（单次请求级别），影响可忽略
