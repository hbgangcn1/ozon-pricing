# test-isolation Specification

## Purpose
TBD - created by archiving change fix-pytest-xdist-isolation. Update Purpose after archive.
## Requirements
### Requirement: Worker-scoped database schema isolation

测试运行时，每个 pytest-xdist worker SHALL 拥有独占的 PostgreSQL schema（命名 `test_<worker_id>`，例如 `test_gw0`、`test_gw1`、`test_master`），所有 ORM 写入与查询 SHALL 通过 `search_path` 自动定位到该 worker schema 而无需测试代码显式限定。Worker 之间互不可见。

#### Scenario: 并行 worker 创建相同 username 不冲突
- **WHEN** worker `gw0` 与 worker `gw1` 同一时刻分别在自己 schema 内 INSERT 一行 `users(username='test_x', is_test_user=1)`
- **THEN** 两次 INSERT 都成功（不同 schema 无 unique 冲突），且 worker `gw0` 的后续 `SELECT * FROM users WHERE username='test_x'` 仅返回自己创建的那一行（不可见 worker `gw1` 的行）

#### Scenario: clean_db fixture 不影响其他 worker
- **WHEN** worker `gw0` 触发 `clean_db` fixture 的 `DELETE FROM users WHERE is_test_user=1`
- **THEN** worker `gw1` 的 schema 内已存在的 `is_test_user=1` 行 SHALL 不被删除，worker `gw1` 后续 SELECT 返回原行

#### Scenario: 单 worker 模式（pytest -n0）走 master schema
- **WHEN** 开发者执行 `pytest -n0`（环境变量 `PYTEST_XDIST_WORKER` 不存在）
- **THEN** 系统 SHALL 创建并使用 `test_master` schema，而非污染生产 `public` schema

### Requirement: Worker schema 自动创建与回收

xdist master 进程 SHALL 在 `pytest_sessionstart` 阶段对所有预期 worker schema 执行 `DROP SCHEMA IF EXISTS ... CASCADE` + `CREATE SCHEMA`；每个 worker 进程 SHALL 在自身 `pytest_sessionstart` 阶段在已存在的 schema 内通过 `Base.metadata.create_all` 重建全部 ORM 表。Master 进程 SHALL 在 `pytest_sessionfinish` 阶段执行 `DROP SCHEMA test_gw* CASCADE` + `DROP SCHEMA test_master CASCADE` 兜底回收。

#### Scenario: 测试套件正常退出后 schema 全部回收
- **WHEN** `pytest -n 4` 全量正常完成
- **THEN** PostgreSQL 中 SHALL 不残留任何以 `test_` 开头的 schema（除 `public` 外）

#### Scenario: 上一次崩溃残留的 schema 在下次启动时被清空
- **GIVEN** PostgreSQL 中残留 `test_gw0` schema（包含上次崩溃留下的脏数据）
- **WHEN** 开发者再次执行 `pytest -n 4`
- **THEN** master 进程 SHALL 在新 worker 启动前先 DROP 旧 schema，然后重建为干净 schema；本次测试不受上次脏数据影响

#### Scenario: PG 用户缺少 CREATE SCHEMA 权限时 fail-fast
- **WHEN** 配置的 `POSTGRES_USER` 没有 `CREATE` 权限于 `logistics` 数据库
- **THEN** master 进程 SHALL 在 sessionstart 阶段抛出明确错误（指明缺少 `CREATE` 权限 + 修复命令 `GRANT CREATE ON DATABASE logistics TO <user>`），而非进入测试运行后产生海量混淆失败

### Requirement: 生产代码路径零改动

生产业务代码（`database.py`、`api/`、`db/`、`services/`、`models/`、`pricing/` 等）SHALL 在本次变更后保持字节级与运行时行为完全不变；schema 隔离逻辑 SHALL 仅通过 `tests/` 目录内的代码 + 环境变量 `PYTEST_XDIST_WORKER` 触发。

#### Scenario: 生产部署不触发 schema 切换
- **WHEN** `gunicorn -w 3` 在生产启动 `api.main:app`，环境变量 `PYTEST_XDIST_WORKER` 不存在
- **THEN** `database.AsyncSessionLocal` SHALL 走默认 `public` schema，不创建任何 `test_` schema

#### Scenario: 生产 deploy.sh 不受影响
- **WHEN** 在生产执行 `bash deploy/deploy.sh`
- **THEN** 第 4.2 步 `scripts/check_schema_integrity.py` SHALL 仍然只检查 `public` schema 的 CHECK 不变量，且 deploy 流程 SHALL 不读取任何测试隔离相关代码

### Requirement: 单 worker 与多 worker 行为一致

任何测试在 `pytest -n0` 与 `pytest -n auto` 下的通过/失败结果 SHALL 一致；同一份测试代码 SHALL 不因并发度变化而出现间歇性失败。

#### Scenario: 已修复后全量并行通过率与单 worker 一致
- **GIVEN** `pytest -n0` 当前 100% 通过
- **WHEN** 切换为 `pytest -n auto`（4 worker，loadscope）
- **THEN** 失败用例数 SHALL 为 0（与 `-n0` 一致），不再出现 `assert result is not None` / `cannot unpack non-iterable NoneType` / `coroutine 'xxx' was never awaited` 这三类典型隔离失败模式

#### Scenario: 解锁 add-pro-trial-overflow Phase 8.1 阀门
- **WHEN** `add-pro-trial-overflow` Phase 8.1 执行 `pytest -n auto` 全量回归
- **THEN** 系统 SHALL 报告 `0 failed`，QA 阀门 "全量并行零失败" SHALL 通过

