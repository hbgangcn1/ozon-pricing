## Why

`pytest.ini` 默认 `-n 4 --dist=loadscope`，整套测试 4 个 worker 共享同一个 `logistics` PostgreSQL 数据库；`tests/conftest.py` 的 `test_user` / `test_admin` / `clean_db` fixture 对全局 `is_test_user=1` 行做无范围的 COMMIT + DELETE，worker 之间互相清空对方的数据，全量并行运行出现 ~243/2254 测试失败（典型症状：`assert result is not None`、`TypeError: cannot unpack non-iterable NoneType`、`RuntimeWarning: coroutine 'xxx' was never awaited`），同样测试在 `-n0` 顺序模式 100% 通过。这导致 `add-pro-trial-overflow` Phase 8.1 "全量并行零失败" QA 阀门无法通过，必须先修。

## What Changes

- **新增**：xdist worker 启动时按 `worker_id` 创建独占 PostgreSQL schema（如 `test_gw0`、`test_gw1` …），将该 worker 的 SQLAlchemy `engine` 的 `search_path` 限定到该 schema + `public`。
- **新增**：worker-local 的 schema 启动钩子在 schema 内 `CREATE TABLE` 全部 ORM 模型（基于 `Base.metadata.create_all` 复用现网 DDL），保证 worker 间数据物理隔离。
- **修改**：`tests/conftest.py` 的 `test_user`、`test_admin`、`clean_db`、`db_session` 的清理 SQL 仅作用于本 worker 的 schema，移除跨 worker 副作用。
- **修改**：根目录 `conftest.py` 的 `pytest_sessionfinish` 在 master 进程上 `DROP SCHEMA test_gw* CASCADE` 兜底回收。
- **保持**：生产 `database.py` 行为不变；schema 切换仅在测试运行时通过 `PYTEST_XDIST_WORKER` 环境变量触发，生产代码路径 0 改动。
- **保持**：`-n0` 单 worker 仍然走 master schema（兼容当前直接调用 `python -m pytest -n0` 的工作流）。
- **BREAKING（仅测试侧）**：直接对 `public.users` / `public.logistics` 等表做 raw SQL 的旧测试需通过 ORM 或带 schema-qualified 名访问；本次会同步修补涉及 6+ 测试文件中的 raw SQL 残留。

## Capabilities

### New Capabilities
- `test-isolation`：定义 pytest 测试运行时的数据隔离契约——worker 间互不可见、worker 退出时自动回收、生产代码 0 改动、本地 `-n0` 与 CI `-n auto` 行为一致。

### Modified Capabilities
（无；本变更仅影响测试基础设施，不修改任何业务能力的需求。）

## Impact

- **影响代码**：
  - `tests/conftest.py`（重写 4 个 fixture 的清理 SQL；新增 worker-schema 启动夹具）
  - `conftest.py` 根目录（`pytest_sessionstart` 触发 schema 创建；`pytest_sessionfinish` 回收所有 `test_gw*` schema）
  - `database.py`（仅在 `PYTEST_XDIST_WORKER` 存在时注入 `connect_args.server_settings.search_path`，生产路径走 default `public`）
  - 6+ 个 raw SQL 残留的测试文件（具体清单 design.md 列出）
- **影响 API / 数据库 schema**：无生产 schema 变更；测试运行期临时创建 `test_gw0..test_gwN`，运行结束 DROP。
- **影响依赖**：无新增 PyPI 依赖；复用 `pytest-xdist`（已存在）+ `sqlalchemy`（已存在）。
- **影响 CI / 部署**：无；`deploy/deploy.sh` 不跑 pytest，仅跑 alembic + schema-integrity guard。
- **影响开发者工作流**：本地 `pytest -n0` 与 `pytest -n auto` 行为一致；新增一行 README 说明：测试 PostgreSQL 用户需有 `CREATE SCHEMA` 权限（开发机默认 `postgres` 超级用户已满足，CI/E2E 同）。
- **解锁**：`add-pro-trial-overflow` Phase 8.1 全量并行 QA 阀门。
