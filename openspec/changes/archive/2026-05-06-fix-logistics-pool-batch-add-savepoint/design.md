## Context

`api/routes/logistics_pool.py` 中的 `batch_add_to_my_logistics`（公共物流池"批量添加到我的物流"接口）当前对任意非空 `ids` 一律 500。隔离 repro 脚本直接抛出 `sqlalchemy.exc.AsyncContextNotStarted: AsyncSessionTransaction context has not been started and object has not been awaited.`。

根因链：

1. **SAVEPOINT 用法错误**（第 255-266 行）
   ```python
   savepoint = session.begin_nested()      # 仅返回对象，未启动
   try:
       new_id = await create_logistics(...)
       await savepoint.commit()             # 炸点：savepoint 从未 await/async with
   ```
   SQLAlchemy 2.x AsyncSession 协议要求 `async with session.begin_nested():` 或 `await session.begin_nested()`，二选一。

2. **except 链过窄 + 嵌套结构混乱**（第 255-280 行）
   外层只接 `IntegrityError`，`AsyncContextNotStarted`（继承自 `InvalidRequestError`）逃逸 → 全局 handler → 500。

3. **日志文件 sink 缺少 `{exception}`**（`logger_config.py:245-259` 的 `format_log`）
   loguru `InterceptHandler` 已在 `logger_config.py:190` 实现，`logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)` 已在 `:344` 调用。但 `format_log` 自定义模板未包含 `{exception}` 字段，因此 `logging.error(..., exc_info=True)` 经桥接进入 loguru 后 traceback 被丢弃。结果：`logs/logistics_error_*.log` 0 字节，调试时看不到调用栈。

对照实验：单条路由 `POST /api/logistics-pool/{pool_id}/add-to-my-logistics`（不使用 SAVEPOINT）200 OK，证明 `create_logistics`、`_sanitize_pool_data`、`_check_logistics_limit`、Logistics 表 schema 全部正常。

## Goals / Non-Goals

**Goals:**
- batch handler 在 SAVEPOINT 用法上符合 SQLAlchemy 2.x AsyncSession 协议。
- 单条记录的 **数据库 / 数据级失败**（`IntegrityError`、`DataError`、`StatementError`）转为 `errors[]` 条目，**不污染同批次其他记录**，整批返回 200。
- 程序错误（`AttributeError`、`TypeError`、`KeyError`）和系统级错误（`OSError`、`asyncio.CancelledError`）必须 **继续向上传播** 到全局 handler，避免把真实 bug 伪装成 "单行失败"。
- 全局 exception handler 抛出的 traceback 必须完整落到 `logs/logistics_error_*.log`。
- 单条路由 `add_to_my_logistics` 也用 SAVEPOINT 包裹，但 **不静默吞异常**：仍按既有 4xx/5xx 语义抛出，仅依赖 SAVEPOINT 让 outer session 保持干净。

**Non-Goals:**
- 不改前端代码（前端调用方已正确）。
- 不改响应 JSON 形状（前端按现有 schema 解析）。
- 不改 logistics / logistics_pool 表 schema、不加迁移。
- 不引入新 Python 依赖（loguru / SQLAlchemy 已存在）。
- 不改 `_check_logistics_limit` 业务规则、订阅额度逻辑。
- 不改 `recalculate_priority_groups` 的调用时机或语义。
- **不改空列表 / 超限的 HTTP 状态码**（保留现有 `400`，避免外部 API 行为变更）。

## Decisions

### D1: SAVEPOINT 用 `async with`，异常在外层捕获

**选择**：
```python
for pool_id in body.ids:
    item = pool_items.get(pool_id)
    if not item:
        not_found.append(pool_id)
        continue
    data = {k: v for k, v in item.items() if k not in _COPY_EXCLUDE}
    _sanitize_pool_data(data)
    try:
        async with session.begin_nested():
            new_id = await create_logistics(session, user_id, data)
    except IntegrityError as exc:
        name = data.get("name", pool_id)
        pgcode = getattr(exc.orig, "pgcode", None) if exc.orig else None
        if pgcode == "23505":
            errors.append(f"{name}: 已存在")
        elif pgcode:
            errors.append(f"{name}: 数据库错误({pgcode})")
        else:
            errors.append(f"{name}: {exc}")
        logger.warning("batch-add 跳过 pool_id=%s: %s", pool_id, exc)
    except DBAPIError as exc:
        # connection_invalidated 必须中止整批 (spec.md:38, design.md D2)
        if getattr(exc, "connection_invalidated", False):
            logger.exception("batch-add 连接失效，中止整批")
            raise
        # 其它 DBAPI 子类 (DataError / ProgrammingError / OperationalError 等) 单条跳过
        name = data.get("name", pool_id)
        errors.append(f"{name}: {exc}")
        logger.warning("batch-add 跳过 pool_id=%s DB 错误: %s", pool_id, exc)
    except StatementError as exc:
        # 非 DBAPI 的 StatementError (绑定/编译阶段错误等)，单条跳过
        name = data.get("name", pool_id)
        errors.append(f"{name}: {exc}")
        logger.warning("batch-add 跳过 pool_id=%s 语句错误: %s", pool_id, exc)
    else:
        added.append(new_id)
```

**异常顺序的关键不变量**（SQLAlchemy 异常 MRO，违反则 `connection_invalidated` 永远不可达）：
- `IntegrityError ⊂ DatabaseError ⊂ DBAPIError ⊂ StatementError`
- `DataError ⊂ DatabaseError ⊂ DBAPIError ⊂ StatementError`

因此必须 **先具体后宽泛**：`IntegrityError` → `DBAPIError`（含 connection_invalidated 检查）→ `StatementError`（兜底非 DBAPI 的语句错误）。把 `(DataError, StatementError)` 放在 `DBAPIError` 前面会**屏蔽**整个 `DBAPIError` 分支（因为 `DBAPIError` 是 `StatementError` 的子类），导致 connection_invalidated re-raise 失效，连接已废仍继续轮询。

**理由**：
- `async with` 自动处理 commit / rollback 与异常重抛，比手写 `await sp.commit()` / `await sp.rollback()` 少一层错误面；SQLAlchemy 官方对 AsyncSession SAVEPOINT 首选示例就是 `async with`。
- 异常处理放在 `async with` **外层**：上下文管理器先回滚 SAVEPOINT，再让异常继续传播到我们的 except 链，结构清晰。
- `else` 分支保证 **只有真正成功** 才追加到 `added` / `new_ids`，避免回滚后状态不一致。
- 与现有项目其它 async 上下文（`AsyncSessionLocal()` / `async with session.begin()`）风格一致。

**Alternatives considered**：
- `sp = await session.begin_nested(); try: ...; await sp.commit() except: await sp.rollback(); raise` — 更啰嗦、易再次写错（曾经的 bug 就是这种风格残留）。
- 把 `added.append(new_id)` 放在 `async with` 内部 — 拒绝。如果未来在块内追加更多语句导致 commit 在追加之后才失败，会出现 "已 rollback 但已记录" 的假阳性。

### D2: 异常 catch 范围窄而明确（不裸 `except Exception`）

**选择**：只 catch `IntegrityError`、`DataError`、`StatementError`、`DBAPIError`（按 SQLAlchemy 异常层次的"数据 / 数据库执行错误"），并对 `DBAPIError.connection_invalidated == True` 立即 re-raise。

**理由**：
- batch 接口语义是 "对每条数据库失败保持鲁棒"，**不是** "对所有异常保持鲁棒"。
- 裸 `except Exception` 会吞 `AttributeError` / `TypeError` / `KeyError` / `InvalidRequestError`，这些都是程序员错误，伪装成 "单行失败" 会让真实 bug 隐藏在 `errors[]` 里很久。
- `KeyboardInterrupt`、`SystemExit`、`asyncio.CancelledError`（继承自 `BaseException`，不属 `Exception`）天然不会被这条链抓到，符合 Python 最佳实践。
- 连接失效（`connection_invalidated`）说明整个 session 已经废，继续循环没有意义，必须 re-raise 让全局 handler 接管。

**Alternatives considered**：
- 仅 catch `IntegrityError`（原版） — 拒绝。`volume_mode` CHECK 违反会抛 `DataError`（`IntegrityError` 的兄弟），仍然 500，没解决用户报告的核心症状。
- 增加白名单 `ValueError` — 拒绝。`ValueError` 来源太杂，应该在 `_sanitize_pool_data` 里前置校验，不在循环里吞。

### D3: 单条路由加 SAVEPOINT，但不吞异常

**选择**：`add_to_my_logistics`（单条路由）用 `async with session.begin_nested():` 包裹 `create_logistics`，**不加 except**。任何异常按既有语义传到 FastAPI 全局 handler，但因为 SAVEPOINT 已 rollback，outer session 仍可被 `get_db()` 的 finally 干净 commit 或 rollback。

**理由**：
- 行为统一（SAVEPOINT pattern 全文件一致），便于审计。
- 隔离潜在的 `IntegrityError`，不让 outer transaction 进入 `PendingRollback`。
- 单条接口的语义是 "这一条插入成功 / 失败" 二元结果，不像 batch 需要鲁棒，**不应** catch + 转 4xx，否则会把 `recalculate_priority_groups` 失败等系统错误也错误降级。
- 性能开销可忽略（一次 SAVEPOINT/RELEASE）。

**Alternatives considered**：
- 维持现状（单条无 SAVEPOINT） — 拒绝。文件内两套 pattern 增加心智负担，未来再写新路由容易抄错。
- 单条路由也 catch `IntegrityError` 转 409 — 拒绝。改变现有响应语义，超出本 change 范围。

### D4: 修复 `format_log` 让 traceback 落盘

**选择**：在 `logger_config.py` 的 `format_log` 函数末尾追加 `\n{exception}` 字段（loguru 模板变量），让 `logger.exception(...)` / `logger.error(..., exc_info=True)` 的 traceback 真正写入文件 sink。

**当前现状**（关键修订点）：
- ✅ `InterceptHandler` 类已在 `logger_config.py:190-206` 实现完整。
- ✅ `logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)` 已在 `:344` 调用。
- ✅ `logs/logistics_2026-05-06.log` 末尾可见 `INFO | logging:callHandlers:1744 | setup plugin alembic.autogenerate.*`，证明 stdlib 日志确实已经被 InterceptHandler 桥接到 loguru。
- ❌ **但** `logs/logistics_error_2026-05-06.log` 是 0 字节，因为 `format_log` 模板字符串只引用了 `{record['time']}` / `{record['level']}` / `{record['name']}` / `{record['function']}` / `{record['line']}` / `{message}`，**没有** `{exception}` 字段。loguru 默认会把 `exc_info` 编为 `record["exception"]`，但自定义 format 函数不引用它就被丢弃。

**修改**：
```python
def format_log(record):
    ...
    base = (
        f"<green>{record['time']:YYYY-MM-DD HH:mm:ss}</green> | "
        f"<level>{record['level'].name: <8}</level> | "
        f"<cyan>{record['name']}</cyan>:"
        f"<cyan>{fn_name}</cyan>:"
        f"<cyan>{record['line']}</cyan> | "
        f"<level>{message}</level>"
    )
    # 关键：让 traceback 跟在 message 之后落盘
    return base + "\n{exception}"
```

**注意**：返回字符串中的 `{exception}` 是 **loguru 模板字符串**（loguru 会替换它），不是 Python f-string 占位符。所以必须 **不在 f-string 内** 而是用纯字符串拼接，或者用双 `{{exception}}` 转义。

**Alternatives considered**：
- 显式在 except 链里 `logger.bind(exc=traceback.format_exc()).error(...)` — 拒绝。要改大量 caller，治标不治本。
- 改 `api/main.py:274` 用 `from loguru import logger; logger.exception(...)` 替换 stdlib — 可行但不彻底，未来其他模块用 stdlib 仍然丢 traceback。

### D5: 测试用真实 PostgreSQL，IntegrityError 通过 CHECK 约束触发

**选择**：新增 `tests/test_api_logistics_pool_batch_add.py` 用项目现有 `conftest.py` 的真实 DB 夹具（`db_session` / `test_admin` / `client`）。

**关键修订**：`logistics` 表 **没有** unique 约束（`models/logistics.py` 全文确认），所以原计划 "插入重复触发 23505" 不可行。改用：
- **Test E（IntegrityError 隔离）**：用 `monkeypatch` 替换 `api.routes.logistics_pool._sanitize_pool_data`，让其在第 2 条记录时把 `data["volume_mode"]` 设为 `"__INVALID__"`，触发 alembic `d2e9f3b4c5a6_update_volume_mode_check_constraint` 添加的 CHECK 约束 → 真实 Postgres 抛 `IntegrityError`，pgcode `23514`。
- **Test F（非 IntegrityError 隔离）**：用 `monkeypatch` 替换 `api.routes.logistics_pool.create_logistics`，让其在第 2 条记录时抛 `DataError("simulated", "stmt", {})` （SQLAlchemy `DataError` 是 batch except 链中的合法范围）。

不 mock session、不 mock 数据库连接，符合 AGENTS.md 规范；只 monkeypatch **路由内引用的辅助函数**，等价于改写一个临时实现。

**Alternatives considered**：
- 真给数据库加临时 unique index 来触发 23505 — 拒绝。改 schema 超出范围。
- mock `session.execute` 抛错 — 拒绝。AGENTS.md 禁止 mock session。

## Risks / Trade-offs

- **Risk: `async with session.begin_nested()` 在 outer 没有 transaction 时行为依赖 autobegin** → Mitigation: SQLAlchemy 2.x AsyncSession 默认 autobegin，`get_db()` 已经触发 autobegin（第一个 `await get_by_ids` 即启动）。已通过 repro 脚本验证 nested 能在 autobegin 之上正常建立。
- **Risk: D2 异常范围依然漏掉了某种 SQLAlchemy 异常子类** → Mitigation: `DBAPIError` 是 SQLAlchemy 几乎所有 DB 层异常的基类，`StatementError` 覆盖参数绑定 / 转换错误。如果发现新的逃逸异常，在不破坏 D2 原则（不裸 `except Exception`）的前提下追加具体类型。
- **Risk: D3 单条路由加 SAVEPOINT 后某些既有客户端依赖原 transaction 行为** → Mitigation: SAVEPOINT 对外完全透明（成功就 RELEASE，失败就 ROLLBACK SAVEPOINT），不改变任何对外语义。
- **Risk: D4 改 `format_log` 影响所有 sink（控制台 + 文件）** → Mitigation: loguru 在 `record["exception"]` 为空时会渲染为空字符串 + 一个换行，控制台多一个空行可接受；如果嫌丑可在 console sink 单独配 `format=` 不带 `{exception}`。
- **Risk: 测试 E 用 monkeypatch 改 `_sanitize_pool_data` 可能影响并行的其他测试** → Mitigation: pytest `monkeypatch` 自动 per-test teardown，xdist 不同 worker 不共享 module state（unless `loadgroup`），项目目前未配置危险并行模式。
- **Trade-off**: 单条路由加 SAVEPOINT 增加一次 SQL 往返（BEGIN SAVEPOINT / RELEASE） → 可接受，单条接口本就低频。
- **Trade-off**: 不改 4xx → 5xx 行为 / 不改空列表 422 → 牺牲 "API 一致性"，但保证 "无 user-visible 行为变更"，符合 bug fix scope。

## Migration Plan

无 schema 迁移、无数据迁移。部署即生效：
1. 合并代码后重启 backend。
2. 验证：`curl POST /api/logistics-pool/batch-add-to-my-logistics body {"ids":[<现有 pool id>]}` 返回 200。
3. 回滚策略：`git revert` 即可，无需任何数据修复。
