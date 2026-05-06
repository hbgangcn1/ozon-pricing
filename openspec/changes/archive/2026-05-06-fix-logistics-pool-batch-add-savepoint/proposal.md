## Why

`POST /api/logistics-pool/batch-add-to-my-logistics`（前端"全部添加到我的物流"按钮）当前对任意非空 `ids`（即使只有 1 条）一律返回 HTTP 500，用户无法批量从公共物流池导入物流规则。已通过隔离 repro 脚本 100% 锁定根因：`api/routes/logistics_pool.py:255-266` 的 SAVEPOINT 用法不符合 SQLAlchemy 2.x AsyncSession 协议（`session.begin_nested()` 既未 `await`、也未 `async with`），抛出 `AsyncContextNotStarted`；该异常不属于 `IntegrityError`，逃逸出 except 链，被全局 handler 转成 500。同时全局 handler 用 stdlib `logging` 写 traceback 但项目使用 loguru、未做桥接，`logs/logistics_error_*.log` 0 字节，错误信息完全丢失，是过去 debug 摸黑的元原因。bug 阻塞核心业务流，必须立刻修复。

## What Changes

- **修复 batch handler 的 SAVEPOINT 用法**：`api/routes/logistics_pool.py:255-266` 改用 `async with session.begin_nested():`，符合 SQLAlchemy 2.x AsyncSession 协议。
- **窄化异常兜底**：batch handler 用 SQLAlchemy 异常层次按 MRO **由具体到抽象** 排序的 except 链 — `IntegrityError`（特化 pgcode 处理）→ `DBAPIError`（含 `connection_invalidated` re-raise，覆盖 `DataError` / `ProgrammingError` / `OperationalError` 等所有 DBAPI 子类）→ `StatementError`（兜底非 DBAPI 的绑定 / 编译错误），把单条数据库失败转换为 `errors[]` 条目而不是整批 500，与"批量"语义一致；**禁止 `except Exception`**，programmer errors（`AttributeError` / `TypeError` / `KeyError`）必须传播到全局 handler 暴露真实 bug（详见 design.md D2 与 spec.md SR-3）。
- **统一单条路由防御**：`add_to_my_logistics`（单条路由）也用同一 SAVEPOINT 模式包裹，行为统一、便于审计。
- **修复 stdlib logging → loguru 桥接**：在 `logger_config.py` 引入 `InterceptHandler`，让 `logging.getLogger("api.error")` 等 stdlib logger 的输出进入 loguru 文件，未来线上排障不再"摸黑"。
- **新增回归测试**：`tests/test_api_logistics_pool_batch_add.py` 覆盖：成功批量、部分 not_found、IntegrityError 转 errors、空 ids、超过 200 条上限、订阅额度超限、单条失败不阻塞批次。

## Capabilities

### New Capabilities
- `logistics-pool-batch-add`: 公共物流池"批量添加到我的物流"接口的事务边界、异常隔离、限额、响应契约，覆盖 `POST /api/logistics-pool/batch-add-to-my-logistics` 与同模块单条路由 `POST /api/logistics-pool/{pool_id}/add-to-my-logistics`。

### Modified Capabilities
（无 — 现有 `openspec/specs/` 中没有 logistics-pool 相关 capability）

## Impact

- **Code**: `api/routes/logistics_pool.py`（batch + 单条路由）、`logger_config.py`（新增 InterceptHandler）、新增测试 `tests/test_api_logistics_pool_batch_add.py`。
- **APIs**:
  - `POST /api/logistics-pool/batch-add-to-my-logistics` — 行为修正（不再 500），响应 schema 不变。
  - `POST /api/logistics-pool/{pool_id}/add-to-my-logistics` — 内部加 SAVEPOINT，外部行为不变。
- **Dependencies**: 无新增依赖（SQLAlchemy / loguru 已在 `requirements.txt`）。
- **Database**: 无 schema 变更、无迁移。
- **Frontend**: 无变更（前端按钮已存在，修复后即可工作）。
- **Logs**: `logs/logistics_error_*.log` 起将记录全局 handler 抛出的 traceback；现有日志文件兼容。
- **Tests**: 新增 7 个用例；预期不影响现有 108 个后端测试文件。
