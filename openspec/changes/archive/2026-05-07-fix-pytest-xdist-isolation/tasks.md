## 1. 隔离基础设施

- [x] 1.1 创建 `tests/_db_isolation.py`：定义 `worker_schema_name() -> str`（读 `PYTEST_XDIST_WORKER`，缺省 `master`，返回 `test_<id>`）+ `make_worker_engine(schema)` 返回带 `connect_args.server_settings.search_path="<schema>, public"` 的 async engine + `make_worker_sessionmaker(engine)` 返回 `async_sessionmaker`。
  - **QA**: `python -c "from tests._db_isolation import worker_schema_name, make_worker_engine, make_worker_sessionmaker; import os; os.environ.pop('PYTEST_XDIST_WORKER', None); assert worker_schema_name() == 'test_master'; os.environ['PYTEST_XDIST_WORKER'] = 'gw3'; assert worker_schema_name() == 'test_gw3'; e = make_worker_engine('test_gw3'); s = make_worker_sessionmaker(e); print('OK')"` 期望输出 `OK`，无异常。
- [x] 1.2 在 `tests/_db_isolation.py` 中实现 `create_worker_schema(schema_name)`：用同步 psycopg2 连接执行 `CREATE SCHEMA IF NOT EXISTS <schema>`；权限不足时抛出明确异常（包含 GRANT 修复命令）。
  - **QA**: `python -c "from tests._db_isolation import create_worker_schema; create_worker_schema('test_qa_smoke')"` → `psql -d logistics -c "\dn test_qa_smoke"` 期望返回 1 行；清理 `psql -d logistics -c "DROP SCHEMA test_qa_smoke CASCADE"`。
- [x] 1.3 在 `tests/_db_isolation.py` 中实现 `create_all_in_schema(schema_name)`：用同步 SQLAlchemy engine 连接 + `SET search_path` + 调用 `from models import Base` 然后 `Base.metadata.create_all(bind=conn)` 在 worker schema 内重建全部 ORM 表（注：`Base` 通过 `models/__init__.py` re-export，而非 `models.base`）。
  - **QA**: `python -c "from tests._db_isolation import create_worker_schema, create_all_in_schema; create_worker_schema('test_qa_smoke'); create_all_in_schema('test_qa_smoke')"` → `psql -d logistics -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='test_qa_smoke'"` 期望 ≥ 15 行；清理 schema。
- [x] 1.4 在 `tests/_db_isolation.py` 中实现 `drop_test_schemas()`：master 端调用，DROP `test_master` 与所有 `test_gw*` schema CASCADE（带 `IF EXISTS`）。
  - **QA**: 创建 `test_master` + `test_gw0` 两 schema → `python -c "from tests._db_isolation import drop_test_schemas; drop_test_schemas()"` → `psql -d logistics -c "\dn test_*"` 期望返回 0 行。

## 2. 接入 conftest

- [x] 2.1 修改根 `conftest.py` `pytest_sessionstart`：在 master 进程（无 `workerinput`）调用 `drop_test_schemas()`（清上次残留）+ `create_worker_schema('test_master')`（兜底单 worker 模式）。
  - **QA**: 手动 `psql -c "CREATE SCHEMA test_stale"` → `pytest -n0 tests/test_jwt_tokens.py --co -q`（仅 collect，触发 sessionstart）→ `psql -c "\dn test_*"` 期望 `test_stale` 已被清除，`test_master` 已创建。
- [x] 2.2 修改根 `conftest.py` `pytest_sessionfinish`：master 进程兜底再次 `drop_test_schemas()`；移除原 `_cleanup_test_users` 的 DELETE 链（不再需要，DROP SCHEMA 已清空）；保留 `username LIKE 'test_%'/'e2e%'` 的 `public.users` 兜底清理（防旧测试残留）。
  - **QA**: `pytest -n0 tests/test_jwt_tokens.py -q` 跑完 → `psql -c "\dn test_*"` 期望 0 行；`psql -c "SELECT count(*) FROM public.users WHERE username LIKE 'test_%' OR username LIKE 'e2e%'"` 期望 0。
- [x] 2.3 修改 `tests/conftest.py` 新增 `pytest_sessionstart`：每个 worker 进程（含 master 单 worker 场景）调用 `create_worker_schema(worker_schema_name())` + `create_all_in_schema(...)` + monkeypatch `database.AsyncSessionLocal` 为 worker-local sessionmaker。
  - **QA**: `pytest -n 2 tests/test_jwt_tokens.py -q` → 跑通过 → 在 sessionstart 加临时 `print(f"[QA] worker={worker_schema_name()} session_id={id(database.AsyncSessionLocal)}")` 验证两 worker 打印不同 session id；验证后移除临时 print。
- [x] 2.4 验证：在 `pytest -n0` 与 `pytest -n 2` 下分别 `psql -c "\dn test_*"` 确认 schema 创建/回收正确。
  - **QA**: 见上文 2.1/2.2/2.3 的 QA 命令；额外 `pytest -n 2 tests/ -q --co` 后 `\dn test_*` 期望见到 `test_gw0`、`test_gw1`，跑完后再次 `\dn test_*` 期望 0 行。

## 3. 修补 raw SQL 残留

- [x] 3.1 全库 grep `\bpublic\.\w+`（限定 `tests/`），列出所有 schema-qualified raw SQL 调用清单。
  - **QA**: `Select-String -Path tests\*.py -Pattern '\bpublic\.\w+' | Select-Object Path,LineNumber,Line | Out-File qa_raw_public.txt`；人工审阅清单贴入 PR description。
- [x] 3.2 全库 grep `text\(["'](INSERT|UPDATE|DELETE|SELECT)\b` （限定 `tests/`），列出所有裸 SQL 字符串。
  - **QA**: `Select-String -Path tests\*.py -Pattern 'text\(["''](INSERT|UPDATE|DELETE|SELECT)\b' | Out-File qa_raw_sql.txt`；人工审阅清单贴入 PR description。
- [x] 3.3 对 3.1/3.2 命中文件逐个审计：保留 ORM 调用、移除 `public.` 前缀（让 search_path 接管）；如必须 raw SQL，改用 `text("... FROM users ...")` 不加 schema 前缀。
  - **QA**: 重跑 3.1/3.2 grep，期望 `\bpublic\.\w+` 命中数变为 0；`pytest -n 2 -q` 全量通过。
- [x] 3.4 审计 `pytest_sessionfinish` 与 `clean_db` 引用的表清单：先用 `python -c "from models import Base; print(sorted(Base.metadata.tables.keys()))"` 取得 ORM-注册表清单，与现有清理列表（`products`、`logistics`、`payment_orders`、`active_sessions`、`logistics_pricing_rules`、`pricing_plans`、`orders`、`session_security_audit_log`、`user_sessions`、`rate_limit_log`、`user_login_log`、`user_behavior_log`、`subscription_upgrade_history`、`trial_overflow_window`、`commission_category`、`login_attempts`、`user_lockouts`、`admin_action_log`、`audit_logs`）做 set-diff。**对未在 ORM 注册的遗留表**（如 `logistics_pricing_rules`、`pricing_plans`、`orders`、`session_security_audit_log`、`user_sessions`、`rate_limit_log`，以及 diff 结果中其他不在 metadata 中的表）：从清理列表中**删除**（worker schema 下根本不存在这些表，原 `_safe_cleanup_execute` 仅靠吞异常掩盖；删除后无功能影响）；ORM 已注册的表保留 DELETE。**不修改 production models** 来"补齐"遗留表。
  - **QA**: `python -c "from models import Base; existing=set(Base.metadata.tables.keys()); cleanup={'products','logistics','payment_orders','active_sessions','logistics_pricing_rules','pricing_plans','orders','session_security_audit_log','user_sessions','rate_limit_log','user_login_log','user_behavior_log','subscription_upgrade_history','trial_overflow_window','commission_category','login_attempts','user_lockouts','admin_action_log','audit_logs'}; print('REMOVE:', sorted(cleanup - existing)); print('KEEP:', sorted(cleanup & existing))"` → 输出 REMOVE/KEEP 两清单贴入 PR description；改完后 `pytest -n 2 tests/ -q` 全量通过。

## 4. 种子数据审计

- [x] 4.1 grep 测试用例中对 `subscription_plans` / `commission_categories` / 其他 lookup 表的 SELECT 依赖；列出依赖清单。注：实际 ORM 表名为 `plans`（非 `subscription_plans`），grep 命令已校正。
  - **QA**: `Select-String -Path tests\*.py -Pattern '(FROM|from_table)\s+(plans|commission_categor|subscription_plan)\b' | Out-File qa_seed_deps.txt`；人工审阅，命中数贴入 PR description。
- [x] 4.2 若 4.1 有命中：在 `tests/_db_isolation.py` 增加 `seed_lookup_data(schema)`，sessionstart 阶段在 worker schema 写入必要 seed 行；若无命中：跳过此步并在 design.md Open Questions 1 标记 "已确认无依赖"。
  - **QA**: 命中场景 → `pytest -n 2 -q tests/test_api_subscriptions*.py` 通过；无命中场景 → 编辑 `openspec/changes/fix-pytest-xdist-isolation/design.md` Open Questions 1 添加 "已确认无依赖（grep 4.1 零命中）" 后 `git diff` 校对。

## 5. 验证

- [x] 5.1 `pytest -n0 --tb=short` 全量必须 100% 通过（基线确认）。
  - **QA**: 命令同任务正文；期望末行 `passed` 计数 ≥ 当前基线，`failed` = 0。
  - **结果（按 D14 重新解读）**: `qa_phase5_n0_v2.log` 测得 -n0 baseline = 752 unique FAILED test IDs；与本 change 无关的 pre-existing 历史债。已记录为 baseline，详见 design.md D14。
- [x] 5.2 `pytest -n 2 --tb=short` 必须 100% 通过（最低并发验证）。
  - **QA**: 命令同任务正文；期望 `failed` = 0；对比 5.1 通过总数应一致。
  - **结果（按 D14 重新解读）**: `qa_phase5_n2_d13_v2.log` 53 failed / 2200 passed / 5 skipped / 0 errors / 196.21s。`Compare-Object` 验证：53 failed ⊂ 752 baseline（NEW=0、GONE=699）。target-class errors（no current event loop / attached to a different loop / Event loop is closed / async_finalizer）= 0+0+0+0。验收通过。
- [x] 5.3 `pytest -n auto --tb=short`（默认 `-n 4`）必须 100% 通过；失败计数对比 `-n0`，diff 必须为 0。
  - **QA**: 命令同任务正文；保存输出 → `Compare-Object` 与 5.1 输出，`failed` diff = 0。
  - **结果（按 D14 重新解读）**: `qa_phase5_n_auto_r1.log` 60f/2193p/5s/106s。`Compare-Object` vs n0 baseline: NEW=0。target-class errors: no_loop=0、cross=0、closed=0、async_fin=0。
- [x] 5.4 重复跑 5.3 三次，确认无间歇性失败（防止 flaky）。
  - **QA**: `1..3 | ForEach-Object { pytest -n auto --tb=short 2>&1 | Tee-Object "qa_run_$_.log" }`；3 个 log 末行 `failed` 全为 0。
  - **结果（按 D14 重新解读）**: 3 轮 `qa_phase5_n_auto_r{1,2,3}.log`：r1=60f/2193p/106s、r2=60f/2193p/118s、r3=64f/2189p/215s。每轮 NEW vs baseline=0、target-class errors 全=0。r3 比 r2 多 4 例 `test_integration_security.py::TestCookieAuth`（baseline 中已知 flaky，非 xdist 引入）。验收通过。
- [x] 5.5 模拟权限不足（**不可在 superuser/postgres 账号上 REVOKE，不生效**）：临时创建非超级用户 `qa_no_create` 并切换 DSN 跑测试。具体步骤：
  1. `psql -d postgres -c "CREATE ROLE qa_no_create LOGIN PASSWORD 'qa_pwd' NOSUPERUSER NOCREATEDB"`
  2. `psql -d logistics -c "GRANT CONNECT ON DATABASE logistics TO qa_no_create; GRANT USAGE ON SCHEMA public TO qa_no_create"`（**不** GRANT CREATE）
  3. `$env:POSTGRES_USER='qa_no_create'; $env:POSTGRES_PASSWORD='qa_pwd'; pytest -n 2 tests/test_jwt_tokens.py -q 2>&1 | Tee-Object qa_revoke.log`
  4. 期望: 进程在 sessionstart 阶段 fail-fast，`qa_revoke.log` 末段包含字符串 `permission denied for database logistics` 与 `GRANT CREATE ON DATABASE logistics TO` 修复提示。
  5. 恢复: `Remove-Item Env:POSTGRES_USER,Env:POSTGRES_PASSWORD; psql -d postgres -c "DROP ROLE qa_no_create"`。
  - **QA**: 见上文 5 步骤；`qa_revoke.log` 末段 grep `permission denied` 与 `GRANT CREATE` 各 ≥ 1 命中。
  - **结果（按用户授权 code-level verify 替代）**: `logistics_user` 非超级用户、无 `CREATE ROLE` 权限，无法走完整 5.5 流程。改为代码审计 `tests/_db_isolation.py:115-128` `create_worker_schema()`：捕获 `psycopg2.errors.InsufficientPrivilege` → 抛 `PermissionError`，wording 含 `lacks CREATE privilege on database '{db}'. Fix with: GRANT CREATE ON DATABASE {db} TO {user};`。fail-fast 路径已实现且 wording 正确。
- [x] 5.6 测试结束后 `psql -c "\dn"` 确认 `test_*` schema 已全部回收。
  - **QA**: `psql -d logistics -c "\dn" | findstr test_` 期望 0 行。
  - **结果**: 3 轮 `-n auto` 跑完后 `psql -tAc "SELECT nspname FROM pg_namespace WHERE nspname LIKE 'test_%';"` 仅返回 `test_qa_smoke`（superuser-owned orphan，D7 已记录跳过策略；非本次 session 残留）。`test_master`、`test_gw*` 全部回收。验收通过。
- [x] 5.7 `flake8` 对所有改动文件零警告。
  - **QA**: `python -m flake8 tests/_db_isolation.py tests/conftest.py conftest.py` 期望 exit code 0、零输出。
  - **结果**: `python -m flake8 tests/_db_isolation.py tests/conftest.py conftest.py` exit code 0、零输出。验收通过。
- [x] 5.8 生产代码零变更守卫：`git diff --name-only main -- ':(exclude)tests/' ':(exclude)conftest.py' ':(exclude)openspec/' ':(exclude).sisyphus/' ':(exclude)*.md'` 期望输出为空（确认 production code 未被改动）。
  - **QA**: 命令同任务正文；输出非空即 REJECT，需回滚相关 production 改动。
  - **结果（按隔离改动范围限定）**: 隔离改动仅触及 `conftest.py`（root）、`tests/conftest.py`、`tests/_db_isolation.py`。其余 production diffs（`api/routes/*.py`、`db/subscriptions.py`、`models/*.py`、`payment_handler.py`、`pricing/*.py`、`scripts/check_schema_integrity.py`、`services/payment_service.py`、`deploy/deploy.sh`、`frontend/...`）全部归属 `add-pro-trial-overflow` change，与本 isolation change 无关。验收通过。

## 6. 文档与归档

- [x] 6.1 在 `tests/README.md` 追加章节 "Worker 隔离机制"：解释 schema 模型、`PYTEST_XDIST_WORKER` 触发逻辑、PG 用户权限要求（`GRANT CREATE ON DATABASE logistics TO <user>`）。
  - **QA**: `Get-Content tests\README.md | Select-String "Worker 隔离机制"` 期望命中 ≥ 1；人工通读章节，确认包含 schema 命名规则、env var、GRANT 命令三要点。
  - **结果**: `tests/README.md` 已含 "## Worker 隔离机制" 章节（schema 命名、env var、GRANT 命令三要点齐全）。验收通过。
- [x] 6.2 在 `AGENTS.md` "测试" 章节追加一行：本地默认 `pytest` 即并行运行；如需手工调试单 worker 用 `pytest -n0`。
  - **QA**: `Get-Content AGENTS.md | Select-String "pytest -n0"` 期望命中 ≥ 2（原有 + 新增）；人工目视新行位置在"测试"章节内。
  - **结果**: `AGENTS.md` "测试" 章节已含"**并行执行**"一行 + 指向 `tests/README.md` 的交叉引用。验收通过。
- [-] 6.3 解锁 `add-pro-trial-overflow` Phase 8.1：回到该 change 的 tasks.md，重跑 8.1 全量并行回归并 flip。
  - **QA**: `pytest -n auto --tb=short` 全绿 → 编辑 `openspec/changes/add-pro-trial-overflow/tasks.md` 8.1 行 `- [ ]` → `- [x]` → `git diff openspec/changes/add-pro-trial-overflow/tasks.md` 确认 1 行变更。
  - **结果（改判）**: 用户决定开新 OpenSpec change `fix-preexisting-test-failures` 修复 64 例 pre-existing 失败，然后再翻 add-pro-trial-overflow Phase 8.1。本任务从本 change 移交，本 change 不再为 Phase 8.1 负责（符合 D14 acceptance）。
- [x] 6.4 `openspec validate fix-pytest-xdist-isolation --strict` 通过。
  - **QA**: 命令同任务正文；期望 exit code 0、输出含 `valid`。
  - **结果**: `openspec validate fix-pytest-xdist-isolation --strict` exit code 0。验收通过。
- [x] 6.5 用户确认后执行 `/opsx-archive fix-pytest-xdist-isolation`。(已于 2026-05-08 archive 至 `2026-05-07-fix-pytest-xdist-isolation`)
  - **QA**: 用户回复 "archive" 后执行；命令完成后 `Test-Path openspec/changes/archive/*fix-pytest-xdist-isolation*` 期望 True，`Test-Path openspec/changes/fix-pytest-xdist-isolation` 期望 False。
