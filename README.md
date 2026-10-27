# 物流定价系统

基于 FastAPI + React 的现代化跨境电商物流定价管理系统，提供产品管理、物流规则配置、智能定价计算、数据统计、订阅管理等功能。

## 快速启动

### 方法一：使用批处理脚本（推荐）

1. **安装依赖**：
   ```bash
   install_dependencies.bat
   ```

2. **启动应用**：
   ```bash
   start_app.bat
   ```

### 方法二：使用 PowerShell

```powershell
.\start_app.ps1
```

### 开发环境联合启动脚本

如果需要同时启动 FastAPI 后端和 Vite 前端开发服务，可直接使用：

```powershell
.\start_dev.ps1
```

或者在 CMD 中运行：

```bat
start_dev.bat
```

启动后访问地址：
- 后端：`http://localhost:8003`
- 前端：`http://localhost:3001`

### 方法三：手动启动

1. **激活虚拟环境**：
   ```bash
   .venv\Scripts\activate
   ```

2. **启动后端**：
   ```bash
   uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
   ```

3. **启动前端**（新终端）：
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

## 技术栈

### 后端
- **FastAPI** — REST API 框架
- **SQLAlchemy 2.0** (async) — ORM
- **Alembic** — 数据库迁移
- **PostgreSQL** (asyncpg) — 主数据库
- **Pydantic v2** — 数据校验
- **PyJWT** — JWT 认证
- **bcrypt** — 密码加密
- **loguru** — 日志

### 前端
- **React 18** + **Vite**
- **shadcn/ui** (Radix UI) + **Tailwind CSS** — 组件与样式
- **Zustand** — 状态管理
- **Axios** — HTTP 客户端
- **React Router v6** — 路由
- **React Hook Form** + **Zod** — 表单校验
- **lucide-react** — 图标
- **sonner** — 通知提示

### 测试
- **pytest** — 后端测试（183 个测试文件）
- **Vitest** + **Testing Library** — 前端单元测试（58 个测试文件）
- **Playwright** — 前端 E2E 测试（33 个 spec）

## 数据库配置

### 配置步骤

1. **创建配置文件**：
   ```bash
   cp env.template .env
   ```

2. **编辑 `.env` 文件**（关键字段）：
   ```env
   # 数据库类型：sqlite 或 postgresql
   DB_TYPE=postgresql

   # PostgreSQL 配置
   POSTGRES_HOST=localhost
   POSTGRES_PORT=5432
   POSTGRES_DB=logistics
   POSTGRES_USER=postgres
   POSTGRES_PASSWORD=your_password_here
   ```

3. **运行数据库迁移**：
   ```bash
   alembic upgrade head
   ```

完整环境变量说明见 `env.template`。

## 功能特性

### 核心功能
- **用户管理** — 注册、登录、JWT 认证、角色权限控制
- **产品管理** — 产品 CRUD、批量操作
- **物流规则** — 物流方案配置、费用计算
- **智能定价** — 自动定价计算、利润率分析
- **数据统计** — 用户行为分析、收入统计、留存分析
- **订阅管理** — 订阅计划、用户升级、权限管理
- **汇率服务** — 实时汇率查询

### 安全特性
- **JWT 认证** — 无状态令牌认证
- **密码加密** — bcrypt 加密存储
- **会话安全** — 增强会话管理
- **CORS** — 跨域访问控制
- **请求限流** — API 速率限制
- **微信支付** — V3 API 安全验证

### 数据库
- **SQLAlchemy ORM** — 类型安全的数据库操作
- **Alembic 迁移** — 版本化数据库变更
- **连接池** — asyncpg 异步连接池
- **PostgreSQL 备份** — 自动备份与恢复

## 测试

### 运行后端测试
```bash
python -m pytest tests/ --tb=short
```

### 运行前端测试
```bash
cd frontend
npm run test
```

### 运行 E2E 测试
```bash
cd frontend
npm run test:e2e
```

## 项目结构

```
logistics/
├── api/                             # FastAPI 后端
│   ├── main.py                      # FastAPI 应用入口（CORS、限流、异常处理）
│   ├── dependencies.py              # 共享依赖（JWT 认证）
│   ├── middleware/                   # 中间件（限流等）
│   ├── models/                      # API schemas
│   └── routes/                      # API 路由
│       ├── admin.py                 # 管理员用户管理
│       ├── auth.py                  # 登录/注册/改密
│       ├── exchange.py              # 汇率查询
│       ├── logistics.py             # 物流记录 CRUD
│       ├── orders.py                # 订单查询
│       ├── pricing.py               # 定价计算
│       ├── products.py              # 产品 CRUD
│       ├── settings.py              # 系统设置 + 备份管理
│       ├── statistics.py            # 统计报表
│       └── subscriptions.py         # 订阅计划
├── models/                          # SQLAlchemy ORM 模型
│   ├── user.py                      # 用户模型
│   ├── product.py                   # 产品模型
│   ├── logistics.py                 # 物流模型
│   ├── order.py                     # 订单模型
│   ├── session.py                   # 会话模型
│   ├── config.py                    # 配置模型
│   ├── cache.py                     # 缓存模型
│   └── log.py                       # 日志模型
├── db/                              # 数据库操作层（CRUD）
│   ├── users.py                     # 用户操作
│   ├── products.py                  # 产品操作
│   ├── logistics_crud.py            # 物流操作
│   ├── orders.py                    # 订单操作
│   ├── subscriptions.py             # 订阅操作
│   ├── statistics.py                # 统计查询
│   ├── admin.py                     # 管理员操作
│   ├── sessions_crud.py             # 会话操作
│   ├── exchange.py                  # 汇率操作
│   ├── config.py                    # 配置操作
│   └── plans.py                     # 计划操作
├── pricing/                         # 定价计算模块
│   ├── calculate_pricing.py         # 定价主流程
│   ├── final_price.py               # 最终价格计算
│   ├── profit.py                    # 利润计算
│   ├── logistic_cost.py             # 物流成本
│   ├── floating_price.py            # 浮动价格
│   ├── exchange_rate.py             # 汇率转换
│   ├── cost_filter.py               # 成本过滤
│   ├── filter.py                    # 通用过滤
│   └── select_best.py               # 最优方案选择
├── security/                        # 安全模块
│   ├── tokens.py                    # JWT 令牌生成/验证
│   └── utils.py                     # 安全工具函数
├── alembic/                         # 数据库迁移
├── frontend/                        # React 前端
│   ├── src/
│   │   ├── components/              # 共享组件（AppLayout, Sidebar, TopHeader 等）
│   │   ├── pages/                   # 19 个页面
│   │   ├── stores/                  # Zustand 状态管理
│   │   ├── services/                # API 调用层
│   │   ├── lib/                     # 工具库
│   │   ├── styles/                  # 全局样式
│   │   ├── __tests__/               # 前端单元测试
│   │   └── App.jsx                  # 路由入口
│   ├── tests/                       # Playwright E2E 测试
│   ├── vite.config.js
│   └── vitest.config.js
├── tests/                           # 后端 pytest 测试（183 个文件）
├── scripts/                         # 脚本工具
├── database.py                      # 数据库连接与会话管理
├── logic.py                         # 业务逻辑
├── exchange_service.py              # 汇率服务
├── enhanced_exchange_service.py     # 增强汇率服务
├── payment_handler.py               # 支付处理
├── payment_callback_enhanced.py     # 增强支付回调
├── postgres_backup_service.py       # PostgreSQL 备份服务
├── session_security.py              # 会话安全
├── session_security_helpers.py      # 会话安全辅助
├── password_recovery.py             # 密码恢复
├── password_utils.py                # 密码工具
├── security_questions.py            # 安全问题
├── sql_security.py                  # SQL 安全检查
├── logger_config.py                 # 日志配置
├── utils.py                         # 通用工具
├── wechat_pay_config.py             # 微信支付配置
├── wechat_pay_v3_api.py             # 微信支付 V3 API
├── requirements.txt                 # Python 依赖
├── env.template                     # 环境变量模板
├── setup.cfg                        # flake8 配置
├── pytest.ini                       # pytest 配置
├── start_app.bat                    # Windows 启动脚本
├── start_app.ps1                    # PowerShell 启动脚本
└── README.md                        # 本文件
```

## 部署

### 生产环境启动

```bash
# Windows
start_production.bat

# Linux
./start_production_gunicorn.sh
```

### 回滚

```bash
./rollback_production.sh
```

### 数据库备份

备份功能集成在系统设置页面中，也可通过 API 调用：
- `POST /api/settings/backup` — 创建备份
- `GET /api/settings/backups` — 查看备份列表

## 故障排除

### 常见问题

1. **依赖安装失败**
   - 确保已激活虚拟环境：`.venv\Scripts\activate`
   - 重新安装：`pip install -r requirements.txt`

2. **数据库连接错误**
   - 确认 PostgreSQL 服务正在运行
   - 检查 `.env` 中的数据库配置
   - 运行迁移：`alembic upgrade head`

3. **前端启动失败**
   - 确认 Node.js 已安装
   - 重新安装依赖：`cd frontend && npm install`

4. **JWT 认证问题**
   - 检查 `.env` 中的 `SESSION_SECRET` 是否已设置
   - 确认后端服务正在运行

### 日志文件
- 应用日志：`app.log`

## 技术支持

如遇到问题，请检查：
1. 虚拟环境是否正确激活
2. 所有依赖是否正确安装（`pip install -r requirements.txt` + `cd frontend && npm install`）
3. PostgreSQL 是否正在运行
4. `.env` 配置是否正确
5. 数据库迁移是否已执行（`alembic upgrade head`）
6. 日志文件中的错误信息

## 版本信息

- **当前版本**：v4.0.0
- **Python 版本**：3.10+
- **Node.js 版本**：18+
- **最后更新**：2026-04
- **主要更新**：
  - 前端全站视觉统一 — 移除 Ant Design，迁移至 shadcn/ui + Tailwind CSS
  - 后端从 Streamlit 迁移至 FastAPI REST API
  - 数据库层从原始 SQL (db_utils) 迁移至 SQLAlchemy ORM + Alembic
  - 定价逻辑重构为独立 `pricing/` 模块
  - 新增 JWT 无状态认证
  - 前端状态管理迁移至 Zustand
  - 新增 Playwright E2E 测试
