# Design: fix-preexisting-test-failures

## Context

`fix-pytest-xdist-isolation` 已于 D7~D14 阶段彻底修复 pytest-xdist worker 间的事件循环 / 数据库 schema / 引擎缓存隔离问题(详见同名 change 的 design.md)。修复后的 `qa_phase5_n0_v3.log`(`pytest -n0`,2026-05-08)给出权威基线:

```
64 failed / 2189 passed / 5 skipped
```

64 例失败按文件分布(权威清单 `qa_failures_64.txt`):

| 失败数 | 测试文件 | 涉及 Test 类 / 关键字 |
|---|---|---|
| 26 | `tests/test_api_routes.py` | `TestAdminAPI`, `TestAuthAPI`, `TestLogisticsAPI`, `TestOrdersAPI`, `TestProductsAPI` |
| 16 | `tests/test_xlsx_import.py` | China Post xlsx 解析、列映射、容错 |
| 11 | `tests/test_api_routes2.py` | `TestPricingAPI`, `TestStatisticsAPI`, `TestSubscriptionsAPI` |
| 4 | `tests/test_logistics_pool_import_limit.py` | Free / Efficiency / Professional 导入额度 |
| 3 | `tests/test_integration_logistics_products.py` | 批量删除、列表过滤集成路径 |
| 2 | `tests/test_db_users.py` | `users.username_lower` 唯一索引 |
| 1 | `tests/test_db_logistics_pool.py::test_upsert_pool_item_updates_existing_row_in_place` | 已知 `assert 2 == 1` 测试 bug |
| 1 | `tests/test_api_logistics_pool_batch_add.py::test_batch_add_integrity_error_isolated` | 批量插入冲突隔离 |

这些失败长期被早期 event-loop 噪声掩盖,导致回归套件持续红/黄,无法作为质量阀门;`add-pro-trial-overflow` Phase 8.1(`零失败零警告`)亦因此被卡。

## Goals

- 将 `pytest -n0` 与 `pytest -n auto` 的失败数同时降至 **0**(warnings 同步降至 0)
- 每例失败先经过 **"测试 bug vs 生产 bug"** 二分诊断,再决定修复点
- 任何对 production 代码的改动 **必须** 附 Priority 1-4 注释 justification 并独立 commit
- 把"严格绿基线"沉淀为可机器验证的 spec(capability `test-quality-baseline`),避免后续回退
- 解锁 `add-pro-trial-overflow` Phase 8.1 + 8.2 + 8.6,推进其归档

## Non-Goals

- 不重构受影响的 production 模块(只做最小修复;大规模重构走独立 change)
- 不引入新依赖(pytest-timeout 已在 `fix-pytest-xdist-isolation` 中引入)
- 不变更 CI / 部署 / 数据库迁移
- 不扩大测试覆盖率(只让现有测试绿,不新增 happy path 测试)
- 不修复非本批 64 例失败之外的"潜在脆弱点"(出现新失败时另开 change)

## Decisions

### D1. 三段式诊断协议(每例失败必走)

每例失败按以下顺序分类,**禁止跳步**:

1. **复现**:`pytest -n0 <node-id> -x --tb=long --no-header` 在 `test_master` schema 下复现失败,记录完整 traceback
2. **二分诊断**(产出 1 行结论 + 1 段证据):
   - **测试 bug**:测试期望与生产代码当前**正确**行为不符(常见:fixture 数据陈旧、断言写死过期常量、忘记 await、忘记清理)。修复路径 = 仅改 `tests/`
   - **生产 bug**:生产代码行为违反 spec / 用户预期 / 一致性。修复路径 = 改生产代码 + 附 Priority 1-4 注释 + 独立 commit;若触达业务 capability,需在本 change 的 specs 中追加 MODIFIED Requirements
3. **修复 + 单测重跑**:`pytest -n0 <node-id>` 单测绿;再 `pytest -n0 <file>` 同文件全绿

### D2. Priority 1-4 注释 justification 标准(production 改动专用)

任何 production 代码改动若需要新增/修改注释或 docstring,必须以以下任一 Priority 开头:

- **P1 业务正确性**:修复用户可见的错误结果(金额、单位、订单状态)
- **P2 数据完整性**:修复 DB 数据被错误写入/读出的问题(类型、约束、时区)
- **P3 安全 / 权限**:修复鉴权 / SQL 注入 / 越权类问题
- **P4 兼容性**:修复跨 worker / 跨 Python 版本 / 跨 PG 版本不一致

不属于以上任一项 → 不允许添加新注释/docstring;若需修代码本身,直接 inline 修改不附注释。

### D3. 修复顺序(按文件,非按 Test 类)

按失败数从大到小、按文件聚簇修(loadscope 友好):

1. `tests/test_api_routes.py`(26)
2. `tests/test_xlsx_import.py`(16)
3. `tests/test_api_routes2.py`(11)
4. `tests/test_logistics_pool_import_limit.py`(4)
5. `tests/test_integration_logistics_products.py`(3)
6. `tests/test_db_users.py`(2)
7. `tests/test_db_logistics_pool.py`(1)
8. `tests/test_api_logistics_pool_batch_add.py`(1)

每完成一个文件:`pytest -n0 <file>` 必须 0 failed/0 warnings 才算关闭。

### D4. 中间态 QA 阀门

每个文件修复结束 → 跑 `pytest -n0 <file>` 与 `pytest -n auto <file>` 双跑必须一致绿。所有 8 个文件全部绿后,跑两次 **全量** 验收:

- `pytest -n0` → 0 failed / warnings ≤ baseline(写入 `qa_phase9_n0.log`)
- `pytest -n auto` → 0 failed / warnings ≤ baseline(写入 `qa_phase9_nauto.log`)

任一不通过 → 该 change 不能归档。

> **D4 修订(2026-05-08,Oracle 决策授权范围):** 原文写的 "0 warnings" 在执行 Phase 9 时发现剩余 12 例全部是**生产代码的 pre-existing DeprecationWarning**(`datetime.utcnow` × 11 + FastAPI 库本身 `HTTP_422_UNPROCESSABLE_ENTITY` × 1),由 Python 3.12 / FastAPI 升级引入,**非本 change 造成**。按 AGENTS.md "fix issues YOU caused. Do NOT fix pre-existing issues unless asked",这 12 例划归新 OpenSpec change `fix-deprecation-warnings` 单独修复(用户决策)。本 change 验收标准修订为:**failed=0 + warnings ≤ 16(baseline)** ,实际值 12 ≤ 16 ✓。

### D5. Out-of-Scope flaky 文档化协议

如果某例失败 **确属** 环境/外部依赖/时序竞争且 30 分钟内无法稳定修复,允许用 `@pytest.mark.skip(reason="<flaky-reason>; tracked in <new-issue>")` 跳过,但必须:

1. 在 `tasks.md` 对应任务标 `[~]`(skip 而非 `[x]`)并写明 reason
2. 在新 issue / 新 change 中记录后续修复路径
3. 全量 `0 failed` 计算时,skipped 不算失败但需在最终报告里列出

最多允许 **2 例** out-of-scope skip,超过则本 change 不能归档(必须先消化才能 ship)。

### D6. 不改测试 fixture 公共基础设施

本 change 严禁修改:

- `tests/_db_isolation.py`
- `tests/conftest.py` 中的 worker schema 安装逻辑
- 根 `conftest.py` 的 D13 v2 event-loop 机制

如发现以上模块需要修复,意味着 `fix-pytest-xdist-isolation` 未真正完成 → 中止本 change,回到 isolation change 修补再继续。

## Risks

| 风险 | 等级 | 缓解 |
|---|---|---|
| 修测试时不小心遮蔽真实生产 bug | 高 | D1 三段诊断强制二分;D2 production 改动需注释 justification;Oracle review 任何"修生产"决策 |
| 单 worker 绿但并行红 | 中 | D4 双跑 QA 阀门;失败立即触发 isolation change 回炉(D6) |
| 修复 A 文件破坏 B 文件 | 中 | 每文件结束后跑 `-n0 <file>` + 全量 smoke `-n0 -k "smoke"`(若有) |
| out-of-scope skip 失控膨胀 | 中 | D5 硬上限 2 例;超过中止 change |
| production 改动引入回归 | 高 | 任何 production 改动独立 commit + Oracle review + 全量回归再确认 |
| 64 例中混杂 isolation 残留 | 中 | D6 红线;一旦发现回 isolation change |

## Migration

- 不涉及数据库迁移
- 不涉及部署变更
- 不涉及前端变更
- 仅 `tests/` 子集改动 + 极少数 production 模块修复

## Open Questions

1. `tests/test_xlsx_import.py` 的 16 例是否全部由测试侧 fixture 数据陈旧引起?如果发现 China Post xlsx 解析模块本身有 bug(如列名大小写、空白容错),是否触达 `xlsx-import` capability?
   - **决策点**:遇到首例生产 bug 时即时 ask 用户(若不存在 capability,则在本 change 中以 MODIFIED Requirements 形式补 spec)
2. `tests/test_db_logistics_pool.py::test_upsert_pool_item_updates_existing_row_in_place::assert 2 == 1` 是已知测试 bug 还是真实 upsert 行为变化?
   - **决策点**:D1 复现后 1 行结论;若是测试 bug 直接改测试
3. 全量 `pytest -n auto` 通过后,是否同时清零 deprecation warnings?
   - **决策点**:warnings 0 已写入 D4;若发现 warnings 需要改 production 才能消除,走 D2 注释 justification

### D15. D5 澄清:已退役 fixture 的测试归类(Oracle bg_c1b01e6b 决策)

D5 的 "out-of-scope skip 上限 2 例" 仅适用于 **环境/外部依赖/时序竞争** 类 flaky。本附录澄清另一类边界:**测试所依赖的 fixture(数据文件、xlsx、固定常量等)已被业务/产品决策正式退役**。

#### 适用范围

仅当满足全部 3 条:

1. fixture 由用户明确声明退役(本场景:用户明文 "旧版 China Post 14-行 和 `HELP_ePacket_AM_AZ_UZ` 已经弃用了。现在只需要适配 `30_04_26` 就行了")
2. 该测试的断言路径在新 fixture 中**不可达**(parser 分支被新 fixture 数据天然绕过,如 `fee_mode=first_weight` / `volume_mode=longest_side`)
3. 该断言所验证的代码分支已有**等价的单元测试覆盖**(本场景:`xlsx_import.common._parse_size_fields` 等 parser 内部函数已在 unit test 层覆盖)

#### 处理方式:**DELETE,不 skip,不计入 D5 上限**

- 直接从 `tests/*.py` 中物理删除该测试函数
- 不允许使用 `@pytest.mark.skip`(skip 会让"已退役"伪装成"暂时不可达",违反 D1 二分诊断)
- **不计入 D5 的 2 例 skip 上限**(D5 针对 flaky;DELETE 是退役,不是 flaky)
- 必须在 `tasks.md` 对应任务条目追加 1 行 Oracle 决策引用 + 删除原因

#### 本 change 的实例

`tests/test_xlsx_import.py` 中 4 例(`test_china_post_conditional_volume_eems`、`test_china_post_eems_size_standard1`、`test_china_post_first_weight_mode_eparcel`、`test_china_post_first_weight_mode_eems`)已按本附录 DELETE。Oracle bg_c1b01e6b Option E3 决策。Per-file gate `pytest -n0 tests/test_xlsx_import.py` = 52 passed in 9.54s。

#### 与 D5 的关系

- D5(skip 上限 2)→ 仍生效,**不变**
- D15(退役 DELETE)→ 与 D5 互斥,本批次未消耗 D5 配额(0/2)

## Decision Log

- D1~D6 由本设计文档定义,任何后续偏离必须在 design.md 追加新 Decision 编号(D7+)
- D15:D5 边界澄清,Oracle bg_c1b01e6b Option E3,2026-05-08
- D4 修订:warnings 验收标准从 "0" 改为 "≤ baseline(16)",pre-existing deprecations 划归新 change `fix-deprecation-warnings`,2026-05-08
