# SHIP_READINESS.md — 生产就绪报告

**项目**：cbprice.cn 物流定价 SaaS
**报告日期**：2026-04-22
**报告范围**：Wave 1–9 累计 68 原子 commit，P0–P3 字面清零
**HEAD**：`e7b40603`（ahead `origin/main` 68 commits，**未 push**）

---

## 1. 放行结论

- **P0（阻断）**：✅ 清零（Wave 9 复核无新增）
- **P1（严重）**：✅ 清零（Wave 9 修复 3 项真问题）
- **P2（质量）**：✅ 清零（Wave 6 重审计裁决后，Wave 9 复核无新增）
- **P3（卫生）**：✅ 清零（Wave 6 + Wave 9 裁决后）

具备生产上线条件。等待用户决定是否 `git push`。

---

## 2. 环境与版本固定

| 项 | 版本 |
|---|---|
| Python | 3.11.9 |
| Node.js | v22.22.0 |
| Alembic head | `e53fd4a44e97` |
| React | ^18.2.0 |
| Vite | ^5.1.0 |
| Tailwind CSS | ^3.4.19 |
| Zustand | ^4.5.0 |
| 数据库 | PostgreSQL（仅） |
| 后端框架 | FastAPI + SQLAlchemy 2.0 async |
| UI 组件 | shadcn/ui (Radix Primitives) + sonner + lucide-react |
| 表单 | react-hook-form |

---

## 3. 质量基线（Wave 9 主控亲跑）

| 检查项 | 命令 | 结果 |
|---|---|---|
| 后端 Lint | `python -m flake8` | **0 违规**（全仓） |
| 后端测试 | `python -m pytest` | **2154 passed, 4 skipped**（~91s） |
| 前端 Lint | `npm run lint -- --max-warnings 0` | **0 warnings** |
| 前端单测 | `npm run test` (vitest) | **37 files / 296 tests passed**（23.48s） |
| 前端构建 | `npm run build` | ✓ built in 5.89s |
| 工作区 | `git status` | clean |

**4 个 skipped**：均为 Playwright E2E，需真实运行服务器，本地单机批跑不启用。

---

## 4. Wave 6 重审计真/伪裁决表

本 Wave 针对第三方 audit 报告逐项主控复核，以防误判引入无效 churn。

| 报告项 | 主控裁决 | 处置 |
|---|---|---|
| P0：CSRF 缺失 | ❌ **误判** | `api/dependencies.py:77` 已实现，不动 |
| P2：4 个文件 >500 行 | ⚠️ **3 误判 / 1 真** | 仅 `postgres_backup_service_db.py` 573 行属实，已拆分 |
| P3：streamlit 依赖 | ⚠️ **dead branch + test mock** | 已重构为 FastAPI Request（commit `5e741cb4`） |
| P3：`db_utils` 死代码 | ✅ **真** | 已清理（commit `9147e8e0`） |
| P3：README 测试数过时 | ✅ **真** | 已更新 47→108 / 20→37（commit `90be6dec`） |
| P3：Pydantic 约束缺失 | ✅ **真** | 已加（commit `39322a26`） |
| P3：conftest 超大函数 | ✅ **真** | sessionstart 140→5 行、sessionfinish 101→17 行（commit `e08c6493`） |
| P3：backup db 573 行 | ✅ **真** | 拆为 3 Mixin 模块（commit `f14964a3`） |

**关键设计决策（Pydantic 分层）**：
`min_length=6` 放在 Pydantic schema 层会让弱密码测试返回 422 而非业务层期望的 400。最终决策：
- **Schema 层**：仅 `max_length`（防 payload 滥用）+ `min_length=1`（结构性非空）
- **业务层**：密码强度/复杂度校验保留在 `password_utils`，错误码维持 400 与 “密码不符合要求” 语义

---

## 5. Wave 1–9 累计成果（68 commits）

### 5.1 分类统计

| 类型 | 数量 |
|---|---|
| feat | 25 |
| fix | 17 |
| refactor | 9 |
| perf | 4 |
| docs | 6 |
| chore | 3 |
| security | 1 |
| test | 3 |
| **合计** | **68** |

### 5.2 主要能力落地

**认证与会话安全**
- JWT + 7 天 refresh token sliding session
- 新登录踢下旧会话（`active_sessions.inactive_reason` 字段 + 前端 `SessionKickedDialog`）
- 登录 / 登出 / 注册 / 改密 审计日志
- `check-username` 端点 IP 级严格限流 + 审计

**密码找回（完整三步流程）**
- `password_reset_tokens` 表 + 单次使用令牌服务
- 三端点：请求 → 验证 → 重置
- 前端 `ForgotPasswordPage` 三步向导
- 重置后强制清 session

**支付安全**
- 微信支付平台签名验证
- notify 回调 CAS 幂等（防双扣）
- 路由层 Suspicious 异常捕获 → `await session.rollback()` → 防止脏 CAS 被 `get_db` 自动 commit（Wave 9）
- `_parse_duration` 兼容英文 `month`/`year` billing_cycle，修复年付只开 30 天 bug（Wave 9）
- `wechat_pay_v3_api` 单测覆盖恢复

**数据一致性（Wave 9）**
- `users` 表 `lower(username)` / `lower(email)` 数据库级 functional unique 索引，彻底消除大小写并发 race 导致的 `MultipleResultsFound`

**性能（N+1 消除）**
- `get_all_users`、`batch_update_users`、`batch_add_to_my_logistics`、`confirm_product_import` 全部改批量

**前端体验**
- 草稿持久化 hook（`useDraftPersist` + sessionStorage）+ 登记、物流、定价三页接入
- `DraftRestoreDialog` 草稿恢复对话框
- 401 refresh 失败保留 `returnTo` + sonner 提示
- `LogisticsPoolPage` 表体虚拟化（`@tanstack/react-virtual`）
- `LogisticsPage` 1235 行 / `PricingPage` 1395 行拆分为模块化组件
- 用户名实时查重 + 密码强度反馈

**代码健康与合规**
- 61 ESLint 错误/警告清零
- gunicorn 升级修复 CVE-2024-1135 / CVE-2024-6827
- 4 个大文件拆分至合规行数
- 死代码清理（streamlit、`db_utils`、`session_security_enhanced` re-export shim、未用 SSE 端点）

---

## 6. 部署注意事项

- **部署位置**：`ssh SSH_USER@SERVER_IP:/var/www/ozon-pricing`
- **Push 状态**：本地 68 commit 未 push；等待用户指令
- **历史重写授权**：用户已授权本地 main 历史重写
- **Windows CRLF**：Windows 本地克隆可能出现 CRLF warning，不影响功能
- **bash 工具前缀**：任何自动化脚本必须前缀 `$env:CI='true'; $env:GIT_TERMINAL_PROMPT='0'; $env:GIT_PAGER='cat'; $env:PAGER='cat';`
- **禁区**：opencode bash 内**不得启动** `uvicorn` / server 进程（会阻塞 agent shell，已踩坑 2 次）

---

## 7. 已知限制

1. **4 个后端测试 skipped**：Playwright E2E，需要真实运行服务器，本报告不计入失败
2. **Python 运行要求**：3.10+（类型注解用到 PEP 604 `X | Y`）
3. **仅 PostgreSQL**：不兼容 SQLite / MySQL（async 驱动与 schema 迁移均绑定 PostgreSQL）
4. **未跑负载/压测**：本轮未覆盖性能基准，仅消除 N+1 逻辑级问题

---

## 8. 回滚策略

- 所有改动均为**原子 commit**，可用 `git revert <sha>` 精确回退任一能力
- 未 push，可用 `git reset --hard origin/main` 整体回滚到上游状态
- 数据库迁移头：`e53fd4a44e97`；如需回滚迁移使用 `alembic downgrade -1`

---

## 9. 下一步建议

1. 用户评审本报告
2. `git push origin main`（等用户授权）
3. SSH 部署到 `SERVER_IP:/var/www/ozon-pricing`
4. 生产环境执行 `alembic upgrade head`
5. 重启后端 / 刷新前端静态资源
6. 冒烟：登录 → 定价 → 登出 → 密码找回三步 → 支付 notify

---

---

## 10. Wave 9 专项（2026-04-22 追加）

Wave 9 执行四份独立审计（oracle P0 / oracle P1 / Junior-deep P2 / Junior-deep P3），主控逐项核实后裁决。

### 10.1 主控裁决表（22 报告项 → 5 真 / 17 伪）

| 类别 | 报告项 | 主控裁决 | 处置 |
|---|---|---|---|
| P0 | `AUDIT_REPORT.md` 含明文密码 | ✅ **真** | 删除整文件 `cc593159` |
| P0 | `docs/superpowers/plans/...` 第二处密码 | ❌ 伪 | grep 全仓不存在 |
| P1 | 微信 notify CAS 设计错误 | ❌ 伪 | CAS 单语句设计正确 |
| P1 | 路由层吞 Suspicious 异常致脏 CAS 被 commit | ✅ **真** | 注入 session，异常路径 `await session.rollback()` `3d07529f` |
| P1 | `_parse_duration` 不识别英文 billing_cycle | ✅ **真** | `payment_service.py` + `payment_handler.py` 双处兼容 + 5 测试 `8f94d353` |
| P1 | 用户名/邮箱大小写并发 race | ✅ **真** | 新增 alembic `e53fd4a44e97`：`ux_users_username_lower` + `ux_users_email_lower` functional 唯一索引 + 2 测试 `ef0b7dc2` |
| P2 | `payment_callback_enhanced.py` >500 行 | ❌ 伪 | 实测 437 行 |
| P2 | `exchange_service_providers.py` >500 行 | ❌ 伪 | 实测 410 行 |
| P2 | `redis_cache.py` >500 行 | ❌ 伪 | 实测 386 行 |
| P2 | `test_api_routes.py` >800 行 | ❌ 伪 | 实测 776 行 |
| P2 | `test_db_statistics.py` >800 行 | ❌ 伪 | 实测 682 行 |
| P2 | `test_session_security_full.py` >800 行 | ❌ 伪 | 实测 680 行 |
| P3 | 生产前端 4 处 `console.warn` | ❌ 伪 | grep 实测 0 处 |
| P3 | AGENTS.md alembic head 过时 | ❌ 伪 | 修前已是最新 |
| P3 | README 引用 `env.template` 错 | ❌ 伪 | 实测正确 |
| P3 | README "14 个页面"过时 | ✅ **真** | 修正为 19 `798bf6b1` |
| 其他 7 项 | 格式/风格建议 | ❌ 伪或非阻断 | 不动 |

**核实方法论**：Wave 6 与 Wave 9 连续两轮均发现 audit agent ~50%+ 误判率（行数虚报、grep 假阳性、对 `get_db` 自动 commit 行为不熟），故确立硬性规则：**所有 audit 输出必须经主控 `Read` + `grep` + 上下文核实后方可进入修复流水线**。

### 10.2 Wave 9 commit 清单

| Commit | 类别 | 摘要 |
|---|---|---|
| `cc593159` | security | remove obsolete AUDIT_REPORT.md (−751 lines, 明文密码清除) |
| `3d07529f` | fix(payment) | rollback transaction on suspicious wechat notify |
| `8f94d353` | fix(payment) | parse english month/year billing_cycle correctly |
| `ef0b7dc2` | fix(db) | enforce case-insensitive uniqueness on users via functional indexes |
| `798bf6b1` | docs | correct frontend page count from 14 to 19 in README |

### 10.3 Wave 9 回归基线对比

| 检查项 | Wave 7 基线 | Wave 9 新基线 |
|---|---|---|
| Backend pytest | 2147 passed, 4 skipped | **2154 passed, 4 skipped**（+7 新测试） |
| Backend flake8 | 0 | **0** |
| Frontend vitest | 37 files / 296 tests | **37 files / 296 tests** |
| Frontend lint | 0 warnings | **0 warnings** |
| Frontend build | 6.25s | **5.89s** |
| Alembic head | `87a840348f80` | `e53fd4a44e97` |

### 10.4 关键架构事实（Wave 9 确认，供运维参考）

- `database.py:get_db()` 在 `yield` 之后**自动 `await session.commit()`**；仅异常传播路径才 rollback。路由层若 try/except 吞掉 service 层 raise，脏状态会被持久化。
- `apply_wechat_payment_success` 使用 `UPDATE ... WHERE wechat_transaction_id IS NULL RETURNING ...` 单语句 CAS，天然并发安全；金额/用户/身份校验在 CAS 成功后进行。
- `create_order(billing_cycle=...)` 把参数**原样**写入 `PaymentOrder.duration`，`_parse_duration` 必须同时识别中文（"月"/"年"）与英文（`month`/`year`）。
- `users.username` / `users.email` 现存两套唯一性保障：Python 层 `func.lower()` 预检 + DB 层 functional unique 索引，并发 race 在 DB 层被终结为 `IntegrityError`。

---

**报告产出人**：Sisyphus（主控）
**签发基线**：HEAD `e7b40603`，working tree clean，ahead origin/main 68，所有质量门全绿

---

## 11. Wave 10 专项（2026-04-22 追加）

Wave 10 修复 5 类 UX/功能问题，6 个原子 commit，**主控亲自实施 + manual QA 验证**。

### 11.1 问题清单与处置

| # | 问题 | 处置 | Commit |
|---|---|---|---|
| 1 | VirtualTable 表头透明，滚动时下方内容穿透 | 表头改 `bg-muted` 不透明背景 | `0b1ebfb1` |
| 2 | 找回密码页冗余「安全提示」Alert | 删除整段 Alert | `c6a5a290` |
| 3 | 注册页 5 题、找回密码 10 题不统一 | 后端 `SECURITY_QUESTIONS` 收敛为 5 题 + 新增 GET 端点 | `46bbcf69` |
| 4 | register 流程未持久化 q1/a1，导致后续找回密码 NULL 字段 | register API 写入 q/a 双字段 | `c94608b0` |
| 5 | 找回密码 2 题校验，与注册仅 1 题不对称 | 后端/前端统一为 1 题制 | `84411b08` |
| 6 | 老用户（升级前注册）登录后无入口补填安全问题 | 登录后强制 Modal 拦截，「提交」或「退出登录」二选一 | _本 commit_ |

### 11.2 Commit 6 设计决议（用户锁定）

| 项 | 决议 |
|---|---|
| C1 拦截强度 | 仅前端 Dialog 拦截（不改后端权限） |
| C2 set 语义 | 仅首次设置（`security_q1 IS NULL` 允许；已设置 HTTP 409） |
| C3 答案归一化 | `strip+lower + bcrypt`（与 `password_recovery.py:175` verify 对称） |
| C4 admin 路径 | 不在本 commit 范围 |
| C5 逃生口 | Dialog 提供「退出登录」按钮，避免账户被锁 |

### 11.3 Commit 6 file manifest（21 文件 = 14 修改 + 7 新增）

**后端修改 7**：`security_questions.py`、`password_recovery.py`、`db/users.py`、`api/main.py`、`api/models/schemas.py`、`api/routes/auth.py`、`api/dependencies.py`

**后端新增 1**：`api/routes/auth_security.py`（POST `/api/auth/security-question`，仅首次设置）

**后端测试修改 2**：`tests/test_auth_dependencies.py`、`tests/test_api_routes.py`（+P0 回归 3 测试）

**后端测试新增 1**：`tests/test_api_security_question.py`（7 测试）

**前端修改 5**：`frontend/src/services/api.js`、`frontend/src/__tests__/api.test.js`、`frontend/src/stores/authStore.js`、`frontend/src/__tests__/authStore.test.js`、`frontend/src/components/AppLayout.jsx`

**前端新增 3**：`frontend/src/components/SecurityQuestionRequiredDialog.jsx`、`frontend/src/__tests__/SecurityQuestionRequiredDialog.test.jsx`、`frontend/src/__tests__/AppLayout.test.jsx`

### 11.4 实施期间发现并修复的集成 bug（manual QA 兜底）

| 级别 | 问题 | 根因 | 修复 |
|---|---|---|---|
| P0 | login/register response 缺 `has_security_question` → 所有用户都弹 Dialog | UserResponse 构造时遗漏 flag；`db/users.py:verify_user` dict 缺 `security_q1` key | auth.py 两处 + db/users.py 1 处补字段 + 3 回归测试 |
| P1 | Dialog 名导出但 AppLayout 用 default import → 整个前端白屏 | vitest 用 named import 通过，浏览器崩溃 | AppLayout 改 `import { SecurityQuestionRequiredDialog }` |
| P2 | AppLayout 未传 `onSuccess`/`onLogout` → 提交后 200 OK 但 Dialog 不关 | 仅传 `open` prop | AppLayout 完整集成 `handleSuccess` + `handleLogout` |

**教训**：vitest 通过 ≠ 浏览器可用；**manual QA 必须兜底**。

### 11.5 Wave 10 manual QA 截图证据

| 路径 | 截图 |
|---|---|
| legacy 用户登录 → Dialog 弹出 | `docs/qa/wave10-commit6-dialog.png` |
| 提交安全问题 → Dialog 关闭进入 `/pricing` | `docs/qa/wave10-commit6-no-dialog-after-set.png` |
| Dialog 内点「退出登录」→ 跳回 `/login` | `docs/qa/wave10-commit6-logout-escape.png` |
| modern 用户登录 → 不弹 Dialog | `docs/qa/wave10-commit6-modern-no-dialog.png` |
| 找回密码 1 题制 E2E（输入用户名 → 答题 → 重置密码 → 跳 /login，新密码 API login 200 OK） | `docs/qa/wave10-commit6-recovery-success.png` |

### 11.6 Wave 10 回归基线对比

| 检查项 | Wave 9 基线 | Wave 10 新基线 |
|---|---|---|
| Backend pytest | 2154 passed, 4 skipped | **2164 passed, 4 skipped**（+10 新测试：T6×7 + T7/P0 ×3） |
| Backend flake8 | 0 | **0** |
| Frontend vitest | 37 files / 296 tests | **39 files / 307 tests**（+2 新文件：Dialog + AppLayout） |
| Frontend lint | 0 warnings | **0 warnings** |
| Alembic head | `e53fd4a44e97` | `e53fd4a44e97`（无新迁移） |

### 11.7 Wave 10 commit 清单

| Commit | 类别 | 摘要 |
|---|---|---|
| `0b1ebfb1` | fix(ui) | VirtualTable header use opaque bg-muted background |
| `c6a5a290` | fix(ui) | remove redundant 'security tip' alert on forgot password page |
| `46bbcf69` | fix(security-questions) | unify preset list to 5 questions and expose API endpoint |
| `c94608b0` | fix(auth) | persist security_question/answer on register to prevent NULL recovery fields |
| `84411b08` | feat(security) | 找回密码统一为 1 题制（Wave 10 Commit 5） |
| _Commit 6 SHA 见 git log_ | fix(wave10/commit6) | 登录后强制 Dialog 补填安全问题（含 P0+P1+P2 集成修复 + 5 张 manual QA 截图） |

---

**Wave 10 报告产出人**：Sisyphus（主控）
**Wave 10 签发基线**：HEAD = Wave 10 Commit 6/6（SHA 见 `git log --oneline -6`），pytest 2164 / vitest 307 / flake8 0 / lint 0 全绿，manual QA 5/5 全部通过（含找回密码 1 题制 E2E + 新密码 API login 200 OK 端到端闭环）。本地 ahead origin/main 74 commits，**未 push，等待用户授权**。
