# SHIP_READINESS.md — 生产就绪报告

**项目**：cbprice.cn 物流定价 SaaS
**报告日期**：2026-04-22
**报告范围**：Wave 1–7 累计 61 原子 commit，P0–P3 字面清零
**HEAD**：`f14964a3`（ahead `origin/main` 61 commits，**未 push**）

---

## 1. 放行结论

- **P0（阻断）**：✅ 清零
- **P1（严重）**：✅ 清零
- **P2（质量）**：✅ 清零（Wave 6 重审计裁决后）
- **P3（卫生）**：✅ 清零（Wave 6 重审计裁决后）

具备生产上线条件。等待用户决定是否 `git push`。

---

## 2. 环境与版本固定

| 项 | 版本 |
|---|---|
| Python | 3.11.9 |
| Node.js | v22.22.0 |
| Alembic head | `87a840348f80` |
| React | ^18.2.0 |
| Vite | ^5.1.0 |
| Tailwind CSS | ^3.4.19 |
| Zustand | ^4.5.0 |
| 数据库 | PostgreSQL（仅） |
| 后端框架 | FastAPI + SQLAlchemy 2.0 async |
| UI 组件 | shadcn/ui (Radix Primitives) + sonner + lucide-react |
| 表单 | react-hook-form |

---

## 3. 质量基线（Wave 7 主控亲跑）

| 检查项 | 命令 | 结果 |
|---|---|---|
| 后端 Lint | `python -m flake8` | **0 违规**（全仓） |
| 后端测试 | `python -m pytest` | **2147 passed, 4 skipped**（~66s） |
| 前端 Lint | `npm run lint -- --max-warnings 0` | **0 warnings** |
| 前端单测 | `npm run test` (vitest) | **37 files / 296 tests passed**（22.96s） |
| 前端构建 | `npm run build` | ✓ built in 6.25s |
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

## 5. Wave 1–7 累计成果（61 commits）

### 5.1 分类统计

| 类型 | 数量 |
|---|---|
| feat | 25 |
| fix | 14 |
| refactor | 9 |
| perf | 4 |
| chore | 3 |
| docs | 3 |
| test | 3 |
| **合计** | **61** |

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
- `wechat_pay_v3_api` 单测覆盖恢复

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
- **Push 状态**：本地 61 commit 未 push；等待用户指令
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
- 数据库迁移头：`87a840348f80`；如需回滚迁移使用 `alembic downgrade -1`

---

## 9. 下一步建议

1. 用户评审本报告
2. `git push origin main`（等用户授权）
3. SSH 部署到 `SERVER_IP:/var/www/ozon-pricing`
4. 生产环境执行 `alembic upgrade head`
5. 重启后端 / 刷新前端静态资源
6. 冒烟：登录 → 定价 → 登出 → 密码找回三步 → 支付 notify

---

**报告产出人**：Sisyphus（主控）
**签发基线**：HEAD `f14964a3`，working tree clean，ahead origin/main 61，所有质量门全绿
