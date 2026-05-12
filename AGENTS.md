# AGENTS.md - 项目开发指南

## 重要规则

### 核心原则
- **绝不留技术债务**：任何任务都要全力完成，不怕风险，多花时间也要完成
- **不找借口**：风险高、时间紧、复杂度高都不能成为暂缓的理由
- **彻底完成**：宁可多花时间把事情做彻底，也不要留下半成品

### Oracle 决策授权（必须遵守）
- **范围**：和**设计方向无关、只和技术相关**的问题，都可以直接交给 Oracle 决定，无需事前征求用户意见
- **典型可委派给 Oracle 的问题**：
  - 依赖管理（如 `pytest-timeout` 放 requirements.txt 还是 requirements-dev.txt）
  - 配置文件位置 / 命名约定（pytest.ini vs pyproject.toml）
  - 测试隔离 / 并行策略 (xdist worker 数 / loadscope)
  - lint/format 工具选择和参数（flake8 max-line / black vs ruff）
  - 库版本固定方式 / 锁文件策略
  - CI 工作流细节 / 缓存策略 / 工具链选型
  - 调试方案 / 性能调优策略 / 重试策略
  - 错误处理模式 / 日志级别选择
- **不能委派给 Oracle 的问题**（必须问用户）：
  - 产品功能取舍 / UX 设计决策
  - 业务规则 / 定价策略 / 权限模型
  - 是否引入新依赖（如换数据库、换 UI 库）
  - 测试范围扩展 / 覆盖率目标变更
  - 任何会改变用户体验或业务行为的决策
- **执行流程**：识别为纯技术问题 → 立即 `task(subagent_type="oracle", run_in_background=true, ...)` → 等通知 → 按 Oracle 决策执行
- **优先级**：Oracle 决策视为权威；如不同意需向用户说明理由后再覆盖

### 计划管理
- **每次在 Plan 模式中修改计划，必须同步更新 PLAN.md 文件**
- PLAN.md 是唯一的计划真实来源
- 开始工作前先读取 PLAN.md 确认当前任务

### 代码规范
- Python 函数 < 100 行
- Python 文件 < 500 行
- 测试文件 < 800 行

### 架构约定
- 数据库：PostgreSQL（仅）
- 后端：FastAPI
- 前端：React + shadcn/ui (Radix Primitives) + Tailwind + Zustand + react-hook-form + sonner + lucide-react
- 认证：JWT（security/tokens.py + api/dependencies.py）
- 安全模块：security/

### Linter - 必须遵守
- **flake8检查**：所有Python代码必须通过 `python -m flake8`（无额外参数）检查
- **Pylance检查**：PyCharm 中的 Pylance 警报必须全部修复
- **Pyright检查**：Cursor 中的 Pyright 警报必须全部修复
- **随时修复**：每次修改代码后必须运行 flake8，检查 Pylance/Pyright 警报，发现错误立即修复
- **修复优先级**：E999(语法错误) > F821(未定义名称) > F8xx(逻辑错误) > E类(代码风格) > W类(警告)
- **非Python文件**：也需有合适的检查方式（如 ESLint for JavaScript, Prettier for 格式化）
- **三重检查**：flake8 + Pylance + Pyright 三个工具都必须通过，缺一不可

### 测试 - 必须遵守
- **零容忍政策**：所有测试必须通过，不允许任何警告或失败
- **pytest执行**：`python -m pytest --tb=short` 所有测试必须通过
- **测试覆盖率**：核心模块必须达到90%+覆盖率
- **持续检查**：每次代码修改后必须运行完整测试套件
- **立即修复**：发现测试失败立即修复，不允许遗留
- **并行执行**：本地默认 `pytest` 即并行运行（`pytest.ini` `addopts` 含 `-n 4 --dist=loadscope`）；如需手工调试单 worker 用 `pytest -n0`。每个 worker 自动获得独立 PostgreSQL schema（`test_master` / `test_gw*`），机制详见 [`tests/README.md` "Worker 隔离机制"](tests/README.md#worker-隔离机制)。

### 数据库 schema 完整性 - 必须遵守
- **新增/修改 CHECK 约束的迁移**：必须同步在 `scripts/check_schema_integrity.py` 的 `EXPECTED_CHECK_VALUES` 加对应不变量
- **生产部署**：`deploy/deploy.sh` 第 4.2 步会自动跑 `scripts/check_schema_integrity.py`，失败即中止部署
- **关于 `alembic check`**：当前**不在** deploy.sh 中启用——生产 DB 存在大量历史 SQLite→PostgreSQL 类型残留（TEXT vs String、REAL vs Float 等），`alembic check` 会报海量 false positive 阻塞部署。启用前提：先 autogenerate 一次性清理迁移消除历史 drift。**禁止**未做清理就把 `alembic check` 加回 deploy.sh
- **历史教训**：生产 alembic_version 曾被 stamp 至 head 但部分迁移 DDL 未真正执行（如 `d2e9f3b4c5a6` 的 `volume_mode` CHECK），导致 `volume_mode='sum_of_sides'` 写入 23514 失败。即使 `alembic check` 启用也抓不到——它只比对 model 与 DB，而本项目 CHECK 约束只在迁移 DDL 中声明（models/*.py 无 `CheckConstraint`）。`check_schema_integrity.py` 是唯一能抓此类 drift 的守卫
- **修复 stamp drift**：直接在生产事务里 DROP+CREATE 对应约束，alembic_version 不动

### 生产部署流程 - 必须遵守

**生产环境信息**
- 域名：`https://www.cbprice.cn`
- SSH：`SSH_USER@SERVER_IP`（需已配置 SSH key，无密码）
- 项目路径：`/var/www/ozon-pricing`
- venv：`/var/www/ozon-pricing/venv`
- systemd 服务：`fastapi-app.service`（gunicorn + uvicorn worker × 3，监听 `127.0.0.1:8003`）
- nginx：`/etc/nginx/sites-enabled/cbprice.cn`（前端静态 + `/api` 反代到 8003）
- 部署日志路径：`/tmp/deploy.log`（每次 deploy.sh 重写）
- gunicorn 应用日志：`/var/log/cbprice/access.log` + `/var/log/cbprice/error.log`

**标准部署三步**（绝对不要 ssh 进生产手改代码）

```powershell
# 1. 本地 push 到 main
git push origin main

# 2. SSH pull（必须分步：pull → 后台启动 deploy → 跟日志，遵循"长程命令"规则）
ssh SSH_USER@SERVER_IP 'cd /var/www/ozon-pricing && git pull origin main 2>&1 | tail -5'

# 3. 后台启动 deploy.sh + 重定向日志（前台运行会阻塞 agent shell，禁止）
ssh SSH_USER@SERVER_IP 'cd /var/www/ozon-pricing && nohup bash deploy/deploy.sh > /tmp/deploy.log 2>&1 < /dev/null & disown; echo started'

# 4. 30s 后跟日志（典型部署 30~60s 完成）
Start-Sleep -Seconds 30
ssh SSH_USER@SERVER_IP 'tail -30 /tmp/deploy.log'
```

**deploy.sh 11 步速览**
1. 预检（venv / .env 存在性）
2. 备份当前 git commit 为 `pre-deploy-<timestamp>` tag + nginx 配置快照
3. `git pull origin main`
4. `pip install -r requirements.txt`
4.1. `alembic upgrade head`
4.2. **`scripts/check_schema_integrity.py`**（schema CHECK 不变量守卫，drift 中止部署）
5. 检查前端构建产物（`frontend/dist`，本地构建后 commit 进 repo）
6. 创建 `/var/log/cbprice/`
7. 停旧服务（`streamlit-app` / `pricing-api` `systemctl stop`+`disable`）+ **`fuser -k 8003/tcp`** 杀孤儿 gunicorn
8. 安装 systemd unit `fastapi-app.service`
9. 安装 nginx 配置 + `nginx -t` + `nginx -s reload`
10. `systemctl restart fastapi-app` + 等待 healthcheck
11. 健康检查：本地 `curl 127.0.0.1:8003/api/exchange/rates` + 公网 `curl https://www.cbprice.cn`

**健康检查（部署后必跑）**
```powershell
# 公网 HTTPS 必须返回 200
(Invoke-WebRequest https://www.cbprice.cn/api/exchange/rates -TimeoutSec 10).StatusCode
# 生产 systemd 状态
ssh SSH_USER@SERVER_IP 'systemctl --no-pager status fastapi-app | head -10'
```

**回滚**
```powershell
# 列出最近备份标签
ssh SSH_USER@SERVER_IP 'cd /var/www/ozon-pricing && git tag -l "pre-deploy-*" | tail -5'
# 回滚（rollback.sh 接受 tag 参数）
ssh SSH_USER@SERVER_IP 'cd /var/www/ozon-pricing && bash deploy/rollback.sh pre-deploy-<timestamp>'
```

**故障排查**
- `deploy.sh` 退出非 0 → 看 `/tmp/deploy.log` 末尾的 `[ERROR]` 行
- 第 4.2 步失败 → schema CHECK drift，read `scripts/check_schema_integrity.py` 输出找出 drift 的约束
- 第 10 步 `Connection in use` → 8003 端口被孤儿进程占（应该已被第 7 步 fuser 清掉，若仍出现：`ssh SSH_USER@... 'ss -ltnp | grep 8003'` 找 PID 手 kill）
- FastAPI 启动失败 → `ssh SSH_USER@... 'tail -50 /var/log/cbprice/error.log'`（systemd journal 当前在该用户下不可读）
- nginx `conflicting server name` 警告 → pre-existing 历史配置残留，不影响功能，可忽略

### SECRET_KEY 轮换流程

**触发条件**：定期轮换（每 6 个月）/ 怀疑泄漏 / 关键员工离职

**前置检查**：
- security/tokens.py 已实现 SECRET_KEY 长度 ≥32 校验 + lru_cache + 无默认值
- 当前 .env 中 SECRET_KEY 必须为 32 字符以上随机字符串

**轮换步骤**：
1. **生成新密钥**（本地）：
   ```powershell
   .\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(64))"
   ```
2. **备份当前 .env**：`Copy-Item .env .env.backup-$(Get-Date -Format yyyyMMdd-HHmmss)`
3. **生产服务器更新**（SSH）：
   ```bash
   ssh SSH_USER@SERVER_IP
   cd /var/www/ozon-pricing
   cp .env .env.backup-$(date +%Y%m%d-%H%M%S)
   # 编辑 .env，替换 SECRET_KEY
   nano .env
   sudo systemctl restart fastapi-app
   ```
4. **验证**：
   ```bash
   sudo systemctl status fastapi-app | head -10
   curl -s https://www.cbprice.cn/api/exchange/rates | head -5
   ```
5. **副作用**：
   - 所有现存 JWT token 立即失效（用户被强制重新登录）
   - 监控 `/var/log/cbprice/error.log` 1 小时，确认无异常 401 spike

**回滚**：恢复 .env.backup → systemctl restart fastapi-app

### WeChat Pay 审计日志排查

**审计表**：`wechat_notify_audit_logs`（迁移 c8f3d6b9e2a1 引入）

**字段**：
- `id` / `out_trade_no` / `transaction_id` / `signature_verified` / `raw_body` / `response_code` / `response_message` / `created_at`

**常见排查场景**：

1. **签名失败 spike**（疑似攻击或证书漂移）：
   ```sql
   SELECT date_trunc('hour', created_at), COUNT(*) AS bad_sig_count
   FROM wechat_notify_audit_logs
   WHERE signature_verified = false
     AND created_at >= NOW() - INTERVAL '24 hours'
   GROUP BY 1 ORDER BY 1 DESC;
   ```
   - 单小时 >100 条 → 立即检查微信支付平台证书是否过期 + nginx access log 看 IP 分布

2. **某订单未入账**（用户报"已付款未到账"）：
   ```sql
   SELECT * FROM wechat_notify_audit_logs
   WHERE out_trade_no = '<订单号>'
   ORDER BY created_at DESC;
   ```
   - 若 `signature_verified = false` → 微信侧支付成功但回调被拒，需手工对账后补发权益
   - 若 `signature_verified = true` 且无对应 payment_orders 入账 → 检查 services/payment_service.py CAS 逻辑 + with_for_update lock

3. **重试风暴检测**（同一 transaction_id 多次回调）：
   ```sql
   SELECT transaction_id, COUNT(*) AS retry_count
   FROM wechat_notify_audit_logs
   WHERE created_at >= NOW() - INTERVAL '1 hour'
   GROUP BY transaction_id HAVING COUNT(*) > 3;
   ```
   - 正常情况下 ≤2 次（微信偶尔重发已确认通知），>3 次需排查路由 200 OK 是否正常返回

**保留策略**：
- 审计表无自动清理；建议每月归档 90 天前数据到冷存储
- 切勿信任 raw_body 内容（未验签 payload 不可作为业务依据）

**告警**：
- 接入 ops 监控：每 5 分钟统计 `WHERE signature_verified=false AND created_at>=NOW()-INTERVAL '5 min'` > 阈值时告警

**禁止事项**
- ❌ SSH 进生产 `vim` 改代码（除紧急 schema 修复，且必须事后回填到 repo）
- ❌ 跳过 deploy.sh 直接 `systemctl restart fastapi-app`（绕过 schema 守卫 + 备份 + 健康检查）
- ❌ 前台运行 `bash deploy/deploy.sh`（阻塞 agent shell，违反"长程命令"规则）
- ❌ 修改 `EXPECTED_CHECK_VALUES` 时不同步迁移 DDL（守卫脚本只校验 DB 实况）

### 通信语言
- 中文

### skill_mcp 工具调用规约（必须遵守，防止 "missing operation" 错误）

> ⚠️ **历史教训**：subagent 调用 `skill_mcp` 时只传 `mcp_name`，缺操作字段，导致工具拒绝并报 "missing operation"。

**强制签名**：
```
skill_mcp(
  mcp_name="<server-name>",        // 必填
  tool_name="<tool>"               // ← 三选一必填其一
  | resource_name="<uri>"
  | prompt_name="<prompt>",
  arguments='{...}' | {...}        // 可选；JSON 字符串或对象
)
```

**正例**（调用 playwright MCP 的 browser_navigate 工具）：
```
skill_mcp(
  mcp_name="playwright",
  tool_name="browser_navigate",
  arguments='{"url":"http://localhost:3001"}'
)
```

**反例**（缺操作字段 → "missing operation"）：
```
skill_mcp(mcp_name="playwright", arguments='{"url":"..."}')   ❌ 缺 tool_name
skill_mcp(mcp_name="playwright")                              ❌ 同上
```

**何时用哪个字段**：
- `tool_name` — 调 MCP server 的工具（最常见，~95% 场景）
- `resource_name` — 读 MCP server 暴露的资源（URI）
- `prompt_name` — 取 MCP server 预定义的 prompt 模板

**绝不能同时传两个**操作字段；只能三选一。

### 当前项目结构
```
logistics/
├── api/                  # FastAPI后端
│   ├── main.py           # FastAPI主应用（CORS、限流、异常处理）
│   ├── dependencies.py   # 共享依赖（JWT+fallback双模式认证）
│   └── routes/           # API路由
│       ├── admin.py      # 管理员用户管理
│       ├── auth.py       # 登录/注册/改密
│       ├── exchange.py   # 汇率查询
│       ├── logistics.py  # 物流记录CRUD
│       ├── orders.py     # 订单查询
│       ├── pricing.py    # 定价计算+SSE进度
│       ├── products.py   # 产品CRUD
│       ├── settings.py   # 系统设置+备份管理
│       ├── statistics.py # 统计报表
│       └── subscriptions.py # 订阅计划
├── security/             # 安全模块
│   ├── tokens.py         # JWT令牌生成/验证
│   └── utils.py          # 安全工具函数
├── models/               # SQLAlchemy ORM模型（user, product, logistics, order, session, config, cache, log）
├── db/                   # 数据库CRUD操作层（users, products, logistics_crud, orders, subscriptions, statistics, admin, sessions_crud, exchange, config, plans）
├── pricing/              # 定价计算模块（calculate_pricing, final_price, profit, logistic_cost, floating_price, exchange_rate, cost_filter, filter, select_best）
├── services/             # 业务服务层
├── alembic/              # 数据库迁移（head: 87a840348f80）
├── migrations/           # 历史迁移脚本
├── scripts/              # 运维/工具脚本
├── docs/                 # 项目文档
├── frontend/             # React前端（Vite + shadcn/ui + Radix + Tailwind + Zustand）
│   ├── src/
│   │   ├── components/   # 共享组件（AppLayout, Sidebar, TopHeader, VirtualTable等）
│   │   ├── pages/        # 14个页面
│   │   ├── stores/       # Zustand状态管理（auth, logistics, product）
│   │   ├── services/     # API调用层
│   │   ├── lib/          # 工具库
│   │   ├── styles/       # 样式
│   │   ├── __tests__/    # 前端单元测试（32个文件，Vitest + Testing Library）
│   │   └── App.jsx       # 路由入口
│   ├── tests/            # Playwright E2E测试
│   ├── vite.config.js
│   └── vitest.config.js
├── tests/                # 后端测试（111个文件，pytest + 真实PostgreSQL）
│   ├── conftest.py       # 测试夹具（PostgreSQL连接 + 测试用户清理）
│   ├── test_api_*.py     # API路由测试
│   ├── test_jwt_tokens.py           # JWT令牌测试
│   ├── test_auth_dependencies.py    # 认证依赖测试
│   ├── test_payment_handler.py      # 支付处理测试
│   ├── test_session_security*.py    # 会话安全测试
│   └── ...                          # 其他测试文件
├── database.py           # 数据库连接与会话管理（SQLAlchemy async）
├── db_config.py          # 数据库配置
├── logic.py              # 业务逻辑入口
├── exchange_service.py   # 汇率服务
├── enhanced_exchange_service.py  # 增强汇率服务
├── payment_handler.py    # 支付处理（微信支付回调）
├── payment_callback_enhanced.py  # 增强支付回调
├── postgres_backup_service.py    # PostgreSQL备份
├── conftest.py           # 根级pytest配置（仅 redis/auto_backup/postgres_backup_service mock + 测试用户清理）
├── session_security.py   # 会话安全（含 SessionSecurityEnhanced 类）
├── session_security_helpers.py   # 会话安全辅助
├── password_recovery.py  # 密码恢复
├── password_utils.py     # 密码工具
├── security_questions.py # 安全问题
├── sql_security.py       # SQL安全检查
├── redis_cache.py        # Redis缓存
├── wechat_pay_config.py  # 微信支付配置
├── wechat_pay_v3_api.py  # 微信支付V3 API
├── logger_config.py      # 日志配置
├── utils.py              # 通用工具
├── setup.cfg             # flake8配置
├── pytest.ini            # pytest配置
├── PLAN.md               # 执行计划（必须维护）
├── README.md             # 项目说明
└── AGENTS.md             # 本文件
```

### 执行流程
1. 读取 PLAN.md 获取当前任务
2. 执行任务
3. 如果任务涉及计划修改，同步更新 PLAN.md
4. 完成后更新 PLAN.md 状态

### Agent 环境限制
- **subagent 打开的项目文件夹必须限制在**: `C:\Users\hbgan\OneDrive\Robert\learn\logistics`
- 运行任务时，始终使用 `workdir` 参数指定正确的项目根目录
- 避免 subagent 扫描错误的目录导致性能问题

### Windows 目录创建规则（必须遵守，防止 EEXIST 错误）

> ⚠️ **这是本项目最常见的任务中断原因，必须严格执行以下规则。**

#### 写文件时：直接用 Write 工具，无需提前创建目录
- **opencode 的 Write 工具会自动创建父目录**，无需任何 `mkdir` 操作
- 错误做法：先 `mkdir tests/`，再写文件 → 必然 EEXIST 崩溃
- 正确做法：直接调用 Write 工具写 `tests/xxx.py`，Write 工具自己处理目录

#### 在代码/脚本中创建目录时：必须用安全 API
- **Python**：`os.makedirs(path, exist_ok=True)` ✅ &nbsp;&nbsp; `os.mkdir(path)` ❌
- **Node.js**：`fs.mkdirSync(path, { recursive: true })` ✅ &nbsp;&nbsp; `fs.mkdirSync(path)` ❌
- **PowerShell**：`New-Item -ItemType Directory -Force -Path $path` ✅ &nbsp;&nbsp; 裸 `mkdir path` ❌

#### 任务开始前：先确认目标目录是否已存在
```powershell
# 在 Bash 工具中确认目录存在，不要尝试创建
Test-Path "C:\Users\hbgan\OneDrive\Robert\learn\logistics\tests"  # 应返回 True
```
- 如果目录已存在 → 直接写文件，不执行任何 mkdir
- 如果目录不存在 → 用安全 API 创建（`exist_ok=True` / `recursive: true`）

### 长程命令进度可见性规则（必须遵守,防止"卡住无反应"）

> ⚠️ **任何预计超过 30 秒的命令都属于"长程命令"。Agent 必须保证用户随时能看到进度,绝不可让用户面对长时间静默等待。**

#### 触发条件（满足任一即视为长程命令）
- 整套测试运行（pytest 全量、playwright/vitest 全量、E2E）
- 数据库批量迁移、备份、恢复
- 大规模脚本（构建、批量导入、批量计算）
- 任何历史上观察到 ≥30s 的命令
- **任何预计整体 ≥1min 的多步任务（即使单步 <30s）**：Playwright MCP 浏览器自动化序列（login → navigate → screenshot × N）、Manual QA 多页面截图、批量文件改写（≥3 文件）、连续 ≥3 次 MCP 工具调用

#### 强制做法（三选一,优先级从高到低）

**方案 A — 后台运行 + 轮询日志（推荐,适用于 ≥2 分钟的命令）**
```powershell
# 1. 后台启动,日志写绝对路径文件
$logOut = "C:\Users\hbgan\OneDrive\Robert\learn\logistics\run.log"
$logErr = "C:\Users\hbgan\OneDrive\Robert\learn\logistics\run.err.log"
$proc = Start-Process -FilePath "npx.cmd" `
  -ArgumentList "playwright","test","--reporter=list" `
  -RedirectStandardOutput $logOut -RedirectStandardError $logErr `
  -NoNewWindow -PassThru -WorkingDirectory "C:\...\frontend"

# 2. 每 10-15 秒 Get-Content -Tail 30 一次,显示进度给用户
# 3. 设置硬超时（默认 10 分钟,Playwright 全量 25 分钟）
# 4. 进程完成或超时 → kill + 输出最终摘要
```

**方案 B — 流式 reporter（适用于 30s~2min 的命令）**
- pytest: `--tb=short -q` (避免 verbose 刷屏)
- playwright: `--reporter=line` 或 `--reporter=list`(显示每个 test 进度)
- vitest 4.x: 默认 reporter（**禁用 `--reporter=basic`/`verbose`**）
- npm/pip install: 默认输出已带进度

**方案 C — 分块执行（适用于可拆分的批量任务）**
- 把 312 个 Playwright test 按 spec 文件分批跑,每批 commit 进度
- 每完成一批就向用户回报: "已完成 X/Y, 当前进度..."

#### 反模式（禁止）
- ❌ `python -m pytest` 不带参数 + 前台等待
- ❌ `Select-String -Pattern xxx` 管道 + `Select-Object -Last N`(会缓冲整个流)
- ❌ Bash 工具默认 120s 超时,但 agent 不显示中间进度,用户面对 2 分钟黑屏
- ❌ Start-Process 后立即 `Wait-Process` 不轮询输出
- ❌ 没设置硬超时,任由命令无限挂起

#### Bash 工具单次调用静默问题（必须遵守，反复出现的痛点）

> ⚠️ **历史教训（R-STUCK-COMPOUND）**: bash 工具只在**整个命令结束时**才把 stdout 回传给 agent，agent 才能转发给用户。把 "启动后台进程 + Start-Sleep N + 健康检查" 塞进**一个 bash 调用**，用户在 N 秒内看不到任何字符，必然误判"卡住"。

##### 触发条件
- 单个 bash 调用内含 `Start-Sleep -Seconds N`（N ≥ 3）
- 单个 bash 调用内含 "启动 + 等待启动完成 + 验证" 三段式
- 任何**预计单次调用 >5 秒**的 PowerShell 复合脚本

##### 强制做法：拆分成多个 bash 调用
把"启动 + 等待 + 验证"拆成 3 个独立的 bash 工具调用：
1. **调用 1**：仅 `Start-Process` 启动后台进程，立刻返回 PID
2. **调用 2**：等待固定时间（短，如 `Start-Sleep -Seconds 5`）—— 用户能看到这是"等待"步骤
3. **调用 3**：跑健康检查 / `Invoke-WebRequest` / 读 log tail

每个调用 ≤ 3 秒返回，用户能看到清晰的步骤进度。

##### 正例
```powershell
# 调用 1（立即返回）：
Start-Process -FilePath ... -RedirectStandardOutput backend.log -NoNewWindow -PassThru | Select Id

# 调用 2（5s 返回）：
Start-Sleep -Seconds 5; "boot wait done"

# 调用 3（立即返回）：
try { (iwr http://localhost:8003/docs -Method Head -TimeoutSec 3).StatusCode } catch { "DOWN" }
Get-Content backend.log -Tail 10
```

##### 反例（禁止）
```powershell
# ❌ 整段塞一个 bash 调用，用户面对 8s 黑屏
Start-Process ...
Start-Sleep -Seconds 8
iwr http://localhost:8003/docs ...
Get-Content backend.log -Tail 20
```

##### 与"长程命令"规则的关系
- **长程命令规则**（≥30s）：用 `Start-Process` 后台 + 轮询 log
- **本规则**（5s ~ 30s 复合脚本）：拆成多个 bash 调用，每个 ≤ 3s 返回
- 两条规则互补，覆盖不同时长区间

#### Bash 工具内置 timeout 字段（必用）
- 任何长程命令调用 `bash` 工具时,**必须显式设置 `timeout` 参数**(单位 ms,默认 120000)
- Playwright 全量: `timeout: 1800000` (30 分钟)
- pytest 全量: `timeout: 600000` (10 分钟)
- alembic upgrade: `timeout: 60000` (1 分钟)
- npm install: `timeout: 300000` (5 分钟)

#### 用户反馈触发条件（自我审查）
- 若用户说"卡住了 / 没反应 / 好久没动 / 看不到进度" → 立即停止当前命令,改用方案 A/B/C 重做
- 历史教训: R-STUCK-1/2/3/4/最新 + R-PROGRESS + R-TIMEOUT 都是这条规则缺失导致

#### 进度回报频率
- 后台命令运行期间,**至少每 60 秒**给用户一条进度更新（哪怕是"仍在运行,已 X 秒"）
- 命令完成后立即报告: 总耗时 + 退出码 + 关键摘要(如 pass/fail 数)

#### 多步骤序列任务（Playwright MCP / Manual QA / 批量改写）

> ⚠️ **历史教训（R-STUCK-MCP）**: 后端启动 3.8s 完成后 agent 静默,接着调 Playwright MCP 截图 5 张,期间 1-3 分钟无任何文字输出 → 用户面对黑屏判定"卡住"。即使每个 MCP 调用 < 30s,串起来就是长程任务。

##### 触发条件
- 任何预计整体 ≥1min 的多步任务,即使每步 <30s 都满足
- 典型场景: Playwright MCP login→navigate→screenshot × N、Manual QA 多页面截图、批量改写 ≥3 个文件、连续 ≥3 次 MCP 工具调用

##### 强制做法
1. **开工前一句话宣告**: "接下来 N 步,预计 X 分钟,每步完成回报"
   - 例: "Manual QA 5 截图,预计 2-3 分钟。步骤: 登录 → /statistics → /subscriptions → /product-import → /logistics-pool → /users。每步完成报告。"
2. **每步开始前 1 行声明**: `[step k/N] 正在 {action}...`
3. **每步完成后 1 行回报**: `[step k/N done, took Ys] {summary}`
4. **任何单步失败立即停 + 报错**,不静默重试,不跳过

##### 反模式（禁止）
- ❌ 连续调用 5+ 个 MCP 工具中间不发任何文字
- ❌ 启动后端 / 验证端口存活后直接进入下一步而不告知"准备进入 step 2"
- ❌ Manual QA 截图全做完才一次性报告"完成 5 张",中间静默 2 分钟
- ❌ 假设单步 <30s 就豁免进度回报 — 串行起来就是长程任务

### 后端/前端进程启动规则（用户已授权 agent 自主管理）

  > ⚠️ **历史教训（R-START-HANG，反复出现 5+ 次，2026-05-11 终极方案落地）**

  **根因总结**（按时间顺序的失败方案）：
  1. ❌ `Start-Process -NoNewWindow -PassThru -RedirectStandardOutput`：父 PowerShell 持有子进程 stdout/stderr 句柄，uvicorn 喷 alembic/loguru 日志触发管道死锁，bash 工具卡 60-120s 超时才返回
  2. ❌ `cmd /c "start /B `"`" python ... > log 2>log"`：`cmd /c` 外层 cmd shell 持有重定向句柄，bash 工具的 PowerShell 不见 EOF，仍偶发卡 60s+ 才返回（用户报"启动后端又没反应"）
  3. ✅ **终极方案**：bash 调用 `Start-Process powershell.exe -WindowStyle Hidden -PassThru` 启动一个**独立 PowerShell 子进程**，子进程内部自己负责重定向到日志文件 — 父 bash 工具的 PowerShell **不持有任何子进程句柄**，立即返回（实测 564ms）

  **强制做法**：使用项目封装的启动脚本 `scripts/start_backend_detached.ps1` / `scripts/start_frontend_detached.ps1`。**禁止**直接在 bash 调用里写 `Start-Process -RedirectStandardOutput`、`cmd /c start /B > log`、`uvicorn` 前台等任何变体。

  **启动后端**（推荐，bash 工具 <1s 返回）：
  ```powershell
  & powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\start_backend_detached.ps1" -LogFile "backend.log"
  ```
  - 输出 `backend_launcher_pid=<pid>`（这是 launcher PowerShell 的 pid，真正 uvicorn 是它的子进程）
  - 真正 uvicorn pid 通过 `Get-NetTCPConnection -LocalPort 8003` 查
  - 自动设置 `ALLOWED_ORIGINS=http://localhost:3001` + `E2E_TEST=1` + `E2E_DISABLE_NEW_LOGIN_SESSION_KICK=1`

  **启动前端**：
  ```powershell
  & powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\start_frontend_detached.ps1" -LogFile "frontend.log"
  ```

  **必读：启动后必须按"长程命令进度可见性规则"拆分 bash 调用** ——
  - 调用 1：`scripts/start_backend_detached.ps1`（瞬时返回 launcher pid）
  - 调用 2：`Start-Sleep -Seconds 6`（uvicorn 冷启动 + alembic 需要 4-6s）
  - 调用 3：`(iwr http://localhost:8003/docs -Method Head).StatusCode` + `Get-Content backend.log -Tail 5`
  - 不要把这 3 步塞一个 bash 调用，否则用户面对 6s+ 黑屏

  **关后端/前端**：
  ```powershell
  Get-NetTCPConnection -LocalPort 8003 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
  Get-NetTCPConnection -LocalPort 3001 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
  ```

  **失去响应排查清单**（出现"启动后端没响应/卡住"时按序检查，3 步内定位）：
  1. **不要重启** —— 先 `Get-NetTCPConnection -LocalPort 8003` 确认是否 LISTENING
  2. 如已 LISTENING → 后端实际正常，只是 bash 返回流卡了 → 直接 `iwr http://localhost:8003/docs -Method Head` 验证 200
  3. 如未 LISTENING → `Get-Content backend.log -Tail 30` 找真实错误（用 detach 脚本时所有 stdout+stderr 都在 backend.log，无 backend.err.log）
  4. 真要重启 → 必须先 `Stop-Process` 杀 8003 旧 pid，再调 detach 脚本

  **绝对禁用的反模式**:
  - ❌ `Start-Process -NoNewWindow -PassThru -RedirectStandardOutput "x.log"`（方案 1，已废弃）
  - ❌ `Start-Process -WindowStyle Hidden -RedirectStandardOutput "x.log"`（无 detach，主机仍持有句柄）
  - ❌ `cmd /c "start /B ... > log 2>log"`（方案 2，已废弃，cmd 外层持有句柄）
  - ❌ `nohup`（Windows 没这命令）
  - ❌ 任何不通过 `scripts/start_*_detached.ps1` 的启动方式

### 验证原则
- **Agent 必须自己完成验证**：不要让用户手动操作来验证 agent 的修改结果
- **API 验证**：通过 `Invoke-RestMethod` 调用 API 端点验证数据正确性
- **浏览器验证**：通过 Playwright MCP 打开浏览器，登录并操作 UI 验证前端显示
- **流程**：登录获取 token → API 操作（删除旧数据/导入等）→ API 查询验证 → Playwright 浏览器端到端验证
- **截图留证**：关键验证步骤截图保存，作为验证通过的证据
