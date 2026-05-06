## Context

本系统是一个物流定价计算平台（FastAPI + React），核心功能是根据产品参数、物流方案、汇率等计算最优定价建议。当前全链路使用 IEEE 754 `float` 进行货币计算：

- **数据库层**: PostgreSQL 中使用 `Float` 类型存储价格、费用、汇率（约 14 个列分布在 `products`、`logistics`、`logistics_pool` 等表）
- **ORM 层**: SQLAlchemy `mapped_column(Float)` 映射为 Python `float`
- **业务逻辑层**: `pricing/` 目录 16 个文件，30+ 处 `float()` 强转，所有算术运算基于 float
- **API 层**: Pydantic schemas 使用 `float` 类型注解，`convert_decimals` 桥函数将 ORM 偶尔产生的 `Decimal` 转回 `float`
- **前端层**: `toFixed(2)` 显示价格

**约束**:
- 项目使用 Alembic 进行数据库迁移
- 后端 1597 个测试，前端 234 个测试，必须全部通过
- 生产数据库已有数据，迁移必须保持数据完整性
- 前端不应需要代码变更（JSON number 兼容）

## Goals / Non-Goals

**Goals:**
- 将 pricing 全链路（DB → ORM → 业务逻辑 → API）从 `float` 迁移到 `Decimal`
- 消除所有浮点精度风险（累积误差、灾难性消去）
- 数据库列类型从 `Float` 迁移至 `Numeric(12, 4)`，精确存储
- 保持 API 响应格式向后兼容（前端零改动）
- 全部现有测试通过或正确更新

**Non-Goals:**
- 不改变任何业务逻辑或计算公式（纯类型迁移）
- 不改变前端代码（JSON 序列化策略保证兼容）
- 不改变 API 端点签名或路由结构
- 不迁移非货币字段（如 `weight_kg`、`length_cm` 等物理量，float 完全适合）
- 不做性能优化（Decimal 慢于 float 但 pricing 非热路径）

## Decisions

### D1: Decimal 精度选择 — `Numeric(12, 4)`

**选择**: PostgreSQL `NUMERIC(12, 4)` — 最多 12 位有效数字，4 位小数。

**理由**: 
- 价格范围 0.0001 ~ 99,999,999.9999 覆盖所有业务场景（卢布、美元、人民币）
- 4 位小数适应汇率精度需求（如 CNY/RUB 汇率可能为 12.3456）
- `Numeric(12, 4)` 是电商/物流行业标准精度

**替代方案**:
- `Numeric(10, 2)` — 2 位小数不够汇率和中间计算精度
- `Numeric(18, 6)` — 过度精度，浪费存储，且业务无需
- `Integer`(分为单位) — 需要大量代码重写且不适合多币种汇率

### D2: Python Decimal 构造方式 — 字符串构造

**选择**: 所有 Decimal 通过字符串构造 `Decimal('1.23')`，禁止 `Decimal(1.23)`。

**理由**: `Decimal(1.23)` 会保留 float 的精度问题（`Decimal('1.2299999...')`），字符串构造确保精确。

**实施**: 
- 代码中 `float(x)` → `Decimal(str(x))` 或直接 `Decimal(x)` 当 x 已是字符串/整数
- 浮点字面量 `0.05` → `Decimal('0.05')`
- 从 DB 读取的值通过 SQLAlchemy `Numeric` 自动映射为 `Decimal`，无需手动转换

### D3: API 序列化策略 — JSON number 保持兼容

**选择**: Pydantic schema 字段类型改为 `Decimal`，配置 `json_encoders` 将 Decimal 序列化为 JSON `number`（非字符串）。

**理由**: 
- 前端已在用 `toFixed(2)` 处理 JSON number，零改动
- JSON number 可以精确表示 4 位小数的金额（如 `12.3456` 在 JSON 中是精确的）
- 避免前端需要 `parseFloat()` 字符串的额外改动

**实施**: Pydantic v2 config `model_config = ConfigDict(json_encoders={Decimal: lambda v: float(round(v, 4))})`

### D4: 迁移顺序 — 自底向上

**选择**: DB → ORM → 业务逻辑 → API → 测试，分层逐步迁移。

**理由**: 
- 自底向上确保每层的输入类型在迁移前已经正确
- 可以逐层验证，每层完成后运行测试发现问题
- 最后改 API 层和测试，减少中间状态的不稳定

### D5: `convert_decimals` 处理 — 移除

**选择**: 迁移完成后移除 `api/routes/_pricing_helpers.py` 中的 `convert_decimals` 函数。

**理由**: 该函数的存在是因为 DB 有时返回 Decimal 而系统预期 float。全链路 Decimal 后，这个转换不再需要。

### D6: 汇率服务返回类型 — Decimal

**选择**: `exchange_service*.py` 和 `enhanced_exchange_service.py` 的汇率返回值从 `float` 改为 `Decimal`。

**理由**: 汇率是 pricing 计算的输入，必须保持全链路 Decimal。外部 API 返回的 float 汇率在服务层用 `Decimal(str(rate))` 转换。

## Risks / Trade-offs

**[R1] Alembic 迁移数据精度丢失** → PostgreSQL `ALTER COLUMN ... TYPE NUMERIC(12,4)` 对 Float 数据会四舍五入到 4 位小数。现有 Float 数据本身就是 `round(x, 2)` 后存入的，4 位小数空间充足，不会丢失有效数据。迁移前备份数据库。

**[R2] 性能退化** → Decimal 运算比 float 慢 10-100x。但 pricing 模块是请求级别计算（非批量/高频），单次请求 <100ms 级别的 Decimal 开销可忽略。若未来出现性能问题，可用 `cdecimal`（CPython 3.3+ 默认使用 C 实现的 Decimal）。

**[R3] 第三方库兼容性** → `math.ceil`/`math.floor` 等标准库函数不接受 Decimal 参数（会先转 float 再计算）。需替换为 `Decimal.quantize()` 或自定义 ceil/floor 函数。需逐一检查 pricing/ 中所有 `math.*` 调用。

**[R4] 测试工作量大** → 预估 15+ 个测试文件需要更新 float 断言为 Decimal。采用分批策略：先改核心 pricing 测试，再改 API 测试，最后改边缘测试。

**[R5] JSON 序列化边界** → Pydantic v2 默认将 Decimal 序列化为字符串。必须配置 `json_encoders` 确保序列化为数值，否则前端会收到 `"1.23"` 而非 `1.23`，导致显示异常。

## Migration Plan

1. **备份**: 生产数据库完整备份
2. **Alembic 迁移脚本**: `Float` → `Numeric(12, 4)` 列类型变更
3. **ORM 模型更新**: `mapped_column(Float)` → `mapped_column(Numeric(12, 4))`
4. **业务逻辑迁移**: pricing/ 逐文件改 `float` → `Decimal`
5. **API 层更新**: Pydantic schemas + 序列化配置
6. **测试更新**: 逐文件更新断言
7. **集成验证**: 全量测试套件通过
8. **回滚策略**: Alembic `downgrade` + git revert 代码变更

## Open Questions

_(无——决策已在之前的分析中充分讨论并确认)_
