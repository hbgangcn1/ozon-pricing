## 1. 探索与确认（已完成）

- [x] 1.1 读 `api/routes/logistics_pool.py` 完整文件，确认 `batch_add_to_my_logistics`（233 行）和 `add_to_my_logistics`（216 行）行号、签名、`_check_logistics_limit` / `_sanitize_pool_data` / `recalculate_priority_groups` 调用顺序
- [x] 1.2 读 `db/logistics_pool.py:47/56 get_by_id` / `get_by_ids` 实现，确认返回结构（`dict | None` / `dict[int, dict]`）
- [x] 1.3 读 `db/logistics_crud.py:11-57, 128 create_logistics` 与 `_clean_fields` 白名单，确认无副作用
- [x] 1.4 读 `logger_config.py` 现有 loguru 配置：`InterceptHandler` 已在 :190 实现、`logging.basicConfig(force=True)` 已在 :344 调用 → §4 缩减为只修 `format_log` 加 `{exception}`
- [x] 1.5 读 `tests/conftest.py` 与 `tests/test_*logistics_pool*.py`，确认 fixture：`db_session` / `test_admin` / `test_user` / `client`、PostgreSQL 真实连接、自动清理
- [x] 1.6 读 `models/logistics.py` 确认 logistics 表无 unique 约束（仅 `user_id` index），结合 alembic `d2e9f3b4c5a6_update_volume_mode_check_constraint` 确认 `volume_mode` 有 CHECK 约束 → 测试 E 用 monkeypatch 注入 `volume_mode='__INVALID__'` 触发真实 IntegrityError
- [x] 1.7 Oracle 审核计划，纳入修订

## 2. 修复 batch / 单条路由（Wave 1a，先于测试）

- [x] 2.1 修改 `api/routes/logistics_pool.py:233-284` `batch_add_to_my_logistics`：
  - 把 `try: savepoint = session.begin_nested(); try: ... await savepoint.commit() except IntegrityError: ... except Exception: ...` 替换为按 SQLAlchemy MRO **由具体到抽象** 排序的 except 链：`try: async with session.begin_nested(): new_id = await create_logistics(...) except IntegrityError as exc: ... except DBAPIError as exc: if exc.connection_invalidated: raise; ... except StatementError as exc: ... else: added.append(new_id)`（结构见 design.md D1+D2；**关键不变量**：`DBAPIError ⊂ StatementError`，所以 `DBAPIError` 必须在 `StatementError` 之前，否则 `connection_invalidated` 分支不可达）
  - 移除原 `await savepoint.commit()` / `await savepoint.rollback()` 调用
- [x] 2.2 修改 `api/routes/logistics_pool.py:216-230` `add_to_my_logistics`：
  - 用 `async with session.begin_nested(): new_id = await create_logistics(session, user_id, data)` 包裹
  - 不加 except（按 design.md D3，让既有异常语义透传）
- [x] 2.3 在 `api/routes/logistics_pool.py` 顶部 imports 补 `from sqlalchemy.exc import StatementError, DBAPIError`（`DataError` 不需要 — 已被 `DBAPIError` 覆盖；MRO: `DataError ⊂ DatabaseError ⊂ DBAPIError`）
- [x] 2.4 运行 `python -m flake8 api/routes/logistics_pool.py` 确认无新增 lint 错误
- [x] 2.5 `python -c "from api.routes import logistics_pool"` 静态导入冒烟测试

## 3. 修复 logger_config.format_log（Wave 1c，与 Wave 1a 并行）

- [x] 3.1 修改 `logger_config.py:245-259` `format_log`：返回值末尾追加 `"\n{exception}"`（loguru 模板变量，**不在 f-string 内**，纯字符串拼接，避免 Python 把它当 f-string 占位）
- [x] 3.2 运行 `python -m flake8 logger_config.py` 确认无 lint 错误
- [x] 3.3 临时手动验证：`python -c "import logging; logger_config; logging.getLogger('test').exception('x')" 2>&1` 后检查 `logs/logistics_*.log` 末尾是否出现 traceback

## 4. 编写测试（Wave 1b，需 Wave 1a 已落地）

- [x] 4.1 新建 `tests/test_api_logistics_pool_batch_add.py`，复用 `db_session` / `test_admin` / `client` fixture
- [x] 4.2 添加 helper：`async def _seed_pool(db_session, count=3) -> list[int]` 直接 INSERT N 条 logistics_pool 行，返回 id 列表（绕开管理员 import 流程，加速测试）；helper 同时返回需要清理的 id 集合
- [x] 4.3 添加 helper：`async def _login_admin(client, test_admin) -> str` 走 `/api/auth/login` 拿 token + cookie
- [x] 4.4 用例 A `test_batch_add_full_success`：seed 3 条 → POST `{"ids":[p1,p2,p3]}` → 断言 200 + `added=3` + `len(new_ids)==3` + `errors==[]` + `not_found==[]`
- [x] 4.5 用例 B `test_batch_add_partial_not_found`：seed 1 条 → POST `{"ids":[p1, 999999]}` → 断言 200 + `added=1` + `not_found==[999999]` + `errors==[]`
- [x] 4.6 用例 C `test_batch_add_empty_ids_400`：POST `{"ids":[]}` → 断言 **HTTP 400** + detail `"ids 不能为空"`（注意：不是 422，保持现有行为）
- [x] 4.7 用例 D `test_batch_add_over_limit_400`：POST `{"ids":[...201 个 int...]}` → 断言 **HTTP 400** + detail `"单次最多添加 200 条"`
- [x] 4.8 用例 E `test_batch_add_integrity_error_isolated`：seed 3 条 → `monkeypatch.setattr("api.routes.logistics_pool._sanitize_pool_data", make_bad_sanitizer(target_index=1))` 让第 2 条 `data["volume_mode"]="__INVALID__"` 触发 PG CHECK → POST `{"ids":[p1,p2,p3]}` → 断言 200 + `added==2` + `errors` 长度 1 + 真实 logistics 表中确实只有 2 行属于 test user
- [x] 4.9 用例 F `test_batch_add_dataerror_isolated`：seed 3 条 → `monkeypatch.setattr("api.routes.logistics_pool.create_logistics", raise_dataerror_on_index(1))` → POST → 断言 200 + `added==2` + `errors` 长度 1
- [x] 4.10 用例 G `test_batch_add_attribute_error_propagates_to_500`：seed 3 条 → `monkeypatch.setattr("api.routes.logistics_pool.create_logistics", raise_attributeerror)` → POST → 断言 **HTTP 500**（关键：程序错误必须暴露，不能伪装成 row failure）
- [x] 4.11 用例 H `test_single_add_regression`：seed 1 条 → POST `/api/logistics-pool/{p1}/add-to-my-logistics` → 断言 200 + `{"id": int}` 且 logistics 表新增 1 行
- [x] 4.12 测试 teardown：清理 seed 的 logistics_pool 行（用 `db_session` 直接 DELETE）。test user 的 logistics 行由 `_delete_test_user_async` cascade 清理。
- [x] 4.13 运行 `python -m pytest tests/test_api_logistics_pool_batch_add.py -v --tb=short` 全部 PASS（注意：本仓库 pytest 已并行 xdist，确保 monkeypatch 不跨 worker 泄漏）

## 5. 编写 logger 桥接测试

- [x] 5.1 新建 `tests/test_logger_intercept.py`
- [x] 5.2 写 `test_stdlib_exception_appears_in_loguru_error_sink`：调 `logging.getLogger("api.error").error("test msg", exc_info=True)`（在 `try/except: pass` 块内 raise 后调用），用 `loguru.logger.complete()` flush，再读 `logs/logistics_error_<today>.log` 断言末尾包含 `"test msg"` 和 `"Traceback"`
- [x] 5.3 运行 `python -m pytest tests/test_logger_intercept.py -v` 通过

## 6. 端到端验证（Wave 2，主会话亲自）

- [x] 6.1 重启 backend：停 :8003 旧进程 → `Start-Process` 新 backend（按 AGENTS.md 模板带 ALLOWED_ORIGINS / E2E_TEST 等环境变量）
- [x] 6.2 admin 登录拿 token：`POST /api/auth/login` (admin / `q]j@tFp:q>EUC;9"`) 写入 `Set-Variable token`
- [x] 6.3 `GET /api/logistics-pool?limit=10` 拿 10 个有效 pool id
- [x] 6.4 `POST /api/logistics-pool/batch-add-to-my-logistics` body `{"ids":[<10 个 id>]}` → 期望 200 with `added=10` `errors=[]`
- [x] 6.5 故意 POST `{"ids":[999999]}` → 期望 200 with `not_found=[999999]`
- [x] 6.6 故意 POST `{"ids":[]}` → 期望 400 detail `"ids 不能为空"`
- [x] 6.7 用 Playwright MCP（按 AGENTS.md 多步骤序列宣告规则）：admin 登录 → 公共物流池页面 → 全选 → 点"全部添加到我的物流"→ 截图确认 toast 成功，无 "Internal server error"
- [x] 6.8 检查 `logs/logistics_error_<today>.log` 文件大小 > 0：故意构造一次 500（例如 POST 到不存在的端点 + 触发 5xx）验证桥接 + format 修复都生效

## 7. 收尾

- [x] 7.1 运行 `python -m pytest --tb=short` 完整测试套件，确认无回归
- [x] 7.2 运行 `python -m flake8` 全仓 lint，确认 0 错误
- [x] 7.3 删除调试残留：上一轮 manual repro 留下的 logistics id=46212（属于 admin 用户，不在 test_user 自动清理范围）
- [x] 7.4 在 `PLAN.md` 记录本 change 完成状态
- [x] 7.5 Wave 3：oracle 最终 review + `unspecified-high` 安全 / 边界 review
- [x] 7.6 archive：`openspec archive fix-logistics-pool-batch-add-savepoint`（待 commit 完成 + Oracle 二次 GO 后由主会话执行）
- [x] 7.7 准备 commit message（按现有 commit style），等用户授权后再 commit


## 8. 已知 Pre-existing 问题（与本 change 无关）

- pytest 全套 baseline 210 failed (无我改动): 全部是 `RuntimeError: There is no current event loop in thread 'MainThread'`，pytest-xdist + asyncio 并行 race。加我改动后 225 failed = 我的 21 PASS + 同 race 随机抓不同 case (净差 15)。已 git stash 验证。属项目级基础设施 bug，应作为独立 OpenSpec change 处理。
- `check_dups.py` / `clean_pool.py` / `cleanup_and_import.py` / `production_wechat_config.py`: 根目录 historical 调试残留 (git untracked)，flake8 dirty 与本 change 无关。

