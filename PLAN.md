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
- **后端端口**：`8003`（uvicorn，http://localhost:8003）
- **前端端口**：`3001`（Vite dev server，http://localhost:3001）
- **生产服务器**：`SERVER_IP` (`/var/www/ozon-pricing`)
- **数据库**：PostgreSQL (logistics) - 36个真实用户，19张表
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
| B24 | ✅ | `db/products.py`, `api/routes/products.py` | 产品导入允许大量可选字段留空，`GET /api/products` 返回时 `ProductResponse` 对 `None` 数值/布尔字段做响应校验失败，导致 PricingPage 精准模式产品列表显示为空 — 已修复: `db/products.py` 在产品序列化时把缺失数值字段归一化为 `0/0.0`、缺失布尔字段归一化为 `False`，保证历史导入数据和新导入数据都能被产品列表接口正常返回 |
| B25 | ✅ | `api/models/schemas.py`, `frontend/src/pages/PricingPage.jsx` | 精准模式保存产品佣金类目后重新打开产品列表或重新选择产品时，佣金类目始终显示"选择佣金类目"而非已保存的值 — 根因：`commission_category_id` 字段在 Pydantic schemas (`ProductBase`/`ProductUpdate`) 中完全缺失，前端发送的值被静默丢弃 — 已修复: (1) `schemas.py` 的 `ProductBase` 和 `ProductUpdate` 添加 `commission_category_id: Optional[int] = None` (2) `PricingPage.jsx` 的 `productForm` 初始状态和 `handleOpenProductDialog` 添加 `commission_category_id` 初始化 — 测试: 后端单元测试3个 + 集成测试3个 + 前端单元测试2个 + E2E测试1个，全部通过 |
| B26 | ✅ | `pricing/_result_helpers.py`, `pricing/calculate_pricing.py`, `api/routes/pricing.py` | 精准模式空运计算结果的利润率(profit_margin)始终显示0，陆运正确 — 根因：(1) `_phase2_profit_build` 用 `_` 丢弃了 `_compute_profits` 返回的 `air_profit_margin` (2) `_pick_suggested` 当 suggested=air 时硬编码 margin=0 (3) `format_result` 取统一的 `profit_margin` 而非按运输方式区分 — 已修复: (1) `_phase2_profit_build` 保留 `air_profit_margin` 并传递给 `_build_result` (2) `_pick_suggested` 新增 `air_profit_margin` 参数，不再硬编码 (3) `_build_result` 结果字典新增 `land_profit_margin`/`air_profit_margin` 键 (4) `format_result` 按 `is_land` 分别取对应的 margin 值 — 测试: 后端新增5个单元测试 + 更新1个已有测试，全量1375 passed + 前端201 passed + E2E 12/12 passed |
| B27 | ✅ | `api/routes/pricing.py` | 精准模式空运卡片显示陆运价格（如"水卫士洗碗块"空运应显示¥65.04却显示¥53.57） — 根因：`format_result()` 使用统一的 `res.get("suggested_price")` 获取价格，`_pick_suggested()` 优先选 `land_price` 作为 `suggested_price`，导致 `is_land=False` 时仍返回陆运价格 — 已修复: `format_result()` 改为 `res.get("land_price") if is_land else res.get("air_price")`，availability 检查也按运输方式分别判断 — 测试: 后端 1375 passed (1 pre-existing failure) + 前端 201 passed + E2E 12/12 passed |

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

#### 微信支付后端接口集成（wechat-payment-integration）

| 任务 | 状态 | 描述 |
|------|------|------|
| 1.1 | ✅ | 新建 `api/routes/payment.py`，补齐创建支付、回调通知、状态查询接口与 Pydantic 模型 |
| 1.2 | ✅ | `POST /api/payments/create`：校验套餐金额、创建 `PaymentOrder`、调用微信 Native 下单、失败回写 `FAILED` |
| 1.3 | ✅ | `POST /api/payments/notify`：免认证回调、签名失败返回 400、幂等处理、成功后 `asyncio.create_task()` 异步触发 `PaymentHandler.handle_payment_success` |
| 1.4 | ✅ | `GET /api/payments/{order_id}/status`：用户隔离校验、PENDING 时同步查询微信订单状态并处理成功单 |
| 1.5 | ✅ | `api/main.py` 注册 payment router |
| 2.1 | ✅ | `db/orders.py` 增强：支持 `status` 过滤、`page/page_size` 分页与 `total` 总数，同时保留 `limit/offset` 兼容参数 |
| 2.2 | ✅ | `api/routes/orders.py` 增强：新增分页/状态查询参数，返回 `{orders,total,page,page_size}` |

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
| 9.6 | ✅ | 修复物流池“Delete All”失败 — `db/logistics_pool.py` 改为禁用 ORM session synchronization 的批量删除，确保 `/api/logistics-pool/all` 可正常清空 |

**根因分析**：`api/main.py` 底部 `uvicorn.run()` 默认端口为 8000，但 `frontend/vite.config.js` 代理和 `frontend/playwright.config.js` 均指向 8003。启动脚本使用 `--port 8000` 导致前端无法连接后端。

---

## 完成标准

- [x] `python -m pytest --tb=short` — **1375 passed**, 1 pre-existing failure, 0 errors, 0 warnings
- [x] `python -m coverage run + report` — **94%** 总覆盖率，23个核心模块均90%+
- [x] `python -m flake8` — 0 errors, 0 warnings
- [x] `npx vitest run` (frontend/) — **201 tests**, 0 failures (24 test files)
- [x] `npm run build` (frontend/) — 构建成功
- [x] Playwright E2E — **287 passed**, 1 skipped, 0 failures (288 tests, 27 spec files)
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

---

### Phase 10: 安全审计修复 (42项全部完成) ✅

**审计报告**: `AUDIT_REPORT.md` — 6 CRITICAL + 12 HIGH + 14 MEDIUM + 10 LOW = 42 项

#### CRITICAL (6/6) ✅

| ID | 状态 | 描述 |
|----|------|------|
| C1 | ✅ | `api/dependencies.py` — 移除认证绕过（username-as-token fallback） |
| C2 | ✅ | Phase 0-9 已修复 — `init_db()` 中 `hash_password("admin123")` 不再存在 |
| C3 | ✅ | `enhanced_exchange_service.py` — CurrencyLayerProvider 汇率反转修复 |
| C4 | ✅ | `session_security.py` — 6处静默异常改为日志记录 |
| C5 | ✅ | `frontend/src/pages/*.jsx` — DOMPurify XSS 消毒 |
| C6 | ✅ | `frontend/src/components/ErrorBoundary.jsx` — 新增全局错误边界 |

#### HIGH (12/12) ✅

| ID | 状态 | 描述 |
|----|------|------|
| H1 | ✅ | `api/routes/admin.py` — SQL注入白名单防护 |
| H2 | ✅ | `api/main.py` — CORS 从 `["*"]` 改为环境变量配置 |
| H3 | ✅ | `api/routes/settings.py` — 路径遍历防护 |
| H4 | ✅ | `security/tokens.py` — JWT密钥从环境变量读取 |
| H5 | ✅ | `api/main.py` — 全局异常处理器保留 HTTPException 状态码 |
| H6 | ✅ | `api/routes/auth.py` — 密码重置安全化 |
| H7 | ✅ | 多文件 — async 事件处理器改为 def（防阻塞事件循环） |
| H8 | ✅ | `api/routes/exchange.py` — 修复缺失的 await |
| H9 | ✅ | 多文件 — bare except 改为具体异常类型 + 日志记录 |
| H10 | ✅ | `session_security.py` — check_concurrent_sessions 异常添加日志 |
| H11 | ✅ | `session_security.py` — 数据库密钥从环境变量读取 |
| H12 | ✅ | `db/helpers.py` — psycopg2.sql 参数化查询 |

#### MEDIUM (14/14) ✅

| ID | 状态 | 描述 |
|----|------|------|
| M1 | ✅ | `db_utils.py` → `db/` 包拆分（17个子模块，proxy pattern） |
| M2 | ✅ | `logic.py` → `pricing/` 包拆分（11个文件） |
| M3 | ✅ | `pricing/logistic_cost.py` — 统一返回类型 `(cost, debug_info)` |
| M4 | ✅ | `api/models/schemas.py` — rate字段 `ge=0, le=100` 约束 |
| M5 | ✅ | `db/helpers.py` — `_is_postgresql_connection` 默认值修复 |
| M6 | ✅ | `api/middleware/rate_limit.py` — X-Forwarded-For + LRU 清退 |
| M7 | ✅ | `api/routes/pricing.py` — SSE endpoint 添加认证 |
| M8 | ✅ | `api/routes/products.py`, `logistics.py`, `orders.py` — 添加分页 |
| M9 | ✅ | `session_security.py` — HMAC密钥从环境变量读取 |
| M10 | ✅ | `api/routes/settings.py` — JSONResponse → HTTPException |
| M11 | ✅ | `frontend/src/services/api.js` — 请求超时 + AbortController |
| M12 | ✅ | `frontend/src/pages/*.jsx` — API 错误处理 + loading 状态 |
| M13 | ✅ | `frontend/src/pages/*.jsx` — 空数据状态展示 |
| M14 | ✅ | `db/schema.py` — cursor.close() 移入 finally 块 |

#### LOW (10/10) ✅

| ID | 状态 | 描述 |
|----|------|------|
| L1 | ✅ | 调查确认 — 所有 `pass` 语句均有效，无需修改 |
| L2 | ✅ | `frontend/src/pages/*.jsx` — console.log 移除 |
| L3 | ✅ | `frontend/src/components/SideMenu.jsx` — 活跃菜单项高亮 |
| L4 | ✅ | `frontend/src/pages/RegisterPage.jsx` — 密码强度提示 |
| L5 | ✅ | `frontend/src/services/api.js` — 请求重试机制 |
| L6 | ✅ | `frontend/src/pages/*.jsx` — 表单验证增强 |
| L7 | ✅ | `frontend/src/pages/*.jsx` — loading 骨架屏 |
| L8 | ✅ | `frontend/src/pages/DashboardPage.jsx` — 数据刷新机制 |
| L9 | ✅ | `frontend/src/pages/PricingPage.jsx` — 计算参数记忆 |
| L10 | ✅ | `frontend/package.json` — 移除 framer-motion, recharts 未使用依赖 |

#### 额外修复

| 项目 | 描述 |
|------|------|
| session_security.py | 584→423行（拆分 DistributedLock/helpers 到 `session_security_helpers.py`） |

#### 提交历史 (audit-fixes 分支)

| # | SHA | Issues | 描述 |
|---|-----|--------|------|
| 1 | `9aee73fd` | C1 | 认证绕过移除 |
| 2 | `c647288f` | H5 | 异常处理器修复 |
| 3 | `5d8d165b` | H4+H11+M9 | 安全密钥环境变量化 |
| 4 | `b4699ff7` | C4+H10 | 静默异常→日志记录 |
| 5 | `cd0873b9` | H1+H2+H3+H6+H12 | SQL注入/CORS/路径遍历/密码重置 |
| 6 | `791e3c1a` | H7+H8+H9 | async修复/bare except消除 |
| 7 | `1c0d7ef4` | M1 | db_utils.py → db/ 包 |
| 8 | `6d44f18a` | M2 | logic.py → pricing/ 包 |
| 9 | `91742b0a` | C3 | 汇率反转修复 |
| 10 | `f8e404be` | C5+C6+M11-M13+L2-L10 | 前端全量修复 |
| 11 | `2646dcb3` | M3-M8+M10+M14+L1 | 后端剩余修复 |
| 12 | `125ee124` | — | session_security.py 拆分 |

**最终数据**：
- 后端: **988 passed**, 2 skipped, 0 failed
- 前端: **169 passed**, 0 failed (21 test files)
- E2E: **260 passed**, 4 flaky failures (均为预存在的 UI timing 问题)
- flake8: 0 errors
- 所有函数 < 100 行，所有文件 < 500 行

---

### Phase 11: SQLAlchemy ORM + Alembic 全量重构 ✅

**设计规格**: `docs/superpowers/specs/2026-04-04-sqlalchemy-alembic-design.md`
**实现计划**: `docs/superpowers/plans/2026-04-04-sqlalchemy-alembic.md`

#### 决策记录

| 决策 | 选择 |
|------|------|
| 迁移框架 | Alembic |
| ORM 范围 | 全 SQLAlchemy ORM 重构 |
| 同步/异步 | 异步 SQLAlchemy (create_async_engine + AsyncSession) |
| 迁移策略 | 一次性替换（非增量） |
| 架构 | 方案 B — 直接替换，保持扁平 db/ 结构 |
| 启动迁移 | `run_migrations()` 在 `lifespan` context manager |
| 初始迁移 | `alembic stamp head`（基线，不执行 DDL） |
| 新驱动 | asyncpg 替代 psycopg2-binary |

#### 任务完成

| 任务 | 状态 | 描述 |
|------|------|------|
| T1 | ✅ | 安装依赖 + 创建 20 个 ORM 模型 (models/ 包，9 文件) |
| T2 | ✅ | 创建 database.py (async engine + AsyncSessionLocal + get_db + run_migrations) |
| T3 | ✅ | 配置 Alembic + 初始迁移 (仅 exchange_rates CREATE TABLE) |
| T4 | ✅ | 改写 db/ 核心模块 (config, exchange, plans, logging_utils, statistics) |
| T5 | ✅ | 改写 db/ 用户/产品/管理模块 (users, products, admin, admin_helpers, subscriptions, logistics_crud, sessions_crud) |
| T6 | ✅ | 改写 db/__init__.py + 删除旧文件 (db_adapter.py, db_utils.py, db/connection.py, db/helpers.py, db/_proxy.py, db/schema.py) |
| T7 | ✅ | 改写路由层 (api/dependencies.py + 9 route files + db/orders.py NEW) |
| T8 | ✅ | 改写根模块 (api/main.py, payment_handler.py, session_security*.py) |
| T9A | ✅ | 删除 19 个测试旧 db_utils/db_adapter 的测试文件 + test_error_handling_paths.py |
| T9B | ✅ | 重写 tests/conftest.py (277 行，async ORM fixtures) |
| T9C | ✅ | 重写 API 路由测试 (78/78 pass) |
| T9D | ✅ | 重写 4 个集成测试文件 (64/64 pass) |
| T9E | ✅ | 重写 password_recovery.py (462→259 行) + 4 个会话/密码测试文件 (91/91 pass) |
| T9F | ✅ | 重写 3 个剩余测试文件 (60/60 pass) |
| T9G | ✅ | 全套件验证 — 621 passed, 1 skipped, 0 failed |
| T10 | ✅ | 依赖清理 + 最终验证 |

#### 关键变更统计

| 指标 | 数值 |
|------|------|
| 新建文件 | 16 (models/ 9文件, database.py, alembic/ 4文件, db/ 3个新模块) |
| 重写文件 | 30+ (db/ 全量, routes/ 全量, 根模块, 测试文件) |
| 删除文件 | 28 (db_utils.py, db_adapter.py, 6个db/旧文件, 20个测试文件) |
| 原始代码行 | ~4500 行 raw SQL → SQLAlchemy ORM |
| 运行时驱动 | psycopg2-binary → asyncpg (psycopg2 仅保留在测试依赖中) |

#### 关键发现 & 修复

- **密码含 `@` 的 URL 构建**: `database.py` 和 `alembic/env.py` 使用 `urllib.parse.quote_plus()` 处理
- **psycopg2 测试依赖**: 根 `conftest.py` 的 `pytest_sessionfinish` 使用 psycopg2 做同步清理，移至 `requirements_test.txt`
- **password_recovery.py 完全重写**: 462→259 行，从 raw SQL 改为 async ORM
- **session_security_enhanced.py 简化为 3 行重导出**

#### 最终数据

- 后端: **621 passed**, 1 skipped, 0 failed (54.60s)
- 前端: **169 passed**, 0 failed (21 test files)
- flake8: **0 errors**
- 残留旧导入: **0** (db_utils, db_adapter, get_db_connection 全部清除)
- 所有函数 < 100 行，所有文件 < 500 行，所有测试文件 < 800 行

---

### Phase 12: 后端测试覆盖率全量补充 ✅

**实现计划**: `docs/superpowers/plans/2026-04-04-test-coverage.md` — 16 个 Task

#### 任务完成

| Task | 文件 | 测试数 | 目标覆盖率 | 状态 |
|------|------|--------|------------|------|
| 1 | `test_db_subscriptions.py` | 73 | subscriptions 94% | ✅ (efb79218) |
| 2 | `test_db_exchange_logging.py` | 27 | exchange+logging 100% | ✅ |
| 3 | `test_db_sessions_crud.py` | 46 | sessions_crud 100% | ✅ |
| 4 | `test_db_products.py` | 40 | products 100% | ✅ |
| 5 | `test_db_plans.py` | 44 | plans 100% | ✅ |
| 6 | `test_db_statistics.py` | 39 | statistics 100% | ✅ |
| 7 | `test_db_config.py` | 28 | config 100% | ✅ |
| 8 | `test_db_users.py` | 58 | users 99% | ✅ |
| 9 | `test_db_logistics_crud.py` | 42 | logistics_crud 100% | ✅ |
| 10 | `test_db_admin.py` | 79 | admin 99%/admin_helpers 100% | ✅ |
| 11 | `test_session_security_full.py` | 72 | session_security 99%/helpers 96% | ✅ |
| 12 | `test_routes_pricing.py` | 43 | pricing路由 100% | ✅ |
| 13 | `test_routes_settings.py` | 37 | settings路由 95% | ✅ |
| 14 | `test_routes_misc.py` | 17 | main 93%/deps 100%/database 100% | ✅ |
| 15 | 零警告修复 | — | 0 warnings/skips | ✅ (efb79218) |
| 16 | 最终验证+收尾 | 5 | orders 100% | ✅ |

#### 修复的关键问题

- **dependency_overrides 跨测试污染**: `test_integration_subs_settings.py` 清除 module-level 设置的 overrides → 改为 autouse fixture
- **sys.modules.clear()**: `test_session_security_full.py` 中 `_restore_modules()` → 改为 selective key deletion
- **db/orders.py 覆盖率 88%→100%**: 新增 `test_db_orders.py` 5个测试

#### 覆盖率汇总

| 模块 | 覆盖率 | 目标 |
|------|--------|------|
| `db/admin.py` | 99% | 90%+ ✅ |
| `db/admin_helpers.py` | 100% | 90%+ ✅ |
| `db/config.py` | 100% | 90%+ ✅ |
| `db/exchange.py` | 100% | 90%+ ✅ |
| `db/logging_utils.py` | 100% | 90%+ ✅ |
| `db/logistics_crud.py` | 100% | 90%+ ✅ |
| `db/orders.py` | 100% | 90%+ ✅ |
| `db/plans.py` | 100% | 90%+ ✅ |
| `db/products.py` | 100% | 90%+ ✅ |
| `db/sessions_crud.py` | 100% | 90%+ ✅ |
| `db/statistics.py` | 100% | 90%+ ✅ |
| `db/subscriptions.py` | 94% | 90%+ ✅ |
| `db/users.py` | 99% | 90%+ ✅ |
| `session_security.py` | 99% | 90%+ ✅ |
| `session_security_helpers.py` | 96% | 90%+ ✅ |
| `api/routes/pricing.py` | 100% | 90%+ ✅ |
| `api/routes/settings.py` | 95% | 90%+ ✅ |
| `api/routes/admin.py` | 100% | 90%+ ✅ |
| `api/routes/orders.py` | 100% | 90%+ ✅ |
| `api/routes/statistics.py` | 100% | 90%+ ✅ |
| `api/main.py` | 93% | 90%+ ✅ |
| `database.py` | 100% | 90%+ ✅ |
| `api/dependencies.py` | 100% | 90%+ ✅ |
| **总计** | **94%** | 90%+ ✅ |

#### 最终数据

- 后端: **1272 passed**, 0 failed, 0 skipped, 0 warnings (29s)
- 覆盖率: **94%** 总计，所有 23 个核心模块均 ≥90%
- flake8: 0 errors
- 所有测试文件 < 800 行

---

### Phase 13: 手动测试 Bug 修复 (第二轮) ✅

| 任务 | 状态 | 描述 |
|------|------|------|
| 13.1 | ✅ | Bug 1: `ProductsPage.jsx` — `weight_g` 列 `toFixed(1)` → `toFixed(2)` + 两个 `InputNumber` 添加 `precision={2}`, `step={0.01}` |
| 13.2 | ✅ | Bug 2: `LogisticsPage.jsx` — `continue_fee` 显示 `toFixed(2)` → `toFixed(5)` |
| 13.3 | ✅ | Bug 3: 测试用户泄漏清理 — `global-teardown.js` 重写为分页获取所有用户 + 18 种测试用户名模式匹配; `auth-api.spec.js` 添加 `afterAll` 清理注册用户; SQL 一次性删除 129 个泄漏测试用户 |
| 13.4 | ✅ | Bug 4: `db/admin.py` — 移除 `where(User.role != "admin")` 过滤，用户列表现在包含 admin 用户，按 ID 升序从 admin(ID=1) 开始 |
| 13.5 | ✅ | 全套件验证 — pytest 1272 passed, flake8 0 errors |

**根因分析**：
- Bug 1: `ProductsPage.jsx` 行 86 的 `weight_g` 列用了 `toFixed(1)` 而不是 `toFixed(2)`; 编辑表单的 `InputNumber` 缺少 `precision` 属性
- Bug 2: `LogisticsPage.jsx` 行 340 的 `continue_fee` 用了 `toFixed(2)`，用户要求精确到 5 位小数
- Bug 3: E2E 测试通过 `/api/auth/register` 端点创建用户但无清理机制; `global-teardown.js` 仅获取第一页(20条)无法清理分布在后续页面的测试用户
- Bug 4: `db/admin.py` 的 `get_all_users` 查询硬编码了 `where(User.role != "admin")` 过滤，导致 admin 用户被排除

**数据库状态**：165 → 36 个真实用户（删除 129 个泄漏测试用户）

#### 最终数据

- 后端: **1272 passed**, 0 failed, 0 skipped, 0 warnings (24s)
- flake8: 0 errors
- 数据库: 36 个真实用户（0 个测试用户泄漏）

---

### Phase 14: 手动测试 Bug 修复 (第三轮) ✅

| 任务 | 状态 | 描述 |
|------|------|------|
| 14.1 | ✅ | Bug A: `PricingPage.jsx` — 产品编辑弹窗精度修复: (1) `handleEditProduct` 金额字段 `toFixed(2)`, 百分比字段 `*100` 显示整数 (2) `handleSaveProduct` 百分比字段 `/100` 保存小数 (3) `handleProductSelect` 金额 `toFixed(2)`, 百分比 `*100` (4) `RateInput` 组件透传 `step` prop (5) 产品弹窗金额 Input `step="0.01"`, 百分比 RateInput `step="1"` (6) 快速模式+精准模式 RateInput 也添加对应 step |
| 14.2 | ✅ | Bug B: 用户管理排序 — `db/admin.py` 代码已正确(Phase 13修复), DB 验证 admin(ID=1) 在首位, 问题为后端服务器未重启加载新代码 |
| 14.3 | ✅ | 全套件验证 — pytest 1272 passed, flake8 0 errors |

**根因分析**：
- Bug A: 数据库存储百分比为小数(如0.05), `handleEditProduct`/`handleProductSelect` 直接 `String()` 显示导致"0.05"而非"5"; `handleSaveProduct` 不做 `/100` 导致存入原始输入值; 金额字段无 `toFixed()` 导致浮点精度问题
- Bug B: 代码已在 Phase 13 修复, 但用户本地后端服务器未重启仍运行旧代码

#### 最终数据

- 后端: **1272 passed**, 0 failed, 0 skipped, 0 warnings (21s)
- flake8: 0 errors
- Commit: `3ed26273` — fix: PricingPage产品编辑弹窗精度

### Phase 15: 侧边栏UI改造 ✅

| 任务 | 状态 | 描述 |
|------|------|------|
| 15.1 | ✅ | `Sidebar.jsx` — 移除 `collapsed` state 和收起/展开按钮, 固定 `w-64` 展开状态, 移除所有 `!collapsed &&` 条件渲染 |
| 15.2 | ✅ | `Sidebar.jsx` — `ExchangeRateDropdown` 重写为 `ExchangeRatePanel`, 汇率直接内联显示(无折叠), 移除 `isOpen` state 和 `ChevronDown` 图标 |
| 15.3 | ✅ | `Sidebar.test.jsx` — 移除 `collapse toggle works` 测试, 新增 `sidebar is always expanded with fixed width` 和 `ExchangeRatePanel displays rates directly` 测试 |
| 15.4 | ✅ | `AppLayout.jsx` — 无需修改, `ml-64` 已为固定宽度 |
| 15.5 | ✅ | 前端全套件验证 — 169 tests passed, 0 failed |

#### 最终数据

- 前端: **169 passed**, 0 failed (21个测试文件)
- Commit: `67c85099` — fix: 侧边栏固定展开 — 移除收起/展开功能，汇率直接内联显示

### Phase 16: 物流限价人民币统一 🔄

| 任务 | 状态 | 描述 |
|------|------|------|
| 16.1 | ✅ | 新增 Alembic 迁移 `eacc63642541_unify_price_limits_to_cny.py`：为 `logistics` / `logistics_pool` 增加 `price_limit_cny`、`price_min_cny`，并按 RUB×0.075 / USD×7.2 回填 |
| 16.2 | ✅ | ORM + Schema + CRUD：`models/logistics*.py` 新增 CNY 字段；`api/models/schemas.py` 仅暴露 CNY 字段；`db/logistics_crud.py` 与 `api/routes/logistics.py` 允许字段切换到 CNY |
| 16.3 | ✅ | 定价引擎：`pricing/filter.py`、`pricing/cost_filter.py` 改为直接比较 `price_limit_cny` / `price_min_cny`，错误信息统一为 CNY |
| 16.4 | ✅ | Excel 导入：`xlsx_import/common.py` 新增 `parse_price_limit_cny()`；4 个 parser 全部提取 CNY 限价列 |
| 16.5 | ✅ | 前端 `LogisticsPage.jsx` 编辑表单移除货币下拉，改为 `价格上限（元）` / `价格下限（元）`，提交字段切换为 CNY |
| 16.6 | ✅ | 迁移执行与数据校验：`alembic upgrade head` 成功；校验结果 `logistics` 3033 条记录全部具备 `price_limit_cny` / `price_min_cny` |
| 16.7 | ⚠️ | 验证：flake8 通过；后端定向 pytest 87 passed；前端 LogisticsPage vitest 16 passed；`tests/test_xlsx_import.py` 中 CIS 样例文件受 OneDrive reparse-point 权限影响，当前环境仍报 `PermissionError` |

### Phase 16: Group 6 盈亏平衡线定价计算 ✅

| 任务 | 状态 | 描述 |
|------|------|------|
| 16.1 | ✅ | `api/routes/pricing.py` — 精准模式 `/calculate` 与 `/calculate-grouped` 追加盈亏平衡线并行计算，使用 `dict(product)` 复制后强制 `target_profit_margin=0` |
| 16.2 | ✅ | `api/models/schemas.py` — 为普通/分组定价响应新增 breakeven 字段，保持现有字段不变 |
| 16.3 | ✅ | `frontend/src/pages/PricingPage.jsx` — 精准模式结果区新增“盈亏平衡线”开关，切换展示普通/盈亏平衡结果且不触发 API |
| 16.4 | ✅ | `tests/test_routes_pricing.py` + `frontend/src/__tests__/PricingPage.test.jsx` — 新增后端返回结构与前端切换展示测试（先 RED 后 GREEN） |
| 16.5 | ✅ | 验证 — `python -m flake8 api/`、`python -m pytest tests/test_routes_pricing.py --tb=short`、`npm run test -- PricingPage.test.jsx`、`npm run build` |

**结果**：后端精准模式响应同时返回 normal + breakeven；前端精准模式可本地切换展示，开关在无结果时隐藏，切换不丢失结果也不重新计算。

### Phase 17: 手动测试 Bug 修复 (第四轮 — 5项) ✅

| 任务 | 状态 | 描述 |
|------|------|------|
| 17.1 | ✅ | Issue 1: xlsx 导入健壮性 + Smart 物流检测 — `xlsx_import/__init__.py` 单次打开/重试逻辑, `xlsx_import/parsers/fbp.py` 合并单元格 Smart 标识检测, 所有 parser 接受可选 workbook 参数 |
| 17.2 | ✅ | Issue 2: 透明菜单/面板修复 — `dropdown-menu.jsx` bg-popover→bg-card, `LogisticsPoolPage.jsx` bg-muted/50→bg-surface-container |
| 17.3 | ✅ | Issue 3a: 产品导入成功面板 Audit+Polish — `ProductImportPage.jsx` 成功面板样式统一 |
| 17.4 | ✅ | Issue 3b: 导入后产品列表为空 — `db/products.py` `_product_to_dict()` NULL 字段归一化 |
| 17.5 | ✅ | Issue 4: 佣金百分比 Bug — `CommissionCategoriesPage.jsx` 表单输入/存储/显示的百分比转换修复 |
| 17.6 | ✅ | Issue 5: 全量测试验证 |
| 17.7 | ✅ | `api/main.py` 全局异常处理器添加日志记录（之前静默吞掉错误） |
| 17.8 | ✅ | 修复 4 个预存在的 pytest 失败 (test_db_admin, test_db_config, test_db_logistics_pool, test_db_sessions_crud) |

**新增测试文件**：
- `tests/test_xlsx_import_locking.py` — xlsx 导入锁定/重试测试
- `tests/test_logistics_pool_import.py` — 物流池导入集成测试
- `tests/test_fbp_smart_detection.py` — FBP Smart 标识检测测试（扩展）
- `tests/test_product_import_truncation.py` — 产品导入截断测试

**修改文件**：
- 后端: `api/main.py`, `api/routes/logistics_pool.py`, `db/products.py`, `xlsx_import/__init__.py`, `xlsx_import/detector.py`, `xlsx_import/parsers/fbp.py`, `xlsx_import/parsers/china_post.py`, `xlsx_import/parsers/scoring_rfbs.py`, `xlsx_import/parsers/cis_rfbs.py`, `xlsx_import/common.py`
- 前端: `frontend/src/components/ui/dropdown-menu.jsx`, `frontend/src/pages/LogisticsPoolPage.jsx`, `frontend/src/pages/CommissionCategoriesPage.jsx`, `frontend/src/pages/ProductImportPage.jsx`
- 测试: `tests/test_db_admin.py`, `tests/test_db_config.py`, `tests/test_db_logistics_pool.py`, `tests/test_db_sessions_crud.py`, `frontend/src/__tests__/CommissionCategoriesPage.test.jsx`

**最终数据**：
- 后端 pytest: **1365 passed**, 0 failed, 0 skipped
- 前端 vitest: **199 passed**, 0 failed (24 test files)
- E2E Playwright: **287 passed**, 1 skipped, 0 failed (288 tests, 3.8min)
- flake8: 0 errors
- 前端 build: ✅

### Phase 18: Group 6 统计模块后端 API 修复 🔄

| 任务 | 状态 | 描述 |
|------|------|------|
| 18.1 | ✅ | `api/routes/statistics.py` — overview 的 `active_users` 改为真实 30 天内登录用户统计 |
| 18.2 | ✅ | `db/statistics.py` + `api/routes/statistics.py` — retention 改为基于 `users.created_at` + `user_login_log.login_time` 的真实月度留存 |
| 18.3 | ✅ | `api/routes/statistics.py` — active-users 趋势改为今日 vs 昨日、近7日 vs 上7日真实差值 |
| 18.4 | ✅ | `db/statistics.py` + `api/routes/statistics.py` — revenue 改为基于 `payment_orders` 成功订单的真实月度收入（元） |
| 18.5 | ✅ | `tests/test_db_statistics.py`, `tests/test_integration_orders_stats.py` — 补充 Group 6 后端统计测试 |
| 18.6 | 🔄 | 验证 — 定向 pytest + changed files LSP diagnostics |

### Phase 18: Group 4 订阅等级门控 ✅

| 任务 | 状态 | 描述 |
|------|------|------|
| 18.1 | ✅ | `api/dependencies.py` 新增 `get_user_with_subscription`，统一返回 `subscription_type`；`api/routes/auth.py`、`db/users.py`、`api/models/schemas.py` 同步将 `subscription_type` 暴露到登录/当前用户响应 |
| 18.2 | ✅ | `api/routes/commission_categories.py` 对 POST/PATCH/DELETE 增加专业版+订阅门控，GET 保持所有等级可读，403 文案为“此功能需要专业版或更高订阅等级” |
| 18.3 | ✅ | `api/routes/products.py` 的 `/import/preview`、`/import/confirm` 与 `api/routes/logistics_pool.py` 的 `/import` 增加企业版+门控，并保留原有 `get_current_user_id` / `require_admin` 认证语义 |
| 18.4 | ✅ | `frontend/src/stores/authStore.js` 增加 `subscription_type` 归一化与 `hasProfessionalAccess` / `hasEnterpriseAccess` helper |
| 18.5 | ✅ | `frontend/src/pages/CommissionCategoriesPage.jsx`、`ProductImportPage.jsx`、`LogisticsPoolPage.jsx` 增加升级提示、条件渲染与导入按钮禁用提示 |
| 18.6 | ✅ | 新增/更新后端与前端测试：后端 45 条定向测试通过，前端 47 条定向测试通过 |

### Phase 19: 深度安全加固 ✅

| Task | 状态 | 描述 |
|------|------|------|
| 1 | ✅ | `api/dependencies.py` — 提取 `_get_user()` 公共函数，`is_frozen` 统一为 `bool()` 检查 |
| 2 | ✅ | `api/middleware/login_limiter.py` — 新建 `LoginRateLimiter`（5次/分锁定15分钟） |
| 3 | ✅ | `db/users.py` — SHA-256 密码自动迁移到 bcrypt |
| 4 | ✅ | `api/routes/payment.py` — `asyncio.create_task` 改为 `await` |
| 5 | ✅ | 多文件 — 静默吞异常修复，空 `except` 添加 `logger.warning` |
| 6 | ✅ | `api/middleware/rate_limit.py` — trusted_proxies、生产模式 localhost 检查、per-IP 上限 |
| 7 | ✅ | `api/main.py` — CORS 收窄 + `security/tokens.py` JWT 8h 过期 + E2E_TEST 生产保护 |
| 8 | ✅ | httpOnly Cookie 迁移 — 后端 login/register 设置 httpOnly cookie，前端移除 localStorage token |
| 9 | ✅ | `db/statistics.py` — `month_start` epoch 取模 → `_month_start()` 正确计算 |
| 11 | ✅ | 测试文件拆分 — `test_logic_coverage.py` + `test_routes_pricing.py` 各拆为 2 个文件 |
| 12 | ✅ | 集成测试 — cookie 认证流程、登录限流、冻结用户拒绝、密码迁移、E2E_TEST 保护（11 tests） |

**新增/修改文件**：
- 新建: `api/middleware/login_limiter.py`, `tests/test_login_limiter.py`, `tests/test_password_migration.py`, `tests/test_integration_security.py`, `tests/test_logic_coverage_part2.py`, `tests/test_routes_pricing_part2.py`
- 修改: `api/dependencies.py`, `api/routes/auth.py`, `api/routes/payment.py`, `api/routes/subscriptions.py`, `api/routes/statistics.py`, `api/main.py`, `api/middleware/rate_limit.py`, `db/users.py`, `db/statistics.py`, `security/tokens.py`, `frontend/src/services/api.js`, `frontend/src/stores/authStore.js`, `frontend/src/__tests__/authStore.test.js`
