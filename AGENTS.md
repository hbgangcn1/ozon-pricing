# AGENTS.md - 项目开发指南

## 重要规则

### 核心原则
- **绝不留技术债务**：任何任务都要全力完成，不怕风险，多花时间也要完成
- **不找借口**：风险高、时间紧、复杂度高都不能成为暂缓的理由
- **彻底完成**：宁可多花时间把事情做彻底，也不要留下半成品

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
- 前端：React + Ant Design + Zustand + Tailwind
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

### 通信语言
- 中文

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
├── frontend/             # React前端（Vite + Ant Design + Zustand）
│   ├── src/
│   │   ├── components/   # 通用组件（TopHeader, SideMenu, Sidebar等）
│   │   ├── pages/        # 14个页面
│   │   ├── stores/       # Zustand状态管理（auth, logistics, product）
│   │   ├── services/     # API调用层
│   │   ├── lib/          # 工具库
│   │   ├── styles/       # 样式
│   │   ├── __tests__/    # 前端测试（21个文件，169个测试）
│   │   └── App.jsx       # 路由入口
│   ├── vite.config.js
│   └── vitest.config.js
├── tests/                # 后端测试（984个测试）
│   ├── conftest.py       # 测试夹具（PostgreSQL连接）
│   ├── test_db_utils_coverage_*.py  # db_utils覆盖率测试（5个文件）
│   ├── test_logic_coverage.py       # logic.py覆盖率测试
│   ├── test_api_routes*.py          # API路由测试（2个文件）
│   ├── test_api_main.py             # FastAPI主应用测试
│   ├── test_jwt_tokens.py           # JWT令牌测试
│   ├── test_auth_dependencies.py    # 认证依赖测试
│   ├── test_payment_handler.py      # 支付处理测试
│   └── ...                          # 其他测试文件
├── db_utils.py           # 数据库工具（核心，~4250行）
├── logic.py              # 业务逻辑（定价计算等）
├── db_adapter.py         # 数据库适配器（SQL转换、连接池）
├── db_config.py          # 数据库配置
├── payment_handler.py    # 支付处理（微信支付回调）
├── payment_callback_enhanced.py  # 增强支付回调
├── conftest.py           # 根级pytest配置
├── session_security.py   # 会话安全
├── session_security_enhanced.py  # 增强会话安全
├── password_recovery.py  # 密码恢复
├── password_utils.py     # 密码工具
├── security_questions.py # 安全问题
├── sql_security.py       # SQL安全检查
├── redis_cache.py        # Redis缓存
├── exchange_service.py   # 汇率服务
├── enhanced_exchange_service.py  # 增强汇率服务
├── postgres_backup_service.py    # PostgreSQL备份
├── wechat_pay_config.py  # 微信支付配置
├── wechat_pay_v3_api.py  # 微信支付V3 API
├── logger_config.py      # 日志配置
├── utils.py              # 通用工具
├── setup.cfg             # flake8配置
├── pytest.ini            # pytest配置
├── PLAN.md               # 执行计划（必须维护）
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

### 严禁在 opencode 的 bash/terminal 中启动后端进程（uvicorn、python server 等）
  - 原因：`Start-Process`、直接运行 `uvicorn` 等方式会阻塞 agent shell，导致 agent 完全失去响应
  - 已踩坑 2 次，每次都需要用户手动终止 session
  - 正确做法：请用户在独立终端中手动运行 `.\start_dev.ps1` 或 `uvicorn api.main:app --reload --port 8003`
  - 如需验证后端是否运行，使用 `Invoke-WebRequest http://localhost:8003/docs -Method Head` 检查即可

### 验证原则
- **Agent 必须自己完成验证**：不要让用户手动操作来验证 agent 的修改结果
- **API 验证**：通过 `Invoke-RestMethod` 调用 API 端点验证数据正确性
- **浏览器验证**：通过 Playwright MCP 打开浏览器，登录并操作 UI 验证前端显示
- **流程**：登录获取 token → API 操作（删除旧数据/导入等）→ API 查询验证 → Playwright 浏览器端到端验证
- **截图留证**：关键验证步骤截图保存，作为验证通过的证据
