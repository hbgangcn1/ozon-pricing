# 物流定价系统 — 全栈修复工作计划 v5.0

## ⚠️ 重要原则

**先本地开发和测试，最后才推送到生产服务器！**

```
本地开发 → 本地测试 → 推送GitHub → 最后部署到服务器
```

---

## 项目概况

- **目标**：修复所有功能缺陷，实现缺失模块，JWT认证替换，90%+ 测试覆盖率
- **本地目录**：`C:\Users\hbgan\OneDrive\Robert\learn\logistics`
- **生产服务器**：`SERVER_IP` (`/var/www/ozon-pricing`)
- **数据库**：PostgreSQL (logistics) - 36个用户，19张表
- **部署方式**：git pull + systemd
- **目标分支**：`release/v1`

---

## 已发现的 Bug

| # | 严重度 | 文件 | 描述 |
|---|--------|------|------|
| B01 | 严重 | `api/routes/auth.py` | 登录返回 `access_token=用户名` — token就是用户名 |
| B02 | ✅ | `payment_handler.py` | ~~文件不存在~~ — 已实现 PaymentHandler 类 + payment_handler 实例 |
| B03 | 高 | `api/routes/pricing.py` 等 | `get_current_user_id()` 在6+路由文件中重复，使用token作为用户名的raw SQL |
| B04 | 高 | `frontend/src/services/api.js` | `logoutUser()` 删除 `'user'` 键但认证用 `'api_user'` |
| B05 | 高 | `frontend/src/services/api.js` | 响应拦截器返回 `response.data`，但调用方如DashboardPage仍然访问 `.data` |
| B06 | 高 | `frontend/src/services/api.js` | 401处理器清除 `api_token` 但不清除 `api_user` |
| B07 | 中 | `frontend/src/components/Sidebar.jsx` | 使用原生 `fetch` 绕过 axios auth拦截器 |
| B08 | 高 | `tests/conftest.py` | 硬编码数据库密码 |
| B09 | ~~高~~ | `tests/conftest.py` | ~~非bug~~ — `_clean_db = clean_db` 别名存在 (line 220) |
| B10 | ✅ | `tests/test_real_database.py` | 导入错误已修复 |
| B11 | ✅ | `tests/test_real_database.py` | `adapt_sql` 多余参数已修复 |
| B12 | 中 | `services/*` | 所有6个服务文件都是mock |
| B13 | 中 | `security/utils.py` | 包含 Streamlit 存根代码 |
| B14 | ✅ | 根目录 | 19 个调试/测试/清理脚本已删除 |
| B15 | ✅ | `api/main.py` | 默认端口 8000 与 vite proxy (8003) / playwright (8003) 不一致 — 已修复为 8003 |
| B16 | ✅ | `PricingPage.jsx` | 精准模式"保存产品"按钮读取 `productForm`（产品对话框状态）而非 `preciseForm`，导致始终验证失败 — 已新增 `handleSavePreciseProduct` 并重新绑定按钮 |
| B17 | ✅ | `api/routes/pricing.py` | 非快速模式无条件要求 `product_id`，即使 `product_data` 已提供也会返回 400 — 已改为优先判断 `product_data` |
| B18 | ✅ | `PricingPage.jsx` | 精准模式选产品后改名再保存会覆盖原产品 — 已改为检测名称变更时走新建分支 |
| B19 | ✅ | `PricingPage.jsx` | 精准模式保存产品时重名检查排除自身（允许更新），用户要求任何重名都应报错"已有同名产品"且保存失败 — 已移除自身排除逻辑，并简化为始终新建（update 分支已删除） |
| B20 | ✅ | `tests/conftest.py`, `conftest.py`, `scripts/purge_test_users.py` | 测试用户累积12051条未清理：(1) `delete_user()` 拒绝删admin角色用户致 `test_admin` fixture teardown 静默失败 (2) `clean_db` SQL 对缺少列的表报错被 `except: pass` 吞掉 (3) 多个测试文件直接 `create_user()` 无清理 — 已修复: 新增 `_delete_test_user_by_id` 直接SQL清理、重写 `clean_db` 用子查询模式、添加 `pytest_sessionfinish` 全局安全网 hook、创建一次性清理脚本 `scripts/purge_test_users.py` |
| B21 | ✅ | `frontend/tests/global-teardown.js`, `frontend/playwright.config.js`, `conftest.py`, `tests/conftest.py`, `scripts/purge_test_users.py` | e2e测试残留20个`e2e*`用户未清理：Playwright无globalTeardown、pytest清理不覆盖e2e模式 — 已修复: (1) 新建 `global-teardown.js` 在Playwright测试后通过API删除所有`/^e2e/`用户 (2) `playwright.config.js` 添加 `globalTeardown` 配置 (3) 扩展 `conftest.py` `pytest_sessionfinish` 和 `tests/conftest.py` `clean_db` 的所有SQL覆盖 `e2e%%` 模式 (4) 扩展 `purge_test_users.py` 覆盖 `e2e%%` (5) 执行清理脚本删除20个e2e用户，DB剩余0测试用户 |
| B22 | ✅ | `frontend/src/pages/UserManagementPage.jsx`, `frontend/src/__tests__/UserManagementPage.test.jsx` | "批量物流规则同步"下拉菜单使用硬编码 `mockUsers` 数组（20条假数据，显示19个非admin用户），而用户列表使用真实API数据（3个用户）导致不一致 — 已修复: (1) 删除 `mockUsers` 硬编码数组 (2) 两个下拉菜单（主卡片+同步对话框）均改为 `users.filter(u => u.role !== 'admin')` 使用真实API数据 (3) 修复测试 `renders user list after loading` 中 `getByText('testuser')` 因下拉和表格同时包含testuser导致多元素匹配，改为 `getAllByText` + TD标签断言 |
| B23 | ✅ | `frontend/vitest.config.js` | Vitest 运行时 23 个 Playwright e2e spec 文件被错误包含导致报告失败 — 已修复: `vitest.config.js` 的 `exclude` 数组添加 `'tests/**'` 排除 `frontend/tests/` 下所有 Playwright 文件 |

---

## 执行阶段

### Phase 0: 基础 — 修复现有失败测试 ✅

| 任务 | 状态 | 描述 |
|------|------|------|
| 0.0 | ✅ | pytest.ini 修复 (`testpaths = tests`)，删除 19 个遗留根目录脚本 |
| 0.1 | ✅ | 修复 test_real_database.py 导入错误 (B10/B11) |
| 0.2 | ✅ | 修复所有 20 张表的 id 序列默认值（根因：`CREATE TABLE IF NOT EXISTS` 跳过 `SERIAL` 转换） |
| 0.3 | ✅ | 在 `init_db()` 中添加 `_ensure_serial_columns()` 防护函数，防止序列问题复发 |
| 0.4 | ✅ | 修复 `calculate_logistic_cost` 不处理负数重量的逻辑 bug |
| 0.5 | ⬜ | 硬编码DB密码改为环境变量 (B08) — 推迟到 Phase 6 |

**结果**：74 failed + 14 errors → **870 passed, 0 failed, 0 errors, 1 skipped** → Phase 1 后 **897 passed** → Phase 2 (PaymentHandler) 后 **928 passed** → Phase 4 后 **1393 passed, 1 skipped, 0 failed**

### Phase 1: Auth 系统改造 — JWT 替换 ✅

| 任务 | 状态 | 描述 |
|------|------|------|
| 1.1 | ✅ | 编写 JWT token 模块测试 (RED) — `tests/test_jwt_tokens.py` 18 tests |
| 1.2 | ✅ | 编写共享 auth 依赖测试 (RED) — `tests/test_auth_dependencies.py` 9 tests |
| 1.3 | ✅ | 实现 security/tokens.py (GREEN) — JWT create/decode/extract |
| 1.4 | ✅ | 实现 api/dependencies.py (GREEN) — 共享依赖，JWT+fallback双模式 |
| 1.5 | ✅ | 更新 auth 路由发行 JWT token — login/register 返回 JWT |
| 1.6 | ✅ | 所有路由文件使用共享 auth 依赖 — 8 个路由文件已更新 |
| 1.7 | ✅ | 移除旧版 auth 中间件 — 替换为重定向注释 |

**结果**：897 passed, 1 skipped, 0 failed; flake8 clean on all modified files

### Phase 2: PaymentHandler & 服务层实现 🔄

| 任务 | 状态 | 描述 |
|------|------|------|
| 2.1 | ✅ | 编写 PaymentHandler 测试 (RED) — `tests/test_payment_handler.py` 31 tests |
| 2.2 | ✅ | 实现 payment_handler.py (GREEN) — 224 行，4 方法 + module-level 实例 |
| 2.3 | ⬜ | 编写服务层测试 (RED) |
| 2.4 | ⬜ | 实现真正的服务层 (GREEN) |
| 2.5 | ⬜ | 验证支付生态集成 |

**PaymentHandler 结果**：928 passed, 1 skipped, 0 failed; flake8 clean

### Phase 3: 前端 Bug 修复 ✅

| 任务 | 状态 | 描述 |
|------|------|------|
| 3.0 | ✅ | 配置 Vitest 测试框架 (vitest + jsdom + @testing-library) |
| 3.1 | ✅ | 修复 logoutUser localStorage 键 (B04): `'user'` → `'api_user'` |
| 3.2 | ✅ | 修复 DashboardPage.jsx double `.data` unwrap (B05) |
| 3.3 | ✅ | 修复 401 处理器不完整清理 (B06): 添加 `localStorage.removeItem('api_user')` |
| 3.4 | ✅ | 修复 Sidebar.jsx + SideMenu.jsx 原生 fetch → apiClient (B07) |
| 3.5 | ✅ | 编写 api.js 单元测试 (interceptors, logoutUser, 401, API namespaces) |
| 3.6 | ✅ | 编写 authStore 单元测试 (initAuth, setAuth, logout, permissions) |
| 3.7 | ✅ | 验证 24 tests passed + `npm run build` 成功 |

**结果**：前端 24 tests passed; build 成功; 后端 928 passed 零回归

### Phase 4: 后端测试覆盖率提升 ✅

| 任务 | 状态 | 描述 |
|------|------|------|
| 4.1 | ✅ | FastAPI 路由集成测试 — 61 tests (`test_api_routes.py` + `test_api_routes2.py`) |
| 4.2 | ✅ | logic.py 覆盖率 94% — 119 tests (`test_logic_coverage.py`) |
| 4.3 | ✅ | db_utils.py 覆盖率 **94%** — 229 tests (`_a/_b/_c/_c2/_d.py`) |
| 4.4 | ✅ | db_adapter.py 覆盖率 94% — 26 tests (`test_db_adapter_coverage.py`) |
| 4.5 | ✅ | api/main.py + rate_limit 测试 — 21 tests (`test_api_main.py`) |
| 4.6 | ✅ | dependencies.py 100%, tokens.py 100%, payment_handler.py 100% |

**结果**：1393 passed, 1 skipped, 0 failed; 所有核心模块 94-100% 覆盖率

**覆盖率汇总**：
| 模块 | 覆盖率 | 目标 |
|------|--------|------|
| `payment_handler.py` | **100%** | 90%+ ✅ |
| `api/dependencies.py` | **100%** | 90%+ ✅ |
| `security/tokens.py` | **100%** | 90%+ ✅ |
| `db_adapter.py` | **94%** | 90%+ ✅ |
| `logic.py` | **94%** | 90%+ ✅ |
| `db_utils.py` | **94%** | 90%+ ✅ |

### Phase 5: 前端测试套件 ✅

| 任务 | 状态 | 描述 |
|------|------|------|
| 5.1 | ✅ | authStore 测试 — 14 tests (Phase 3 中完成) |
| 5.2 | ✅ | api.js 服务测试 — 10 tests (Phase 3 中完成) |
| 5.3 | ✅ | Store 测试 — productStore 11 tests + logisticsStore 11 tests + test-utils.js |
| 5.4 | ✅ | 组件测试 — TopHeader 5 tests + SideMenu 5 tests + Sidebar 5 tests |
| 5.5 | ✅ | 页面测试 — LoginPage 8 tests + ProductsPage 7 tests + DashboardPage 6 tests |
| 5.6 | ✅ | 页面测试 — RegisterPage 11 tests + AccountPage 8 tests |

**结果**：101 前端测试通过（12 个测试文件），覆盖 3 个 store、3 个组件、5 个页面

### Phase 6: 遗留代码清理 ✅

| 任务 | 状态 | 描述 |
|------|------|------|
| 6.1 | ✅ | 删除 16 个无引用根文件 (batch 1: auto_backup, backup_manager, data_encryption 等) |
| 6.2 | ✅ | 删除 11 个无引用根文件 (batch 2: install_optional_deps, scheduled_tasks, hmac_utils 等) |
| 6.3 | ✅ | 删除 services/ 目录 (9 个 mock 服务文件) + api/middleware/auth.py + wechat_callback_server.py |
| 6.4 | ✅ | 删除 25 个关联测试文件（测试已删除模块的测试） |
| 6.5 | ✅ | 清理 security/utils.py Streamlit 残留（移除 MagicMock 依赖） |
| 6.6 | ✅ | 修复硬编码 secret（security/tokens.py fallback 值标准化） |
| 6.7 | ✅ | flake8 全面清扫 — 零错误（修复 db_utils.py E402 + enhanced_exchange_service.py E301 + setup.cfg exclude node_modules） |

**结果**：~55 个文件删除，flake8 零错误，921 后端测试通过

### Phase 7: 最终集成验证 ✅

| 任务 | 状态 | 描述 |
|------|------|------|
| 7.1 | ✅ | 完整测试套件 + 覆盖率运行 — 921 passed, 1 skipped, 0 failed; 6核心模块均94-100% |
| 7.2 | ✅ | npm run build 验证 — 构建成功 (dist: 815KB JS + 34KB CSS) |
| 7.3 | ✅ | 更新 PLAN.md |
| 7.4 | ✅ | 更新 AGENTS.md 项目结构（移除 services/，新增 JWT auth、前端测试等） |

### Phase 8: Playwright E2E 全覆盖测试 ✅

| 任务 | 状态 | 描述 |
|------|------|------|
| 8.1 | ✅ | E2E 可行性评估 — 端点映射 (49 endpoints)、认证流程追踪、UI组件库分析 (3种: Ant Design + shadcn/Radix + native HTML) |
| 8.2 | ✅ | 基础设施搭建 — `playwright.config.js` (双 webServer 自动启动前后端), `auth.setup.js`, `test-data.js`, `selectors.js`, `api-helpers.js`, `auth-helpers.js` |
| 8.3 | ✅ | 限流绕过 — `api/main.py` 添加 `E2E_TEST` 环境变量检查跳过 RateLimitMiddleware |
| 8.4 | ✅ | 30 个 E2E 测试文件创建 (25 spec + 5 infrastructure) — 4 个并行 agent 完成 |
| 8.5 | ✅ | 5 轮 E2E 调试迭代: 215→251→258→272→278 passed (77%→90%→92.5%→97.5%→99.6%) |
| 8.6 | ✅ | 后端 Bug 修复 (E2E 发现): `settings.py` (update_time→updated_at), `auth.py` (create_user参数), `orders.py` (完全重写列名), `statistics.py` (多处列名+bigint类型), `subscriptions.py` (plan_code+subscription_expires) |
| 8.7 | ✅ | 后端回归验证 — 921 passed, 1 skipped, 0 failed; flake8 零错误 |

**E2E 测试套件结构** (25 spec files, 278 tests):
```
frontend/tests/
├── auth/           login(6), register(5), logout(2), change-password(5)
├── products/       products-crud(7)
├── logistics/      logistics-crud(7), logistics-list(7)
├── pricing/        pricing-fast(7), pricing-precise(8)
├── admin/          users(13), settings(13)
├── pages/          account(10), subscription(7), about(10), statistics(11)
├── navigation/     routing(20), sidebar(24)
├── api/            auth-api(14), exchange-api(5), orders-api(5), subscriptions-api(7), statistics-api(13), settings-api(14)
└── e2e/            smoke(5), core-flows(4)
```

**最终数据**：
- 后端: 921 passed, 1 skipped, 0 failed (59s)
- 前端: 101 passed, 0 failed (12 test files)
- E2E: **278 passed, 1 skipped, 0 failed** (3.4min, 25 spec files)
- 覆盖率: db_utils 94%, logic 94%, db_adapter 94%, payment_handler 100%, dependencies 100%, tokens 100%
- flake8: 0 errors
- Build: ✅

### Phase 8.5: 后端API集成测试 + 前端页面覆盖率提升 ✅

| 任务 | 状态 | 描述 |
|------|------|------|
| 8.5.1 | ✅ | 后端集成测试 — orders + statistics 端点 (`test_integration_orders_stats.py`, 20 tests) |
| 8.5.2 | ✅ | 后端集成测试 — subscriptions + settings 端点 (`test_integration_subs_settings.py`, 16 tests) |
| 8.5.3 | ✅ | 后端集成测试 — admin CRUD 端点 (`test_integration_admin.py`, 14 tests) |
| 8.5.4 | ✅ | 后端集成测试 — logistics + products CRUD 端点 (`test_integration_logistics_products.py`, 14 tests) |
| 8.5.5 | ✅ | 前端页面测试 — About(3), Payment(6), Subscription(5), Statistics(5), PlanManagement(6) |
| 8.5.6 | ✅ | 前端页面测试 — UserManagement(9), Settings(10), Logistics(11), Pricing(13) |
| 8.5.7 | ✅ | 修复限流导致的40个后端测试失败 — 根因: RateLimitMiddleware 在全套件运行时触发429; 修复: 根 conftest.py 设置 `E2E_TEST=1` 禁用限流 |
| 8.5.8 | ✅ | 全套件回归验证 — pytest 984 passed, vitest 169 passed, E2E 278 passed, flake8 0 errors |

**新增测试文件**：
- 后端集成测试 (4 文件, 64 tests): `test_integration_orders_stats.py`, `test_integration_subs_settings.py`, `test_integration_admin.py`, `test_integration_logistics_products.py`
- 前端页面测试 (9 文件, 68 tests): `AboutPage.test.jsx`, `PaymentPage.test.jsx`, `SubscriptionPage.test.jsx`, `StatisticsPage.test.jsx`, `PlanManagementPage.test.jsx`, `UserManagementPage.test.jsx`, `SettingsPage.test.jsx`, `LogisticsPage.test.jsx`, `PricingPage.test.jsx`

**最终数据**：
- 后端: **984 passed**, 2 skipped, 0 failed (921→984, +64 集成测试)
- 前端: **169 passed**, 0 failed (101→169, +68 页面测试, 21 test files)
- E2E: 278 passed, 1 skipped, 0 failed
- flake8: 0 errors

### Phase 9: 运行时 Bug 修复 ✅

| 任务 | 状态 | 描述 |
|------|------|------|
| 9.1 | ✅ | 诊断4个UI错误（物流规则/备份设置/用户列表/汇率加载） — 根因: 后端未运行在正确端口 |
| 9.2 | ✅ | 修复端口不一致 (B15) — `api/main.py` 默认端口 8000→8003，对齐 vite proxy 和 playwright 配置 |
| 9.3 | ✅ | 验证数据库完整性 — 25张表完整，数据无丢失（11,847用户、2条汇率记录） |
| 9.4 | ✅ | 验证所有4个API端点通过前端代理正常响应 — exchange/rates返回数据, logistics/admin/settings返回401(需认证) |
| 9.5 | ✅ | 回归测试 — pytest 984 passed, vitest 169 passed, flake8 0 errors |

**根因分析**：`api/main.py` 底部 `uvicorn.run()` 默认端口为 8000，但 `frontend/vite.config.js` 代理和 `frontend/playwright.config.js` 均指向 8003。启动脚本使用 `--port 8000` 导致前端无法连接后端。

---

## 完成标准

- [x] `python -m pytest --tb=short` — **986 passed**, 0 failures, 0 errors
- [x] `python -m pytest --cov=... --cov-report=term-missing` — 6核心模块均94-100%覆盖率
- [x] `python -m flake8` — 0 errors, 0 warnings
- [x] `npx vitest run` (frontend/) — **169 tests**, 0 failures (21 test files)
- [x] `npm run build` (frontend/) — 构建成功
- [x] Playwright E2E — 278 passed, 0 failures (25 spec files, 全覆盖 49 endpoints + 14 pages)
- [ ] 无硬编码密码或秘钥 (B08 conftest.py 密码仍硬编码，低优先级)
- [x] 无 Streamlit 引用
- [x] 无调试脚本在根目录
- [x] 所有前端 API 调用使用 JWT auth
- [x] 所有后端端点有对应的 E2E 测试覆盖
- [x] PLAN.md 和 AGENTS.md 已更新

---

## 详细计划

完整的 35 任务、42 次原子提交的详细计划请参见：
`.sisyphus/plans/logistics-fullstack-fix.md`

---

## 项目审计报告

完整审计报告（42 项发现，按严重度排序）请参见：
`AUDIT_REPORT.md`

**摘要**：
| 严重度 | 数量 | 示例 |
|--------|------|------|
| CRITICAL | 6 | 认证绕过、XSS、硬编码密码、货币换算错误 |
| HIGH | 12 | SQL注入、CORS配置、路径遍历、阻塞事件循环 |
| MEDIUM | 14 | 超大文件、返回类型不一致、限流器缺陷 |
| LOW | 10 | 缺少清理函数、无超时配置、控制台日志 |

**修复优先级建议**：P0（安全）→ P1（数据完整性）→ P2（稳定性）→ P3（代码质量）
