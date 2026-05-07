# Tasks: fix-deprecation-warnings

> 目标:`pytest -n0` 与 `pytest -n auto` 双双 `0 failed / 0 warnings`。
>
> 每个改动遵守 AGENTS.md "Priority 1-4 注释 justification" 与 "fix issues YOU caused" 原则;本 change 用户已显式授权清理 12 例 pre-existing warnings。

## Phase 1: 全量盘点 12 例 warnings

- [x] 1.1 grep `services/`, `db/`, `api/`, `pricing/`, 顶层 `*.py` 中所有 `datetime.utcnow\b` / `datetime.utcfromtimestamp\b`,产出完整清单(预期 ≥ 2 处:`services/password_reset_service.py:79` + `db/statistics.py:114`)
- [x] 1.2 grep `tests/` 中所有 `datetime.utcnow\b` / `datetime.utcfromtimestamp\b`,产出完整清单(已知:`tests/test_password_reset_token_model.py:34`)
- [x] 1.3 确认 FastAPI `HTTP_422_UNPROCESSABLE_ENTITY` deprecation 的 `tests/test_api_security_question.py` 触发栈:确认是 FastAPI 库内部触发,我方代码无 `HTTP_422_UNPROCESSABLE_ENTITY` 引用;若有引用则同步迁移到 `HTTP_422_UNPROCESSABLE_CONTENT`

## Phase 2: 迁移 production datetime API

- [x] 2.1 `services/password_reset_service.py:79` — `datetime.utcnow()` → `datetime.now(datetime.UTC)`;若该值赋给 DB 列 `used_at`(`DateTime` 不带 tz),用 `.replace(tzinfo=None)` 兼容;附 Priority 4 行内注释说明
- [x] 2.2 `db/statistics.py:114` — `datetime.utcfromtimestamp(today_start)` → `datetime.fromtimestamp(today_start, datetime.UTC)`;消费侧若读 naive datetime,同样 `.replace(tzinfo=None)`;附 P4 注释
- [x] 2.3 1.1 grep 出的其它生产文件逐一同步迁移;每文件改完跑 `python -m pytest -n0 <相关测试文件> --tb=short` 0 failed
- [~] 2.4 production 改动 commit:每个文件单独 commit,消息含 `fix(deprecation): migrate datetime.utcnow to datetime.now(UTC) in <module>` 与 P4 justification

## Phase 3: 迁移测试侧 datetime API

- [x] 3.1 `tests/test_password_reset_token_model.py:34` — `datetime.utcnow() + timedelta(seconds=1)` → `datetime.now(datetime.UTC) + timedelta(seconds=1)`(若与 DB 比较需对齐 tzinfo);QA: `pytest -n0 tests/test_password_reset_token_model.py --tb=short` 0 failed
- [x] 3.2 1.2 grep 出的其它测试文件逐一迁移;每改一处跑该文件测试 0 failed

## Phase 4: 处理 FastAPI HTTP_422 deprecation

- [x] 4.1 选定路径(A 升级 FastAPI / B 局部 filterwarnings):若 `requirements.txt` 当前 FastAPI 版本已是最新仍触发,默认走 B;否则走 A
- [~] 4.2 路径 A:`pip install --upgrade fastapi` + `pip freeze | grep fastapi` 更新 `requirements.txt` + 全量回归
- [~] 4.3 路径 B:在 `tests/conftest.py` 或 `tests/test_api_security_question.py` 顶部加 `warnings.filterwarnings("ignore", message=".*HTTP_422_UNPROCESSABLE_ENTITY.*", category=DeprecationWarning)` + P4 注释 + 链接 FastAPI 上游 issue

## Phase 5: 严格阀门验证

- [x] 5.1 `pytest -n0 -W error::DeprecationWarning --tb=short` 全量跑;**any DeprecationWarning fails the build**;若仍 fail 回 Phase 2/3/4 补漏
- [x] 5.2 `pytest -n0 --tb=short 2>&1 | Tee-Object -FilePath qa_dep_n0.log`;summary `0 failed, 0 warnings`
- [x] 5.3 `pytest -n auto --tb=short 2>&1 | Tee-Object -FilePath qa_dep_nauto.log`;summary `0 failed, 0 warnings`
- [x] 5.4 `qa_dep_n0.log` 与 `qa_dep_nauto.log` passed/skipped 数完全一致

## Phase 6: Spec 收紧 + 归档

- [x] 6.1 修改 `specs/test-quality-baseline/spec.md`(MODIFIED):warnings 门槛由 "≤ baseline" 改回 "= 0"(还原 fix-preexisting-test-failures D4 修订)
- [x] 6.2 `openspec validate fix-deprecation-warnings --strict` exit 0
- [ ] 6.3 翻 `add-pro-trial-overflow/tasks.md` Phase 8.1 → `[x]`(此时 "零失败零警告" 真正达成)
- [ ] 6.4 用户 confirm 后:`openspec archive fix-deprecation-warnings`
