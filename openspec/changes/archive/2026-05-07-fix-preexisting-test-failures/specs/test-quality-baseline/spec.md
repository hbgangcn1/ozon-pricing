## ADDED Requirements

### Requirement: 全量回归严格绿基线

测试套件 SHALL 在 `pytest -n0` 与 `pytest -n auto` 两种执行模式下同时报告 `0 failed` 与 `0 warnings`;两种模式下的通过/失败结果 SHALL 完全一致(并发等价性)。剩余 explicit out-of-scope flaky 用例 SHALL 通过 `@pytest.mark.skip(reason=...)` 显式跳过并在 tasks.md 中文档化,且总数 SHALL 不超过 2 例。

#### Scenario: 单 worker 模式全绿
- **WHEN** 开发者执行 `pytest -n0`(`PYTEST_XDIST_WORKER` 环境变量不存在)
- **THEN** pytest 退出码 SHALL 为 0,summary line SHALL 包含 `0 failed`,且 SHALL 不出现 `warnings summary` 区段(或区段内 SHALL 显示 `0 warnings`)

#### Scenario: 多 worker 并行模式全绿
- **WHEN** 开发者执行 `pytest -n auto`(默认 `pytest.ini` `addopts` 含 `-n 4 --dist=loadscope`)
- **THEN** pytest 退出码 SHALL 为 0,summary line SHALL 包含 `0 failed`,且 SHALL 不出现 `warnings summary` 区段

#### Scenario: 单/多 worker 结果一致
- **GIVEN** `pytest -n0` 当前 100% 通过
- **WHEN** 切换为 `pytest -n auto`
- **THEN** 失败用例数 SHALL 为 0,且 SHALL 不出现 `assert result is not None` / `cannot unpack non-iterable NoneType` / `coroutine 'xxx' was never awaited` 这三类典型隔离失败模式

#### Scenario: out-of-scope skip 总数受控
- **WHEN** 本 change 归档前的最终全量回归运行结束
- **THEN** `pytest --co -q` 报告的 `@pytest.mark.skip` 装饰用例总数 SHALL 不超过 2 例;每例 SHALL 在 `openspec/changes/fix-preexisting-test-failures/tasks.md` 中以 `[~]` 标记并附 reason 与跟踪链接

### Requirement: 测试 bug 与生产 bug 二分诊断协议

每例失败修复前 SHALL 完成"测试 bug vs 生产 bug"二分诊断,并在对应 tasks.md 任务中记录 1 行结论 + 1 段证据。被分类为"生产 bug"的失败 SHALL 在生产代码中修复;被分类为"测试 bug"的失败 SHALL 仅修改 `tests/` 目录代码。

#### Scenario: 测试 bug 仅改 tests
- **GIVEN** 某例失败被诊断为测试 bug(fixture 数据陈旧 / 断言写死过期常量 / 忘记 await / 忘记清理)
- **WHEN** 修复该例失败
- **THEN** 修复 commit 的 `git diff --name-only` SHALL 仅出现 `tests/` 路径下文件,SHALL 不修改任何 `api/` `db/` `services/` `models/` `pricing/` `security/` 等生产模块

#### Scenario: 生产 bug 修复附 Priority 1-4 注释
- **GIVEN** 某例失败被诊断为生产 bug(违反 spec / 用户预期 / 数据完整性)
- **WHEN** 修复对应生产代码
- **THEN** 若新增/修改任何注释或 docstring,该注释 SHALL 以 `P1 业务正确性` / `P2 数据完整性` / `P3 安全/权限` / `P4 兼容性` 之一开头,且修复 SHALL 独立成一个 commit(不与测试侧改动混合)

#### Scenario: 触达业务 capability 时补 spec
- **GIVEN** 某例生产 bug 修复改变了某业务 capability 已声明的可观察行为
- **WHEN** 修复完成
- **THEN** 本 change 的 `specs/<existing-capability>/spec.md` SHALL 新增 `## MODIFIED Requirements` 区段,描述前后行为差异

### Requirement: 测试隔离基础设施零改动

本 change SHALL 不修改 `tests/_db_isolation.py`、`tests/conftest.py` 中的 worker schema 安装逻辑、根 `conftest.py` 的 D13 v2 event-loop 机制。如发现以上模块需要修复才能让某例失败通过,SHALL 中止本 change 并回到 `fix-pytest-xdist-isolation` change 修补。

#### Scenario: 隔离基础设施文件未被修改
- **WHEN** 本 change 归档前对全部 commit 跑 `git diff main..HEAD --name-only`
- **THEN** 输出 SHALL 不包含 `tests/_db_isolation.py`,SHALL 不包含 `tests/conftest.py` 中的 `_install_worker_schema_isolation` 函数所在行范围的修改,SHALL 不包含根 `conftest.py` 中 `_session_event_loop` / `_make_pytest_asyncio_loop` 相关的修改

#### Scenario: 发现隔离残留时中止并回炉
- **GIVEN** 修复某例失败时观察到 `assert result is not None` / `coroutine was never awaited` / `attached to a different loop` 等典型隔离失败模式
- **WHEN** 修复尝试触达隔离基础设施
- **THEN** 本 change SHALL 立即中止;在 `fix-pytest-xdist-isolation` change 中追加新 Decision (D15+) 与新 Phase 修补;修补完成后再恢复本 change
