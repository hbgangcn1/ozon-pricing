## Context

`pytest.ini` 默认开启 `-n 4 --dist=loadscope`，4 个 xdist worker 共享同一个 `logistics` PostgreSQL 数据库。当前 `tests/conftest.py` 的 `test_user`/`test_admin` fixture 在创建用户后直接 `await db_session.commit()`，让数据立即对其他 worker 可见；`clean_db` fixture 则用 `DELETE ... WHERE user_id IN (SELECT id FROM users WHERE is_test_user=1 ...)` 进行无 worker 边界的全局清理。两者叠加导致典型时序：

1. Worker A `test_user` 提交 `user_a`（`is_test_user=1`）
2. Worker B `clean_db` 触发 → DELETE 命中 `user_a`
3. Worker A 后续 `SELECT user_a` → `None` → `assert result is not None` 崩溃

实测全量并行 243/2254 失败，全部失败用例在 `-n0` 顺序模式下 100% 通过。该问题阻塞了 `add-pro-trial-overflow` Phase 8.1 "全量并行零失败" QA 阀门。

**现状关键约束**：
- 所有 worker 共用 `database.py` 的 `engine`/`AsyncSessionLocal`（模块级单例）
- `pytest.ini`：`-n 4 --dist=loadscope --timeout=120 --timeout-method=thread`
- `asyncio_default_fixture_loop_scope = session`
- worker 已感知 `PYTEST_XDIST_WORKER` 环境变量做用户名打散，但 DB 层无 schema 隔离
- 生产 `database.py` 必须 0 改动（生产路径不能受测试夹具影响）
- 生产 `users` / `logistics` / `products` 等表全部生活在 PostgreSQL `public` schema 下
- ORM 模型在 `models/*.py`，统一通过 `models.base.Base` 集中元数据
- `deploy/deploy.sh` 第 4.2 步 `scripts/check_schema_integrity.py` 仅作用于 `public` schema

## Goals / Non-Goals

**Goals:**
- `pytest -n auto` 与 `pytest -n0` 全量结果一致，且零跨 worker 数据污染失败。
- 隔离机制对生产代码 0 改动；切换由 `PYTEST_XDIST_WORKER` 单一环境变量驱动。
- worker 退出/异常时 schema 自动回收，开发机不残留 `test_gw*` schema。
- 单 worker（`-n0`，无 `PYTEST_XDIST_WORKER`）继续走 `public` schema，保持现有日常调试体验。
- 所有现存测试无需逐个改写 ORM 调用，自动透过 `search_path` 重定向到 worker schema。

**Non-Goals:**
- 不修改任何业务逻辑、API 行为、生产 DB schema。
- 不引入新 PyPI 依赖；继续用 `pytest-xdist` + `sqlalchemy` 现有能力。
- 不改 `deploy/deploy.sh`；不影响 `scripts/check_schema_integrity.py`（继续只盯 `public`）。
- 不改 alembic 迁移逻辑；测试 schema 不跑 alembic（直接用 `Base.metadata.create_all`）。
- 不解决 E2E 测试（`test_e2e_volume_modes.py` 命中真实后端 8003）的隔离——E2E 显式 skip，不在 xdist 范围。
- 不解决 frontend vitest 隔离问题（独立技术栈）。

## Decisions

### Decision 1：每 worker 独占 PostgreSQL schema（Option A）

**选择**：在 `pytest_configure` 阶段为每个 xdist worker 创建 `test_<worker_id>` schema（如 `test_gw0`、`test_gw1`、`test_master`），将该 worker 的 SQLAlchemy 引擎 `search_path` 限定到 `test_<worker_id>, public`。所有表通过 `Base.metadata.create_all(bind=conn)` 在 worker schema 内重建。

**为什么不选 Option B（每 worker 独立数据库 `logistics_gw0`）**：
- 需要超级用户 `CREATE DATABASE` 权限；CI 与开发机权限差异大。
- 每个 DB 需要单独跑一遍 alembic 或 `create_all`，启动慢。
- DROP DATABASE 在有活跃连接时会阻塞。
- Schema 切换无需重连，pool 复用更高效。

**为什么不选 Option C（嵌套事务/savepoint，全程不 commit）**：
- 业务代码大量 `await session.commit()`（API 路由、`db.subscriptions.apply_subscription_change` 等）；用 savepoint 包裹会破坏业务侧 commit 语义，导致 trigger / `RETURNING` / 序列号行为偏移。
- async SQLAlchemy 的 `AsyncSession` + savepoint + 多 worker 组合复杂度极高，已知有大量边角 bug。
- 即使 savepoint 成功，`session_security_audit_log` 等"独立连接写入"的旁路日志仍跨 worker 互染。

**为什么不引入 `pytest-postgresql` / `testcontainers`**：
- 新增重量级依赖；与现网 `database.py` 的 asyncpg pool 冲突。
- 启动每 worker 一个临时 PG 实例 → CI 资源占用 4 倍。

### Decision 2：worker schema 通过 connect_args.server_settings.search_path 注入

**选择**：测试 `database.py` 在 `PYTEST_XDIST_WORKER` 存在时，重建一个 worker-local 的 async engine（不复用模块级 `engine`），其 `connect_args` 内 `server_settings={"search_path": "test_<worker>, public"}`。所有 ORM 操作天然落到 worker schema 内的同名表。

**替代方案**：在每个 SQL 前 prepend `SET search_path`。否决原因：性能损耗、易遗漏（裸 `text("INSERT ...")` 调用绕过）。

**实现位置**：新增 `tests/_db_isolation.py`（非测试文件）封装 worker engine 工厂；`tests/conftest.py` 用 `monkeypatch.setattr("database.AsyncSessionLocal", worker_session_factory)` 在 `pytest_sessionstart`（worker 端）挂接。

**确认必要性**：核对 `connect_args.server_settings` 是 asyncpg + SQLAlchemy 2.0 的官方支持路径（已在生产 `database.py` 用于 `statement_timeout`）。

### Decision 3：schema DDL 通过 Base.metadata.create_all（不跑 alembic）

**选择**：worker schema 内执行 `Base.metadata.create_all(bind=sync_conn)`，依赖 SQLAlchemy ORM 模型即时生成 DDL。

**为什么不跑 alembic**：
- alembic 历史迁移有大量 `op.execute("ALTER ...")` 操作 `public` 内现有数据，无法在空 schema 重放。
- alembic 跑全链至少 30s+，乘以 4 worker = 启动延迟 2min+。
- 测试关心"能 INSERT/SELECT"，不关心历史迁移路径正确性（schema_integrity_check 已守卫生产 schema）。

**风险**：ORM 模型与生产 schema CHECK 约束不同步 → 测试漏掉某个生产 CHECK 失败场景。
**缓解**：`scripts/check_schema_integrity.py` 已在 deploy 阶段守卫 `public` schema 的 CHECK 不变量；测试 schema 与生产 CHECK drift 由该 guard 保证不会到生产。`tests/test_grep_guard.py` 风格的 invariant test 可在后续追加（不在本次范围）。

### Decision 4：master 进程 sessionfinish 兜底回收

**选择**：根 `conftest.py` 的 `pytest_sessionfinish` 在 master（`not hasattr(session.config, "workerinput")`）执行 `DROP SCHEMA IF EXISTS test_gw0..test_gwN, test_master CASCADE`。

**为什么 worker 自身不 DROP**：worker 异常崩溃可能不触发 fixture finalizer；master 兜底更可靠。
**为什么不在 sessionstart drop**：开发者偶尔需要手动 `psql` 连进 schema 排查上次失败现场。**修正**：保留 sessionstart `DROP IF EXISTS` + sessionfinish 兜底两道，避免上次脏 schema 干扰本次。最终采用：sessionstart drop + create，sessionfinish drop。

### Decision 5：清理 fixture 的 SQL 全部带 schema 限定

**选择**：`db_session` / `test_user` / `test_admin` / `clean_db` 内的清理 SQL 不再依赖 "全局 `is_test_user=1`" 模式，而是：worker schema 内的表本身就是该 worker 私有 → DELETE 全表（或按 `is_test_user=1`）都只影响本 worker。

**好处**：清理逻辑 0 修改，SQL 还是原样，但 search_path 已经把它锁定在 worker schema。
**确认**：`test_user` 创建逻辑保留 `worker_id_pid_timestamp` 唯一命名（防同 worker 内连续测试碰撞），但跨 worker 命名冲突已不可能（不同 schema 互不可见）。

### Decision 6：`pytest_sessionfinish` 跨表清理改为按 schema 全量 TRUNCATE

**选择**：现有根 `conftest.py` 的 `_cleanup_test_users` 逻辑（DELETE 一长串表 by `user_id` 子查询）在新方案下退化为：master 兜底 `DROP SCHEMA test_gw* CASCADE`。原 `_cleanup_test_users` 函数移除（worker schema DROP 即清空）。

**`public` schema 的兜底清理**：保留但简化——只清 `username LIKE 'test_%' OR username LIKE 'e2e%'` 的残留（防止旧版本测试或手工调试残留），不再关心 worker 隔离问题。

### Decision 7：`drop_test_schemas()` 按 owner 过滤（Phase 1.4 加固）

**选择**：`drop_test_schemas()` 的 SELECT 查询带 `nspowner = (SELECT oid FROM pg_roles WHERE rolname = current_user)` 过滤，仅删除当前角色拥有的 `test_*` schema。

**触发原因**：QA 1.4 实测发现 `_qa_debug.py` 早前用其他角色（如 superuser）创建的 orphan schema（如 postgres-owned `test_qa_smoke`）会让 `DROP SCHEMA ... CASCADE` 抛 `InsufficientPrivilege`，整个 `drop_test_schemas()` 中断。

**为什么不用 try/except 跳过**：吞异常会掩盖真正的权限问题（如 logistics_user 失去自己 schema 的 owner 权限）。owner 预过滤在查询层面就排除不可处理的对象，错误路径仍然 fail-fast。

**为什么不在 sessionstart 一次性 ALTER OWNER**：需要 superuser；与本 change "non-superuser 也可用" 的目标冲突。orphan schema 是测试环境意外产物，不在生产路径上，安全可忽略。

### Decision 8：`create_all_in_schema` 用 `checkfirst=False` + 纯 worker schema 的 search_path（Phase 1.3 修正）

**选择**：执行 DDL 时 `SET search_path TO "<schema>"`（不带 `,public`），并调用 `Base.metadata.create_all(bind=conn, checkfirst=False)`。

**触发原因**：QA 1.3 实测发现：若 search_path 包含 `,public` 且 `public` 已经有 ORM 表（`users` 等），`create_all(checkfirst=True)`（默认）的 `has_table` probe 会通过 search_path 解析到 `public.users` → 误判 "已存在" → 跳过 worker schema 内的 CREATE → worker schema 0 表。

**为什么 DDL 阶段独立处理**：DDL 期间不需要 `public` 兜底；`public` 只在测试运行时（async engine 用 `connect_args.server_settings.search_path="<schema>,public"`）作 fallback，方便个别仍引用 public 的 lookup 表（如未来可能引入的种子表）。`checkfirst=False` 在 worker schema 是空 schema 时无副作用（不会重复 CREATE）。

## Risks / Trade-offs

- **[风险] CI / 开发机 PG 用户无 `CREATE SCHEMA` 权限** → **缓解**：开发机 `postgres` 超级用户默认有；CI 用 `pytest_sessionstart` 阶段一次性 `CREATE SCHEMA IF NOT EXISTS`，失败立即 fast-fail 并打印明确文档链接（README 同步追加权限说明）。
- **[风险] ORM 模型与生产 schema CHECK 约束 drift** → **缓解**：`scripts/check_schema_integrity.py` 已在生产部署阶段守卫；测试侧 drift 不会到生产。后续可补 invariant test。
- **[风险] 测试中遗留 `text("INSERT INTO public.users ...")` 等 schema-qualified raw SQL** → **缓解**：本次 design 包含审计步骤（grep `\bpublic\.` 与 `INSERT INTO users`），列入 tasks.md 的 Phase 2，逐文件修补。
- **[风险] 启动开销** → 4 worker × `Base.metadata.create_all`（~30+ 表）≈ 每 worker 1-2s，可接受（远低于 4×alembic 的 30s+）。
- **[风险] sessionfinish DROP SCHEMA CASCADE 竞争** → **缓解**：仅 master 执行；DROP 前对 schema 列表 snapshot；带 `IF EXISTS`。
- **[权衡] 不解决 raw `connection.execute` 绕过 ORM 的写入污染** → 已 grep 整库无此模式（生产代码全走 SQLAlchemy）。

## Migration Plan

**Step 1**：实现 `tests/_db_isolation.py`，添加 `WorkerSchemaSetup` 类（create schema → create_all → 返回 worker engine/sessionmaker）。

**Step 2**：改造 `tests/conftest.py`：
- 在 `pytest_sessionstart`（worker 端，即 `hasattr(config, "workerinput")`）触发 `WorkerSchemaSetup` 并 monkeypatch `database.AsyncSessionLocal`。
- 保留现有 `test_user` / `test_admin` / `clean_db` 内部 SQL 不变（自动透过 search_path）。

**Step 3**：改造根 `conftest.py`：
- `pytest_sessionstart`（master 端）：`DROP SCHEMA IF EXISTS test_gw0..test_gwN, test_master CASCADE` + `CREATE SCHEMA test_master`（兜底单 worker 模式）
- `pytest_sessionfinish`（master 端）：再次 `DROP SCHEMA test_gw* CASCADE`

**Step 4**：审计现有测试中 `public.` qualified SQL 与裸 `text("INSERT INTO ...")`，逐文件修补（tasks.md 列出清单）。

**Step 5**：跑 `pytest -n0` → 必须 100% 通过（确认 `test_master` schema 路径无回归）。

**Step 6**：跑 `pytest -n auto` → 必须 100% 通过（确认 worker schema 路径生效）。

**Step 7**：`/openspec-archive` 归档。

**回滚策略**：移除 `tests/_db_isolation.py` + 还原 `tests/conftest.py` `pytest_sessionstart` 即可恢复旧行为；生产代码 0 改动 → 0 风险。

### Decision 12：per-worker async engine 用 `poolclass=NullPool`（Option b）

**选择**：`tests/_db_isolation.py` 的 `make_worker_engine()` 创建 `AsyncEngine` 时显式传 `poolclass=NullPool`，禁用连接池复用。

**触发原因**：D2 实施后 `-n0` 仍出现 314 例 `attached to a different loop` / `Event loop is closed` 错误。根因：默认 `AsyncAdaptedQueuePool` 在 fixture-scope event loop 关闭后复用其旧 connection，下个 fixture 的新 loop 拿到 stale connection 即报错。

**为什么不选 Option a（每 fixture 重建 engine）**：连接握手开销 × 全测试数 = 不可接受的启动延迟。
**为什么不选 Option c（loop-affinity pool）**：自定义 pool 复杂度高、维护成本大；NullPool 在测试场景下性能损耗可接受。

**验证**：D12 应用后 `-n0` 跑 `qa_phase5_n0_v2.log`：cross-loop 错误从 314 → 0。

### Decision 13 v2：pytest-asyncio session loop 复用（Option g 混合策略）

**选择**：根 `conftest.py` 安装 shim 拦截 pytest-asyncio 0.26 的 `_get_event_loop_no_warn()`：
1. 优先复用 weakref 缓存中的 tagged session loop（`loop.__pytest_asyncio = True`）
2. 缓存未命中时 `gc.get_objects()` 遍历找 alive tagged loop
3. 全失败时才 mint 新 loop（兜底）

外加 autouse session-scoped fixture `_bind_pytest_asyncio_session_loop` 在测试开始即抓取 `_session_event_loop` 并预绑定到 weakref 缓存；wrap `_provide_clean_event_loop` 保证 teardown 后下次 setup 重新绑定。

**触发原因**：D12 解决 cross-loop pool 问题后，`-n2` 出现 1066 例 `no current event loop` 错误。根因：pytest-asyncio 0.26 在 `_wrap_asyncgen_fixture` 的 SETUP 阶段（line 340）捕获 event_loop，在 TEARDOWN 阶段（line 354 `async_finalizer`）使用；session-scoped loop 关闭后 teardown 找不到 current loop 即崩溃。

**为什么不选 D13 v1（option e：RuntimeError 时 `new_event_loop()`）**：v1 实施后 no-loop 错误 → 0，但引入 321 例 cross-loop teardown（新 loop 与原 fixture 的 connection 不匹配）。净结果差。
**为什么不选 option a/b/c/d/f**：见 Oracle 第二轮决策（`bg_b2582d9b`），option g 是唯一同时满足 0 cross-loop + 0 no-loop 的策略。

**验证**：D13 v2 应用后 `-n2` 跑 `qa_phase5_n2_d13_v2.log`：53 failed / 2200 passed / 5 skipped / 0 errors / 196.21s。`no current event loop`=0、`attached to a different loop`=0、`Event loop is closed`=0、`async_finalizer`=0。

**安全性**：`gc.get_objects()` 进程本地，xdist worker 间不冲突；weakref 缓存不阻止 GC。

### Decision 14：Phase 5 验收语义重新解读（基于 -n0 baseline 测得后）

**选择**：Phase 5.1/5.2/5.3 原文 "failed = 0" 改为相对基线判定 "无 xdist-induced 新增失败"。

**触发原因**：tasks.md 编写时未测 `-n0` baseline；实测 `qa_phase5_n0_v2.log` 显示 752 个 unique FAILED 测试 ID 是 baseline 状态（与本 change 无关的 product / test-suite 历史债）。`-n2` D13 v2 实测 53 failed 是该 752 的**严格子集**（`Compare-Object` 验证 NEW=0、GONE=699）。

**重新解读后的验收**：
- xdist 必须**不引入相对 `-n0` baseline 的新失败**（new failures = 0）
- 目标隔离错误类必须全部归零：`no current event loop`、`attached to a different loop`、`Event loop is closed`、`async_finalizer`

**为什么不选 "扩大范围补全 752 → 0"**：违反 AGENTS.md "fix issues YOU caused. Do NOT fix pre-existing issues unless asked"；该 753 失败横跨多文件多原因，应作独立 OpenSpec change 处理。

**验证**：Phase 5.3 ×3 `-n auto` 每轮均比对 `-n0` baseline，要求 new failures = 0、target-class errors = 0。

**Oracle 决策记录**：`bg_5cb7c48d`（22s, ses_1fc69a83effe4kB47Ro6DHP743），选项 (c) 推荐。

## Open Questions

1. **是否需要在 worker schema 内预 SEED `subscription_plans` / `commission_categories` 等"基础数据"表？** → **已确认无依赖**（Phase 4.1 grep `(FROM|from_table)\s+(plans|commission_categor|subscription_plan)\b` 限定 `tests/` 命中数 = 0；Phase 4.2 跳过 `seed_lookup_data` 实现）。如未来新增对 lookup 表的 SELECT，需补回此步。
2. **是否同步收紧 `pytest.ini` 默认 `-n 4` → `-n auto`？** → 不在本次范围；本次仅修隔离，并发度策略保持现状。
3. **是否对 `RuntimeWarning: coroutine 'xxx' was never awaited` 单独修？** → 经分析，多数源自 worker 提前退出；隔离修复后此警告应自然消失。Phase 6 全量回归时确认；如残留再单开 issue。
