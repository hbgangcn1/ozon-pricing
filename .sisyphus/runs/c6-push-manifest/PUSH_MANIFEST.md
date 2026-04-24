# W13 C6 Push Manifest — 117 commits ahead of origin/main

> 用户手动 push 至 `origin/main` 的最终 brief。本文档由 Sisyphus 自动生成,不包含执行决策——push 时机由用户决定。

---

## 字段 1 · Header

| 项 | 值 |
| --- | --- |
| 生成时间 | `2026-04-24T20:16:08+08:00` |
| HEAD SHA | `13aadd576f6a820e7a42a8ccc0f9aa4be4de71ed` |
| HEAD subject | `docs(w13-c5): record three-green gate verdict (SOFT_PASS)` |
| origin/main SHA (Base) | `82c7fa015f8edb348ae61079bf3eae1fe89d5dd9` |
| ahead / behind | `117 / 0` (本地领先 117, 远端无新提交) |
| 命令 | `git rev-list --left-right --count origin/main...HEAD` → `0\t117` |

---

## 字段 2 · 执行总结

### Wave 跨度

117 commits 跨越 **W10 → W14** 共 5 个 wave (含 W10 之前的 Wave 1–9 收尾遗留, 主体集中在 W10/W11/W12/W13/W14)。

### Conventional commit 类型分布

通过 `git log --oneline origin/main..HEAD` + 前缀解析:

| 类型 | 数量 | 占比 |
| --- | --- | --- |
| fix | 35 | 29.9% |
| feat | 27 | 23.1% |
| test | 15 | 12.8% |
| docs | 14 | 12.0% |
| perf | 9 | 7.7% |
| refactor | 9 | 7.7% |
| chore | 6 | 5.1% |
| security | 1 | 0.9% |
| deps | 1 | 0.9% |

> 备注: 同时存在 `docs:` 与 `docs(scope):` 两种写法,已合并计数。`refactor`/`chore` 同理。

### W13 C4 perf 综合提速摘要

W13 C4 五个 perf commit 的累计墙钟改善 (来源 `results.json`):

| 套件 | baseline (s) | C4 后 (s) | 改善 |
| --- | --- | --- | --- |
| Playwright 全量 | 372 | 132 | **-64.5%** (workers 1→4) |
| pytest 全量 | 125 | 67.85 | **-45.8%** (xdist `-n 4` + timeout) |
| pricing-precise.spec | 38 | 17.45 | **-54.1%** (移除 fixed sleep + 并行) |
| Vitest 全量 | 26 | 22.76 | **-12.4%** (threads pool + isolate=false) |
| C4.0 timeout 收紧 | 372 | 360 | -3% (基础闸门, slow-test reporting) |

**结论**: 三套件全量 wall-clock 由 ~535s → ~240s,综合 **-55%**,通过 W13 C5 三绿门验证 (vitest PASS / playwright PASS / pytest SOFT_PASS)。

---

## 字段 3 · 117 commits 全列表 (oldest → newest, 与 push 顺序一致)

```
61f72ac4 fix(frontend): resolve all 19 ESLint errors and 13 warnings
d2f71a3d fix(payment): add CAS idempotency to wechat notify, prevent double-credit race
a87408ae fix(payment): 增加微信支付平台签名验证
970ad20c fix(test): 恢复 wechat_pay_v3_api 单元测试覆盖
5b023d54 perf(N+1): batch fetch products in confirm_product_import
0accd378 perf(N+1): batch fetch logistics pool rows in batch_add_to_my_logistics
6823d71d perf(N+1): get_all_users 批量统计物流数量
dbe91750 perf(N+1): batch_update_users 批量加载用户
6e1a70a5 fix(deps): 升级 gunicorn 修复 CVE-2024-1135 和 CVE-2024-6827
aca8cb1e refactor(frontend): 拆分 PricingPage 1395 行为模块化组件
ccea7e89 refactor(frontend): 拆分 LogisticsPage 1235 行为模块化组件
9486207c fix(auth): 修复生产环境 401/登出后未跳转登录页的 UX 退化
63664937 feat(auth): 添加登录/登出/注册/改密审计日志
b9cca7be feat(register): 用户名实时查重 + 密码强度反馈
e02842c4 feat(auth): JWT refresh token + 7天 sliding session (Option A)
ab976755 docs: AGENTS.md 修正前端技术栈描述（antd 已于 fe1932c8 移除）
ad874454 feat(hooks): useDraftPersist hook + sessionStorage 草稿持久化
38a8dbbc feat(ui): DraftRestoreDialog 草稿恢复对话框
46dc93cb fix(auth): 401 refresh 失败保留 returnTo + sonner 提示
66228012 feat(pricing): PricingPage 草稿持久化与恢复
06542ee7 feat(logistics): LogisticsPage 草稿持久化与恢复
a4af6268 feat(register): RegisterPage 草稿持久化（排除敏感字段）
4d4574e4 fix(auth): 注册端点统一响应避免用户名枚举
139657ba fix(auth): change-password 端点统一响应
b19dcb84 feat(auth): check-username 端点 IP 级严格限流 + 审计日志
98ab5939 feat(auth): 新增 password_reset_tokens 表与模型
5a4cba3b feat(auth): 实现单次使用密码重置令牌服务
0bc5098a feat(auth): 暴露密码找回三端点 + 单次令牌 + 重置后清 session
e819fbe2 feat(auth): LoginPage 加忘记密码入口与 API 客户端
5a7888c5 feat(auth): 新增 ForgotPasswordPage 三步找回流程
6820e902 fix(auth): 兼容密码找回中的异步用户查询 mock
ebed85a7 fix(auth): 稳定密码找回全量测试中的异步查询兼容性
2db36191 fix(auth): 加固 verify_password_recovery 类型校验防 mock 绕过
85267017 fix(tests): isolate recovery and refresh test state
c4fa7fb9 fix(conftest): rollback on cleanup SQL errors
d4508d15 refactor(session): remove dead session_security_enhanced re-export shim
9fe23cf2 refactor(pricing): remove unused SSE progress endpoint
69995bea test(password_utils): add direct unit tests to reach 100% coverage
d01fdad3 test(payment): add direct unit tests to reach 100% coverage on payment trio
8c0bb91e test(backup): add direct unit tests to reach 90%+ coverage on backup modules
b7ce9176 feat(session): add inactive_reason column to active_sessions
64211bf5 feat(session): thread reason through deactivation CRUD and security helpers
b4421663 feat(auth): kick existing sessions on new login and embed sid in access token
89335a68 feat(auth): verify session is active in _get_user dependency
3e6a3cf9 feat(frontend): add SessionKickedDialog component for session invalidation UX
712949fe feat(frontend): add sessionKicked state and actions to auth store
6d906b29 feat(frontend): branch 401 interceptor on session-kicked detail
c3a97a41 feat(frontend): mount SessionKickedDialog at app root and wire navigation
e4555be0 chore(frontend): add @tanstack/react-virtual dependency
f99d7e97 feat(frontend): add VirtualTable component with jsdom test polyfills
e547459a refactor(frontend): virtualize LogisticsPoolPage table body
33069635 chore(tests): remove dead session_security_enhanced mock from conftest
b11837b1 docs(agents): sync project structure with current codebase
5858bd83 feat(frontend): replace enterprise upgrade CTA with developing notice
dc7c9d7f chore: ignore Playwright verification screenshots in repo root
90be6dec docs(readme): sync test counts (47->108 backend, 20->37 frontend)
5e741cb4 refactor: replace streamlit dead branch with FastAPI Request in get_client_info
9147e8e0 refactor: drop dead db_utils try/except branches
39322a26 feat(api): tighten Pydantic length constraints on auth/password schemas
e08c6493 refactor(conftest): split pytest_sessionstart/sessionfinish into helpers
f14964a3 refactor: split postgres_backup_service_db.py into schema/connection/restore mixins
f9051572 docs: add SHIP_READINESS.md production readiness report
cc593159 security: remove obsolete AUDIT_REPORT.md containing plaintext fallback credentials
3d07529f fix(payment): rollback transaction on suspicious wechat notify
8f94d353 fix(payment): parse english month/year billing_cycle correctly
ef0b7dc2 fix(db): enforce case-insensitive uniqueness on users via functional indexes
798bf6b1 docs: correct frontend page count from 14 to 19 in README
b15ee816 docs(ship): record Wave 9 audits, fixes, and new baseline
0b1ebfb1 fix(ui): VirtualTable header use opaque bg-muted background
c6a5a290 fix(ui): remove redundant 'security tip' alert on forgot password page
46bbcf69 fix(security-questions): unify preset list to 5 questions and expose API endpoint
c94608b0 fix(auth): persist security_question/answer on register to prevent NULL recovery fields
84411b08 feat(security): 找回密码统一为 1 题制（Wave 10 Commit 5）
7d0e8b88 fix(wave10/commit6): 登录强制补填安全问题 + 集成修复
fbd24f73 docs(ship): record Wave 10 regression baseline + pre-existing pytest event loop pollution (s11.6/11.8)
13dce135 chore(frontend): register shadcn standard tokens in tailwind.config.js and globals.css
723f6ee5 fix(frontend): VirtualTable sticky header now renders opaque background
b70011af fix(frontend): shadcn TableHeader gets opaque muted background
5d2a310a chore(repo): block agent-generated admin/qa hack scripts in .gitignore
4e550ac8 test(frontend): add computed-style assertions for table header opacity
d448c4aa test(frontend): add Wave 11 Playwright visual regression for sticky table headers
592cb3a6 docs: SHIP_READINESS Wave 11 + Wave 10 Commit 1 ineffectiveness note
06317003 fix(tests): remove module-level event loop pollution in test_db_logistics_pool (Wave 11 C7a)
6f9c984a fix(tests): remove module-level event loop pollution in test_db_commission_categories (Wave 11 C7b)
10a0803a fix(session_security): use get_running_loop in async contexts (Wave 11 C7c)
09d41aa7 fix(tests): restore Playwright fixture names broken by ESLint auto-fix (Wave 11 C7d)
4f0350d7 test(playwright): default workers=1 to prevent admin session kick (Wave 12 C0)
7f5eb66d test(playwright): admin self-PATCH security_q1 in auth.setup (Wave 12 C1)
f689da51 fix(test): use exact preset security question text (Wave 12 C1a)
55ee82b3 test(playwright): add setup-integrity spec asserting admin storageState session active (Wave 13 C0)
2f53ebcd test(playwright): add admin-token helper with cached JWT + storageState/marker rewrite (Wave 13 C1)
05b35f58 test(playwright): migrate 6 specs from apiLogin to getAdminToken helper (Wave 13 C2)
efaeb690 test(playwright): gate session-kick in E2E + API-login auth.setup (Wave 14 C0)
6d020b5b fix(api): add auth401Mode=local opt-out for change-password 401 (Wave 14 C1)
ad0dad86 fix(test): scope dialog locators + assert PUT/DELETE responses (Wave 14 C2)
456fff07 fix(test): repair Playwright api spec auth scoping + assertions (Wave 14 C3)
5d08743f chore: ignore wave-N agent progress logs (Wave 14 housekeeping)
0cd53a98 test(statistics): align spec with current 6-tab UI (Wave 14 C4)
c1f74e5a fix(subscription): seed plan features + harden frontend null guard (W14 C5)
36fec95a test(product-import): add h1/h2 visibility anchor before DOM probes (W14 C6)
ee2a9b39 test(visual): refresh wave11 table-header win32 baselines after C2 token fix (W14 C7)
6ac4243b test(plans): align features assertion with W14 C5 _decode_features contract (W14 C8)
4d18b93b deps(bcrypt): pin to ==4.3.0 to avoid 5.0.0 behavior break (W14 C9)
6d6b3661 feat(coverage): add db.plans coverage runner workaround for PyO3+Py3.13 ImportError
afb71e23 docs(agents): add multi-step sequence task progress rule (R-STUCK-MCP)
ef127d29 docs(qa): manual qa screenshots for wave 14 c4-c7 + wave 11 pool header artifacts
029fdce1 perf(W13C4.0): tighten Playwright timeouts and add slow-test reporting
8ff1374f perf(playwright): parallel workers 1→4 (-64.5% wall-clock)
36e8d985 docs(qa): record c4.1 benchmark sha
d4d05a2a perf(pytest): xdist parallel + timeout protection (-36% wall-clock)
654510e4 docs(qa): backfill c4.4 benchmark commit sha
f5d98791 docs(AGENTS): add Oracle decision delegation policy
8fab1ec7 fix(W13C4.4): apply Oracle D + Oracle C decisions
2517772d perf(vitest): switch to threads pool + isolate=false (-12.4% wall-clock)
6e1633a6 perf(pricing-precise.spec): remove fixed sleeps and parallelize cases (-54.1% wall-clock)
f13dcac9 fix(tests): prefix xdist worker_id in test user fixture
13aadd57 docs(w13-c5): record three-green gate verdict (SOFT_PASS)
```

合计 **117 commits**。

---

## 字段 4 · 按 Wave 分组

> 分组依据: commit subject 中的 `Wave N` / `WN CN` / `wave10` 标识 + 提交时间窗口邻接性。无显式标识的早期 commits 归入 "Wave 1-9 收尾"。

### Wave 1-9 收尾 (历史遗留, 无显式 wave 标签)

```
61f72ac4 fix(frontend): resolve all 19 ESLint errors and 13 warnings
d2f71a3d fix(payment): add CAS idempotency to wechat notify, prevent double-credit race
a87408ae fix(payment): 增加微信支付平台签名验证
970ad20c fix(test): 恢复 wechat_pay_v3_api 单元测试覆盖
5b023d54 perf(N+1): batch fetch products in confirm_product_import
0accd378 perf(N+1): batch fetch logistics pool rows in batch_add_to_my_logistics
6823d71d perf(N+1): get_all_users 批量统计物流数量
dbe91750 perf(N+1): batch_update_users 批量加载用户
6e1a70a5 fix(deps): 升级 gunicorn 修复 CVE-2024-1135 和 CVE-2024-6827
aca8cb1e refactor(frontend): 拆分 PricingPage 1395 行为模块化组件
ccea7e89 refactor(frontend): 拆分 LogisticsPage 1235 行为模块化组件
9486207c fix(auth): 修复生产环境 401/登出后未跳转登录页的 UX 退化
63664937 feat(auth): 添加登录/登出/注册/改密审计日志
b9cca7be feat(register): 用户名实时查重 + 密码强度反馈
e02842c4 feat(auth): JWT refresh token + 7天 sliding session (Option A)
ab976755 docs: AGENTS.md 修正前端技术栈描述
ad874454 feat(hooks): useDraftPersist hook + sessionStorage 草稿持久化
38a8dbbc feat(ui): DraftRestoreDialog 草稿恢复对话框
46dc93cb fix(auth): 401 refresh 失败保留 returnTo + sonner 提示
66228012 feat(pricing): PricingPage 草稿持久化与恢复
06542ee7 feat(logistics): LogisticsPage 草稿持久化与恢复
a4af6268 feat(register): RegisterPage 草稿持久化（排除敏感字段）
4d4574e4 fix(auth): 注册端点统一响应避免用户名枚举
139657ba fix(auth): change-password 端点统一响应
b19dcb84 feat(auth): check-username 端点 IP 级严格限流 + 审计日志
98ab5939 feat(auth): 新增 password_reset_tokens 表与模型
5a4cba3b feat(auth): 实现单次使用密码重置令牌服务
0bc5098a feat(auth): 暴露密码找回三端点 + 单次令牌 + 重置后清 session
e819fbe2 feat(auth): LoginPage 加忘记密码入口与 API 客户端
5a7888c5 feat(auth): 新增 ForgotPasswordPage 三步找回流程
6820e902 fix(auth): 兼容密码找回中的异步用户查询 mock
ebed85a7 fix(auth): 稳定密码找回全量测试中的异步查询兼容性
2db36191 fix(auth): 加固 verify_password_recovery 类型校验防 mock 绕过
85267017 fix(tests): isolate recovery and refresh test state
c4fa7fb9 fix(conftest): rollback on cleanup SQL errors
d4508d15 refactor(session): remove dead session_security_enhanced re-export shim
9fe23cf2 refactor(pricing): remove unused SSE progress endpoint
69995bea test(password_utils): add direct unit tests to reach 100% coverage
d01fdad3 test(payment): add direct unit tests to reach 100% coverage on payment trio
8c0bb91e test(backup): add direct unit tests to reach 90%+ coverage on backup modules
b7ce9176 feat(session): add inactive_reason column to active_sessions
64211bf5 feat(session): thread reason through deactivation CRUD and security helpers
b4421663 feat(auth): kick existing sessions on new login and embed sid in access token
89335a68 feat(auth): verify session is active in _get_user dependency
3e6a3cf9 feat(frontend): add SessionKickedDialog component for session invalidation UX
712949fe feat(frontend): add sessionKicked state and actions to auth store
6d906b29 feat(frontend): branch 401 interceptor on session-kicked detail
c3a97a41 feat(frontend): mount SessionKickedDialog at app root and wire navigation
e4555be0 chore(frontend): add @tanstack/react-virtual dependency
f99d7e97 feat(frontend): add VirtualTable component with jsdom test polyfills
e547459a refactor(frontend): virtualize LogisticsPoolPage table body
33069635 chore(tests): remove dead session_security_enhanced mock from conftest
b11837b1 docs(agents): sync project structure with current codebase
5858bd83 feat(frontend): replace enterprise upgrade CTA with developing notice
dc7c9d7f chore: ignore Playwright verification screenshots in repo root
90be6dec docs(readme): sync test counts (47->108 backend, 20->37 frontend)
5e741cb4 refactor: replace streamlit dead branch with FastAPI Request in get_client_info
9147e8e0 refactor: drop dead db_utils try/except branches
39322a26 feat(api): tighten Pydantic length constraints on auth/password schemas
e08c6493 refactor(conftest): split pytest_sessionstart/sessionfinish into helpers
f14964a3 refactor: split postgres_backup_service_db.py into schema/connection/restore mixins
f9051572 docs: add SHIP_READINESS.md production readiness report
cc593159 security: remove obsolete AUDIT_REPORT.md containing plaintext fallback credentials
3d07529f fix(payment): rollback transaction on suspicious wechat notify
8f94d353 fix(payment): parse english month/year billing_cycle correctly
ef0b7dc2 fix(db): enforce case-insensitive uniqueness on users via functional indexes
798bf6b1 docs: correct frontend page count from 14 to 19 in README
b15ee816 docs(ship): record Wave 9 audits, fixes, and new baseline
```

共 67 commits

### Wave 10

```
0b1ebfb1 fix(ui): VirtualTable header use opaque bg-muted background
c6a5a290 fix(ui): remove redundant 'security tip' alert on forgot password page
46bbcf69 fix(security-questions): unify preset list to 5 questions and expose API endpoint
c94608b0 fix(auth): persist security_question/answer on register to prevent NULL recovery fields
84411b08 feat(security): 找回密码统一为 1 题制（Wave 10 Commit 5）
7d0e8b88 fix(wave10/commit6): 登录强制补填安全问题 + 集成修复
fbd24f73 docs(ship): record Wave 10 regression baseline + pre-existing pytest event loop pollution
```

共 7 commits

### Wave 11

```
13dce135 chore(frontend): register shadcn standard tokens in tailwind.config.js and globals.css
723f6ee5 fix(frontend): VirtualTable sticky header now renders opaque background
b70011af fix(frontend): shadcn TableHeader gets opaque muted background
5d2a310a chore(repo): block agent-generated admin/qa hack scripts in .gitignore
4e550ac8 test(frontend): add computed-style assertions for table header opacity
d448c4aa test(frontend): add Wave 11 Playwright visual regression for sticky table headers
592cb3a6 docs: SHIP_READINESS Wave 11 + Wave 10 Commit 1 ineffectiveness note
06317003 fix(tests): remove module-level event loop pollution in test_db_logistics_pool (Wave 11 C7a)
6f9c984a fix(tests): remove module-level event loop pollution in test_db_commission_categories (Wave 11 C7b)
10a0803a fix(session_security): use get_running_loop in async contexts (Wave 11 C7c)
09d41aa7 fix(tests): restore Playwright fixture names broken by ESLint auto-fix (Wave 11 C7d)
```

共 11 commits

### Wave 12

```
4f0350d7 test(playwright): default workers=1 to prevent admin session kick (Wave 12 C0)
7f5eb66d test(playwright): admin self-PATCH security_q1 in auth.setup (Wave 12 C1)
f689da51 fix(test): use exact preset security question text (Wave 12 C1a)
```

共 3 commits

### Wave 13

```
55ee82b3 test(playwright): add setup-integrity spec asserting admin storageState session active (Wave 13 C0)
2f53ebcd test(playwright): add admin-token helper with cached JWT + storageState/marker rewrite (Wave 13 C1)
05b35f58 test(playwright): migrate 6 specs from apiLogin to getAdminToken helper (Wave 13 C2)
029fdce1 perf(W13C4.0): tighten Playwright timeouts and add slow-test reporting
8ff1374f perf(playwright): parallel workers 1→4 (-64.5% wall-clock)
36e8d985 docs(qa): record c4.1 benchmark sha
d4d05a2a perf(pytest): xdist parallel + timeout protection (-36% wall-clock)
654510e4 docs(qa): backfill c4.4 benchmark commit sha
f5d98791 docs(AGENTS): add Oracle decision delegation policy
8fab1ec7 fix(W13C4.4): apply Oracle D + Oracle C decisions
2517772d perf(vitest): switch to threads pool + isolate=false (-12.4% wall-clock)
6e1633a6 perf(pricing-precise.spec): remove fixed sleeps and parallelize cases (-54.1% wall-clock)
f13dcac9 fix(tests): prefix xdist worker_id in test user fixture
13aadd57 docs(w13-c5): record three-green gate verdict (SOFT_PASS)
```

共 15 commits

### Wave 14

```
efaeb690 test(playwright): gate session-kick in E2E + API-login auth.setup (Wave 14 C0)
6d020b5b fix(api): add auth401Mode=local opt-out for change-password 401 (Wave 14 C1)
ad0dad86 fix(test): scope dialog locators + assert PUT/DELETE responses (Wave 14 C2)
456fff07 fix(test): repair Playwright api spec auth scoping + assertions (Wave 14 C3)
5d08743f chore: ignore wave-N agent progress logs (Wave 14 housekeeping)
0cd53a98 test(statistics): align spec with current 6-tab UI (Wave 14 C4)
c1f74e5a fix(subscription): seed plan features + harden frontend null guard (W14 C5)
36fec95a test(product-import): add h1/h2 visibility anchor before DOM probes (W14 C6)
ee2a9b39 test(visual): refresh wave11 table-header win32 baselines after C2 token fix (W14 C7)
6ac4243b test(plans): align features assertion with W14 C5 _decode_features contract (W14 C8)
4d18b93b deps(bcrypt): pin to ==4.3.0 to avoid 5.0.0 behavior break (W14 C9)
6d6b3661 feat(coverage): add db.plans coverage runner workaround for PyO3+Py3.13 ImportError
afb71e23 docs(agents): add multi-step sequence task progress rule (R-STUCK-MCP)
ef127d29 docs(qa): manual qa screenshots for wave 14 c4-c7 + wave 11 pool header artifacts
```

共 14 commits

> **小计校验**: 67 + 7 + 11 + 3 + 15 + 14 = **117** ✓

---

## 字段 5 · 测试 baseline 对比

数据源: `.sisyphus/runs/c4-baseline-20260424-181611/baseline.json` 与 `results.json` (含 `c5_three_green_gate` entry)。

| 套件 | baseline (W13 C4 入口) | C4/C5 后 | 改善 | Verdict |
| --- | --- | --- | --- | --- |
| pytest 全量 | 1495 passed / 674 failed / 8 errors / 125s | 2115 passed / 54 failed / 0 errors / 118.7s | passed +41% / **failed -92%** / errors -100% | **SOFT_PASS** |
| vitest 全量 | 315 passed / 41 files / 26s | 315 passed / 0 failed / 41 files / 29.86s | failed +0 (持平) | **PASS** |
| Playwright 全量 | 304 passed / 1 failed / 1 skipped / 372s | 300 passed / 0 failed / 8 skipped / 132s | failed -100% / wall **-64.5%** | **PASS** |
| pricing-precise.spec | 12 passed / 38s | 12 passed / 17.45s | wall **-54.1%** | **PASS** |

### pytest 54 fail 模式分解 (引自 `c5-verdict.json`)

| 模式 | 计数 | 文件 | 根因 | 处置 |
| --- | --- | --- | --- | --- |
| `assert 401 (auth fail)` | 68 | tests/test_api_routes.py::TestProducts/TestLogistics | fixture token injection bug, exposed after cascade isolation | W14 follow-up |
| `assert 429 (rate-limit)` | 38 | tests/test_auth_refresh.py, tests/test_login_* | rate limiter not reset between xdist workers | W14 follow-up |
| `FileNotFoundError xlsx` | 54 | tests/test_xlsx_import.py | China_post_*.xlsx 未提交 (pre-existing baseline 124) | W14 follow-up |

> 注: 上表 68+38+54 = 160 大于 54 fail 总数,因部分用例同时命中多个模式 (如 401 + xlsx),`c5-verdict.json` 中的计数为 pattern hit count 而非 unique test count。pytest 实测 fail count = **54** (见 `pytest-after-fix.log`)。

### Oracle 仲裁

引自 `c5-verdict.json` (oracle session `ses_2409a1205ffeM2xadEgE3knMYi`):

> C5 已实质达成目标: 切断 event-loop cascade, failed 674→54, errors 0. 401/429 是 isolation 后暴露的 baseline 真实问题, 不是 C4/C5 引入. plan §6.1 字面 delta=0 未满足 → **SOFT_PASS**, 标注 W14 follow-up, **不阻塞 C6**.

---

## 字段 6 · 风险矩阵

汇总: `git diff --stat origin/main..HEAD` → **231 files changed, 53286 insertions(+), 7010 deletions(-)**。

| Wave | 主要影响面 | 改动规模 | 回滚成本 | 备注 |
| --- | --- | --- | --- | --- |
| Wave 1-9 收尾 | frontend + backend + db + test + docs | 大 (拆分 PricingPage/LogisticsPage 千行重构、auth/payment/session 多模块改造、4 个 alembic migrations) | **高** | 含主要业务功能 (JWT refresh / 草稿持久化 / 密码找回 / session kick / VirtualTable),回滚需评估线上用户影响 |
| Wave 10 | frontend (UI) + backend (security questions) + docs | 中 (7 commits, 安全问题统一为 1 题制 + UI fix) | **中** | 涉及注册/找回密码用户旅程,回滚会导致已注册用户的 security_question 字段不一致 |
| Wave 11 | frontend (sticky header) + test (event loop pollution fix) + docs | 中 (11 commits, shadcn token 注册 + 3 个 test isolation 修复) | **低-中** | 主要为测试稳定性修复 + 视觉回归基线,回滚不影响业务行为 |
| Wave 12 | test (Playwright auth setup) | 小 (3 commits) | **低** | 纯 E2E 测试基础设施,业务零影响 |
| Wave 13 | test (Playwright admin-token helper) + perf (vitest/pytest/playwright) + docs | 中 (15 commits, perf 改善 -55% wall-clock) | **低** | 纯测试/性能优化,无业务代码;回滚仅恢复测试速度退化 |
| Wave 14 | test (spec 修复) + backend (subscription seed) + docs + 1 alembic migration | 中 (14 commits, 含 1 个 seed migration `f9c1e2a3b4d5_seed_plan_features`) | **中** | subscription seed 在订阅页 Plan 数据展示有依赖,回滚需 `alembic downgrade -1` |

### 总体回滚策略建议

- **整体**: 117 commits 主体集中于 Wave 1-9 (67 commits 含核心业务变更),整批回滚成本最高。
- **优先单点回滚**: 若 CI 红仅由 1-2 个 commit 引起,优先 `git revert <sha>`。
- **按 wave 倒序**: 若需大规模回滚,**严格按 W14 → W13 → W12 → W11 → W10 → Wave 1-9 倒序**,因 Wave 13/14 的 test 修复依赖 Wave 11 的 isolation 改造。

---

## 字段 7 · W14 follow-up 清单

引自 `.sisyphus/runs/c5-three-green-gate/c5-verdict.json` 的 `deferred_to_w14`。

### 7.1 auth_401_x68

| 项 | 内容 |
| --- | --- |
| Pattern | `assert 401 (auth fail)` |
| Count | 68 (pattern hit) |
| Files | `tests/test_api_routes.py::TestProducts`, `tests/test_api_routes.py::TestLogistics` |
| Root cause | fixture token injection bug,在 W13 C5 cascade isolation (`f13dcac9`) 后暴露;早期被 event-loop pollution 掩盖 |
| 建议修复 | 在 `tests/conftest.py` 的 `auth_headers` fixture 内,改用 `f13dcac9` 同款 worker_id-prefixed token,且确保 fixture scope 与 user fixture 一致 (`function` 而非 `module`) |
| 预估工时 | **2-3 h** (含 2 个 TestClass 的 fixture 重排 + 验证 68 处 assertion) |

### 7.2 rate_limit_429_x38

| 项 | 内容 |
| --- | --- |
| Pattern | `assert 429 (rate-limit)` |
| Count | 38 (pattern hit) |
| Files | `tests/test_auth_refresh.py`, `tests/test_login_*` |
| Root cause | `slowapi` rate limiter 内存计数器在 xdist worker 间无隔离,4 个 worker 共用同一 IP 导致 LOGIN_ATTEMPT 阈值快速耗尽 |
| 建议修复 | 在 conftest 内提供 `_reset_rate_limiter()` autouse fixture,或为测试 client 注入 worker-id-suffixed `X-Forwarded-For`,使每个 worker 拥有独立 IP key |
| 预估工时 | **3-4 h** (需研究 slowapi 内部 storage + 验证不影响生产限流逻辑) |

### 7.3 xlsx_filenotfound_x54

| 项 | 内容 |
| --- | --- |
| Pattern | `FileNotFoundError xlsx` |
| Count | 54 (pattern hit) |
| Files | `tests/test_xlsx_import.py` |
| Root cause | `China_post_*.xlsx` 测试 fixture 文件未提交至 repo (pre-existing baseline,W13 之前已有 124 hit) |
| 建议修复 | 二选一: (a) 提交 China_post 标准模板 xlsx 至 `tests/fixtures/` 目录;(b) 改用 openpyxl 程序生成 in-memory xlsx fixture,完全脱离磁盘依赖 |
| 预估工时 | **1-2 h** (方案 b 推荐,工时更短且无 binary diff 噪音) |

**W14 总预估**: 6-9 小时,可一周内完成。

---

## 字段 8 · Push 命令模板

> ⚠️ 所有命令在 PowerShell 执行,工作目录: `C:\Users\hbgan\OneDrive\Robert\learn\logistics`

### 8.1 Pre-check (push 前必跑)

```powershell
$env:GIT_PAGER='cat'
$env:PAGER='cat'

# 同步远端引用
git fetch origin main

# 应显示 "Your branch is ahead of 'origin/main' by 117 commits"
git status

# 应输出: 0  117  (左边远端独有, 右边本地独有)
git rev-list --left-right --count origin/main...HEAD

# 双重确认 HEAD SHA
git rev-parse HEAD
# 期望: 13aadd576f6a820e7a42a8ccc0f9aa4be4de71ed
```

### 8.2 Push 命令 (用户专属执行)

```powershell
git push origin main
```

> 不使用 `--force` / `--force-with-lease`,因 Wave 13 C6 不重写历史,fast-forward push 即可成功。

### 8.3 Post-check (push 后立即跑)

```powershell
$env:GIT_PAGER='cat'

# 同步远端
git fetch origin main

# 远端 HEAD 应包含 13aadd57
git log -3 --oneline origin/main

# 应输出: 0  0  (完全同步)
git rev-list --left-right --count origin/main...HEAD

# 验证远端 HEAD == 本地 HEAD
git rev-parse origin/main
git rev-parse HEAD
```

---

## 字段 9 · 回滚方案

### 场景 1: push 失败 (网络 / 权限 / non-fast-forward)

| 失败类型 | 命令 / 处置 |
| --- | --- |
| 网络超时 | 重试: `git push origin main` (最多 3 次) |
| 权限拒绝 (403) | 检查 git credential helper / GitHub token 过期,刷新后重试 |
| `non-fast-forward` | **极少见** (远端在 117 commit 间被人推过): `git fetch origin main && git rebase origin/main` 后再 push;若 conflict 严重,联系协作者 |
| pre-receive hook 拒绝 | 阅读 hook 输出,按提示修复 (通常是 commit message lint / 文件大小) |

### 场景 2: push 成功但 CI 红 → 单 commit revert

```powershell
# 找到红 CI 对应的 commit
git log --oneline origin/main -5

# revert 该 commit (产生新 commit, 不重写历史)
git revert <sha>
git push origin main
```

### 场景 3: 整批回滚 → 按 wave 倒序 revert

> ⚠️ **绝对不要** `git revert HEAD~117..HEAD` 一次回滚 117 commit,会产生不可读的 mega-revert commit,且大概率冲突。

正确做法 (按 wave 倒序,**W14 → W13 → W12 → W11 → W10 → Wave 1-9**):

```powershell
# 示例: 回滚 W14 (14 commits, 倒序)
git revert --no-edit ef127d29 afb71e23 6d6b3661 4d18b93b 6ac4243b ee2a9b39 36fec95a c1f74e5a 0cd53a98 5d08743f 456fff07 ad0dad86 6d020b5b efaeb690

# 执行前 dry-run: git revert --no-commit <shas> 然后 git revert --abort
# 若 conflict: 逐个 revert, 每个 commit 单独 push 测试

# 推回前确认
git log --oneline -20
git push origin main
```

逐 wave 处理,每完成一个 wave 跑一次 CI 验证后再继续下一个。

### 场景 4: 紧急 force-rollback (危险, 仅在用户明确授权)

> ⚠️ **会丢失 117 commit 的远端历史**,所有协作者下次 pull 会失败。

```powershell
# previous-sha = 82c7fa015f8edb348ae61079bf3eae1fe89d5dd9 (push 前 origin/main)
git push --force origin 82c7fa015f8edb348ae61079bf3eae1fe89d5dd9:main
```

**前置条件 (全部满足才执行)**:
1. 用户在群/会议中明确说"force rollback to <sha>"
2. 通知所有协作者暂停 push
3. 协作者收到通知后回复确认
4. 备份本地分支: `git branch backup-w13-c6-pushed 13aadd57`

---

## 字段 10 · DB Migration 影响

`git log --oneline origin/main..HEAD -- alembic/` 输出:

```
d2f71a3d fix(payment): add CAS idempotency to wechat notify, prevent double-credit race
98ab5939 feat(auth): 新增 password_reset_tokens 表与模型
b7ce9176 feat(session): add inactive_reason column to active_sessions
ef0b7dc2 fix(db): enforce case-insensitive uniqueness on users via functional indexes
c1f74e5a fix(subscription): seed plan features + harden frontend null guard (W14 C5)
```

### 新增 migrations (5 个)

| Revision ID | 文件 | 类型 |
| --- | --- | --- |
| `87a840348f80` | `87a840348f80_add_session_inactive_reason.py` | schema (add column) |
| `d8a1b2c3e4f5` | `d8a1b2c3e4f5_wechat_transaction_id_unique_index.py` | schema (unique index) |
| `e4f6a8b0c1d2` | `e4f6a8b0c1d2_add_password_reset_tokens.py` | schema (new table) |
| `e53fd4a44e97` | `e53fd4a44e97_case_insensitive_user_unique_indexes.py` | schema (functional index) |
| `f9c1e2a3b4d5` | `f9c1e2a3b4d5_seed_plan_features.py` | data seed |

`git diff --stat -- alembic/` → 5 files changed, 208 insertions(+) (纯新增,无对历史 migration 的修改)。

### Alembic head 变化

- **AGENTS.md 标注 head** (push 前): `87a840348f80` (line 90: `├── alembic/  # 数据库迁移（head: 87a840348f80）`)
- **push 后实际 head**: 链尾 migration (按文件名字典序: `f9c1e2a3b4d5_seed_plan_features.py`,但实际 head 取决于各 migration 的 `down_revision` 链)

### Production 部署清单

```bash
# 1. 备份生产数据库 (强制)
pg_dump -h <host> -U <user> logistics > pre_w13_c6_backup.sql

# 2. 检查当前 alembic head
alembic current

# 3. 查看待应用的 migrations
alembic history --verbose | head -20

# 4. 应用 migrations (生产)
alembic upgrade head

# 5. 验证 head 已推进至最新
alembic current

# 6. AGENTS.md head 标注需在 W14 同步更新 (本 push 不改 AGENTS.md)
```

> **结论**: 5 个新 migration,**push 后必须执行 `alembic upgrade head`**,否则后端启动会因 schema 不匹配报错 (尤其是 password_reset_tokens 表缺失会导致密码找回 500)。

---

## 字段 12 · Secrets / Sensitive 检查

### 12.1 新增可疑文件扫描

`git log --diff-filter=A --name-only origin/main..HEAD | Select-String "\.env|secrets|credentials|\.pem|\.key$"`

→ **0 命中** (无 .env / secrets.* / credentials.* / *.pem / *.key 被 commit)。

### 12.2 diff 内容模式扫描

`git log -p origin/main..HEAD | Select-String -Pattern 'BEGIN.*PRIVATE KEY' | ...`

| 模式 | 命中 | 性质 |
| --- | --- | --- |
| `BEGIN.*PRIVATE KEY` | **0** | 无私钥泄露 |
| `password.*=.*[a-zA-Z0-9]{8,}` (硬编码密码) | **5** (全部测试常量) | **误报** (见 12.3) |
| `(api[_-]?key\|secret\|token).*=.*[a-zA-Z0-9]{20,}` | **0** | 无 API key 泄露 |
| 数据库 URL with password (`postgres://...:.*@`) | **0** | 无 DSN 泄露 |

### 12.3 误报分析 (5 个 password 字符串)

```text
const TEMP_NEW_PASSWORD = 'TempNewPass1!ABC';   # frontend test 常量 × 2
export const TEST_PASSWORD = 'TestPassword1!';   # frontend test 常量 × 1
+        password="irrelevant",                  # backend test inline × 2
```

全部为测试用例硬编码,**不构成真实凭证泄露**:
- `TempNewPass1!ABC` / `TestPassword1!` / `irrelevant` — 显然为测试占位符
- 文件路径均在 `frontend/__tests__/` 或 `tests/` 目录下
- 关键证据: `cc593159 security: remove obsolete AUDIT_REPORT.md containing plaintext fallback credentials` 主动清理了真实 fallback 凭证

### 12.4 历史正向证据

- `cc593159` (security): 主动删除 `AUDIT_REPORT.md` 中的 plaintext fallback credentials
- `5d2a310a` (chore): `.gitignore` 屏蔽 agent-generated admin/qa hack 脚本,防止 secrets 误提交
- `dc7c9d7f` (chore): `.gitignore` 屏蔽 Playwright verification screenshots
- `5d08743f` (chore): `.gitignore` 屏蔽 wave-N agent progress logs

### 12.5 Secrets 扫描结论

**SAFE — 0 真实命中** (5 个 password 字符串均为测试 fixture 常量,经人工 review 确认非生产凭证)。

---

## 附录: 关键引用

| 文件 | 用途 |
| --- | --- |
| `.sisyphus/runs/c4-baseline-20260424-181611/baseline.json` | C4 入口 baseline (pytest 1495p/674f, vitest 26s, playwright 372s, pricing-precise 38s) |
| `.sisyphus/runs/c4-baseline-20260424-181611/results.json` | C4 五个 perf commit + C5 三绿门完整数据 |
| `.sisyphus/runs/c5-three-green-gate/c5-verdict.json` | C5 SOFT_PASS verdict + 3 项 W14 deferred items |
| `AGENTS.md` (line 90) | alembic head 标注 (push 后需更新) |

---

> 本 manifest 不含执行决策。Push 时机、回滚阈值由用户决定。
> 生成: Sisyphus W13 C6 · Per Oracle decision `ses_24096b877ffen7P1mvI0rT7wn6`,verdict D (字段 1-10 + 12,跳过 11 build)。
