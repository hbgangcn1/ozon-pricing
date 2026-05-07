# Change Proposal: fix-deprecation-warnings

## Why

`fix-preexisting-test-failures` 已将 64 例预存失败清零(`pytest -n0` + `pytest -n auto` 双模 0 failed),但残留 12 例 pre-existing `DeprecationWarning`(baseline 16 → 12 是因为前一个 change 删除了 4 个绑定已退役 fixture 的 xlsx 测试)。

这些 warnings 全部来自**生产代码 / FastAPI 库本身**,不属 `fix-preexisting-test-failures` 的造成范围,按 AGENTS.md "fix issues YOU caused. Do NOT fix pre-existing issues unless asked" 原则,在前一个 change 的 D4 修订中明确划归本 change 处理。

清理这 12 例后,`test-quality-baseline` capability 才能真正达到 "0 failed / 0 warnings" 严格阀门,后续任何新 deprecation 一旦出现即被 CI 抓住,防止温水煮青蛙式累积。

## What Changes

### Production 代码改动(共 11 例 `datetime.utcnow` / `utcfromtimestamp`)

- `services/password_reset_service.py:79` — `datetime.utcnow()` → `datetime.now(datetime.UTC)`(P4 兼容性)
- `db/statistics.py:114` — `datetime.utcfromtimestamp(today_start)` → `datetime.fromtimestamp(today_start, datetime.UTC)`(P4 兼容性)
- 任何其它 grep 命中 `datetime.utcnow\|datetime.utcfromtimestamp` 的生产源(含 `db/`, `services/`, `api/`, `pricing/`, 顶层 `*.py`)逐一迁移

### Test 代码改动(已被 warnings 显式标记的)

- `tests/test_password_reset_token_model.py:34` — `datetime.utcnow()` → `datetime.now(datetime.UTC)`
- 任何其它 `tests/` 内 grep 命中的 deprecated datetime API

### FastAPI 库 deprecation(1 例)

- `tests/test_api_security_question.py` 触发 FastAPI `routing.py` 内部 `HTTP_422_UNPROCESSABLE_ENTITY` deprecation(库自身,**非我们代码**)
- 路径 A:升级 FastAPI 到已用新名称的版本(若已升级仍触发,改 B)
- 路径 B:在测试侧用 `warnings.filterwarnings("ignore", ...)` 局部抑制,附 P4 兼容性注释 + tracking issue 链接,等待 FastAPI 上游修复

### Spec 影响

- MODIFIED capability `test-quality-baseline`:加严 warnings 门槛由 "≤ baseline 16" → "0"
- 全量回归阀门:`pytest -n0` 与 `pytest -n auto` 必须 `0 failed / 0 warnings`

## Impact

### Affected specs

- MODIFIED:`test-quality-baseline`(收紧 warnings 门槛)

### Affected code

- `services/password_reset_service.py`(P4 datetime API 迁移)
- `db/statistics.py`(P4 datetime API 迁移)
- 任何 grep 命中的 deprecated datetime 调用方
- `tests/test_password_reset_token_model.py`(P4 datetime API 迁移)
- 可能 `tests/test_api_security_question.py`(若走路径 B)
- 可能 `requirements.txt`(若走路径 A 升级 FastAPI)

### Risk

| 风险 | 等级 | 缓解 |
|---|---|---|
| `datetime.now(UTC)` 返回 timezone-aware,与下游消费者(序列化、DB 列类型)不兼容 | 高 | 每个改动后单测 + 同文件回归;DB 列若是 `timestamp without time zone` 需 `.replace(tzinfo=None)` 或 spec MODIFIED |
| FastAPI 升级触发其它行为变化 | 中 | 路径 A 前先 `pip install --dry-run` 检查依赖兼容;优先路径 B 局部抑制 |
| 改动后 warnings 仍 > 0(漏改) | 中 | `pytest -n0 -W error::DeprecationWarning` 局部跑可疑文件做 fail-fast 验证 |

## Migration

无数据库迁移、无部署变更、无前端变更。
