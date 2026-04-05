# 🔍 物流定价系统 — 全面审计报告

> 审计日期：2026-04-04
> 审计范围：安全漏洞、数据库泄漏、代码质量、前端问题、API设计缺陷
> 共发现 **42 个问题**：CRITICAL(6) / HIGH(12) / MEDIUM(14) / LOW(10)

---

## 🔴 CRITICAL — 致命（6个）

### C1. 认证绕过：JWT 失败后回退到用户名认证

| 项目 | 内容 |
|------|------|
| **文件** | `api/dependencies.py:14-26, 90-107` |
| **类别** | 安全漏洞 |

**问题代码：**
```python
def get_current_user_id(api_key=Depends(security)) -> int:
    token = api_key.credentials
    try:
        user_id = get_user_id_from_token(token)
    except (TokenExpiredError, TokenInvalidError):
        pass  # ← 静默吞没！
    # JWT失败后，把原始token当用户名查数据库
    with get_db_connection() as (conn, c):
        sql = _safe_adapt_sql("SELECT id FROM users WHERE username = %s", conn)
        c.execute(sql, (token,))
        row = c.fetchone()
        if row:
            return row[0]  # ← 攻击者发送 Bearer admin 即可登录
```

**影响：** 发送 `Authorization: Bearer admin` 即可以管理员身份登录，完全绕过JWT验证。所有受保护端点（包括 `require_admin`）均可被绕过。

**修复：** 移除 token-as-username 回退逻辑。JWT解码失败 → 直接 `raise HTTPException(401)`。

---

### C2. 硬编码管理员默认密码

| 项目 | 内容 |
|------|------|
| **文件** | `db_utils.py:~1196-1200` |
| **类别** | 安全漏洞 |

**问题代码：**
```python
hashed_password = hash_password("admin123")
```

**影响：** `init_db()` 初始化时创建管理员账户使用硬编码密码 `"admin123"`。部署后如不更改，攻击者可直接登录。

**修复：** 通过环境变量提供初始密码，或生成随机密码一次性输出到安全日志。禁止代码中包含任何默认密码。

---

### C3. 货币转换逻辑不一致（影响报价金额）

| 项目 | 内容 |
|------|------|
| **文件** | `api/routes/pricing.py:83-86, 109-114, 186-189` |
| **类别** | 逻辑 Bug |

**问题代码：**
```python
# 第83行：RUB→CNY 用乘法
agency_cny = round(commission_rub * rate, 2) if commission_rub else 0

# 第109行：固定10 RUB→CNY 也用乘法
payment_cny = round(10 * rate, 2)

# 第186行：CNY→RUB 用除法（如果 rate = RUB/CNY，这里应该用乘法）
price_rub = round(price / rate, 2) if rate else 0
```

**影响：** `rate` 的语义不统一（有时是 RUB/CNY，有时当 CNY/RUB 用），导致**报价计算错误，可能造成财务损失**。

**修复：** 统一定义 `rate` 语义（如始终表示 RUB_PER_CNY），所有转换使用一致方向。添加货币转换单元测试。

---

### C4. 安全模块静默异常吞没

| 项目 | 内容 |
|------|------|
| **文件** | `session_security.py:252, 277, 325, 369, 416, 448, 465, 481, 510, 557` 等（10+处） |
| **类别** | 安全漏洞 |

**问题代码：**
```python
# 数据库安全表创建
try:
    cursor.execute("CREATE TABLE IF NOT EXISTS ...")
except Exception:
    pass  # ← 表创建失败也不报错！
```

**影响：** 安全表创建失败时无报错，安全功能（会话管理、并发检测等）静默失效，系统以为一切正常。

**修复：** 替换为具体异常类型 + `logger.exception()`。关键表创建失败应阻止启动。

---

### C5. 前端无 ErrorBoundary

| 项目 | 内容 |
|------|------|
| **文件** | 整个 `frontend/src/` — 全局搜索无结果 |
| **类别** | 前端 |

**影响：** 任何 React 组件渲染异常 → 整个应用白屏崩溃，无降级界面，用户体验毁灭性打击。

**修复：** 创建 `ErrorBoundary` 组件（class component + `componentDidCatch`），包裹 `<Routes>`，提供友好的错误界面和重试按钮。

---

### C6. XSS 漏洞：Markdown 未消毒直接注入

| 项目 | 内容 |
|------|------|
| **文件** | `frontend/src/pages/RegisterPage.jsx:285-288` |
| **类别** | 安全漏洞 |

**问题代码：**
```jsx
<div dangerouslySetInnerHTML={{ __html: marked.parse(eulaContent) }} />
```

**影响：** Markdown 渲染结果未经消毒直接注入 DOM。若 EULA 内容含恶意脚本（`<script>` 或事件属性），即可执行 XSS 攻击。

**修复：**
```jsx
import DOMPurify from 'dompurify';
<div dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(marked.parse(eulaContent)) }} />
```

---

## 🟠 HIGH — 高危（12个）

### H1. SQL 注入：动态列名未白名单校验

| 项目 | 内容 |
|------|------|
| **文件** | `api/routes/logistics.py:143-151`, `api/routes/admin.py:133-139` |
| **类别** | 安全漏洞 |

**问题代码：**
```python
update_data = logistics.model_dump(exclude_unset=True)
set_clause = ", ".join([f"{k} = %s" for k in update_data.keys()])
sql_raw = f"UPDATE logistics SET {set_clause} WHERE id = %s AND user_id = %s"
```

**影响：** 虽然值用了参数化占位符，但列名（`k`）直接从用户输入的 JSON key 拼入 SQL。攻击者可构造恶意 key 注入 SQL 片段。

**修复：** 使用项目已有的 `sql_security.build_update_set_clause()` 或白名单验证列名：
```python
allowed = {"name", "min_days", "max_days", ...}
sanitized = {k: v for k, v in update_data.items() if k in allowed}
```

---

### H2. CORS 配置过度宽松

| 项目 | 内容 |
|------|------|
| **文件** | `api/main.py:50-56` |
| **类别** | 安全漏洞 |

**问题代码：**
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**影响：** `allow_origins=["*"]` + `allow_credentials=True` 违反 CORS 安全规范，允许任何域携带凭证发起跨域请求。

**修复：** 从环境变量读取允许的 origin 列表：
```python
origins = os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(CORSMiddleware, allow_origins=origins, ...)
```

---

### H3. 备份下载目录穿越风险

| 项目 | 内容 |
|------|------|
| **文件** | `api/routes/settings.py:299-322` |
| **类别** | 安全漏洞 |

**问题代码：**
```python
if not filename.endswith(".dump"):
    raise HTTPException(...)
data = read_backup_file(filename)  # 仅检查后缀，未防路径穿越
```

**影响：** 攻击者可构造 `../../etc/passwd.dump` 之类的文件名穿越目录读取任意文件。

**修复：**
```python
import os
safe_name = os.path.basename(filename)
available = {f["name"] for f in list_backup_files()}
if safe_name not in available:
    raise HTTPException(404)
data = read_backup_file(safe_name)
```

---

### H4. JWT 密钥硬编码回退

| 项目 | 内容 |
|------|------|
| **文件** | `security/tokens.py:7` |
| **类别** | 安全漏洞 |

**问题代码：**
```python
SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "fallback-dev-key-change-in-production")
```

**影响：** 生产环境未设置 `JWT_SECRET_KEY` 时使用已知默认密钥，所有 JWT 可被伪造。

**修复：**
```python
SECRET_KEY = os.environ.get("JWT_SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("JWT_SECRET_KEY environment variable is required")
```

---

### H5. 全局异常处理器吞没 HTTPException 状态码

| 项目 | 内容 |
|------|------|
| **文件** | `api/main.py:83-88` |
| **类别** | API 设计 |

**问题代码：**
```python
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc) if os.getenv("DEBUG") else "Internal server error"},
    )
```

**影响：** 捕获所有异常包括 `HTTPException`，4xx 错误也返回 500。DEBUG 模式泄露异常详情。

**修复：**
```python
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    if isinstance(exc, HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    logger.exception("Unhandled exception")
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
```

---

### H6. 管理员密码重置返回明文弱密码

| 项目 | 内容 |
|------|------|
| **文件** | `api/routes/admin.py:158-172` |
| **类别** | 安全漏洞 |

**问题代码：**
```python
default_password = "123456"
password_hash = bcrypt.hashpw(default_password.encode(), bcrypt.gensalt()).decode()
# ...
return MessageResponse(message=f"密码已重置为: {default_password}")
```

**影响：** 使用极弱默认密码 "123456"，且在 API 响应中返回明文密码（可被日志/中间件记录）。

**修复：** 生成随机强密码（`secrets.token_urlsafe(16)`），不在 API 响应中返回明文，通过安全渠道通知用户。

---

### H7. async 端点内同步阻塞 DB 调用

| 项目 | 内容 |
|------|------|
| **文件** | 所有 `api/routes/*.py`（10+ 个文件） |
| **类别** | 性能 |

**问题模式：**
```python
@router.post("/calculate")
async def calculate(request: PricingRequest, ...):
    with get_db_connection() as (conn, c):  # ← 同步阻塞！
        c.execute(sql, params)
```

**影响：** `async def` 端点内直接调用同步 DB 操作，会阻塞 asyncio 事件循环。并发请求时导致性能急剧下降甚至超时。

**修复方案（二选一）：**
- 将 `async def` 改为 `def`（FastAPI 自动在线程池中运行同步函数）
- 或用 `await run_in_threadpool(sync_db_call)` 包装

---

### H8. `await` 缺失导致 404 检查失效

| 项目 | 内容 |
|------|------|
| **文件** | `api/routes/logistics.py:129-137` |
| **类别** | 逻辑 Bug |

**问题代码：**
```python
async def update_logistics_endpoint(...):
    existing = get_logistics_by_id(logistics_id, user_id)  # ← 缺 await！
    if not existing:  # 协程对象永远为真，404 检查永远不生效
        raise HTTPException(status_code=404)
```

**影响：** `existing` 是协程对象（永远为真），对不存在的记录执行更新不会返回 404。

**修复：** `existing = await get_logistics_by_id(logistics_id, user_id)`

---

### H9. 281 个 bare except 吞没异常

| 项目 | 内容 |
|------|------|
| **分布** | `db_utils.py`(95), `postgres_backup_service.py`(29), `enhanced_exchange_service.py`(27), 另 24 个文件 |
| **类别** | 代码质量 |

**问题模式：**
```python
try:
    # 关键操作
except Exception:
    pass  # ← 所有异常被静默吞没
```

**影响：** 隐藏 bug、安全问题和运行时错误。特别是在 DB、安全和支付模块中，错误被吞没可能导致数据不一致或安全功能失效。

**修复：** 逐步替换：优先处理安全/支付/DB 模块，改为具体异常类型 + `logger.exception()`。

---

### H10. `check_concurrent_sessions` 异常时错误返回 True

| 项目 | 内容 |
|------|------|
| **文件** | `session_security.py:424-449` |
| **类别** | 安全漏洞 |

**问题代码：**
```python
except Exception:
    return True, ""  # ← 异常时返回"达并发限制"
```

**影响：** 数据库异常时误判为"达到并发限制"，**强制正常用户登出**。

**修复：** 异常时 `logger.exception()` + 返回安全默认值 `(False, "")`（允许访问）。

---

### H11. conftest.py 硬编码数据库密码

| 项目 | 内容 |
|------|------|
| **文件** | `conftest.py:220-223` |
| **类别** | 安全漏洞 |

**问题代码：**
```python
password=os.environ.get("POSTGRES_PASSWORD", "***REMOVED-PG-PWD***")
```

**影响：** 数据库密码明文存储在代码仓库中。

**修复：** 移除默认密码，仅从环境变量读取。CI/CD 通过 secrets 注入。

---

### H12. db_utils.py f-string 直接拼接 SQL 标识符

| 项目 | 内容 |
|------|------|
| **文件** | `db_utils.py:143-154` |
| **类别** | 安全漏洞 |

**问题代码：**
```python
cursor.execute(f"CREATE SEQUENCE IF NOT EXISTS {seq_name}")
cursor.execute(f"ALTER TABLE {table} ALTER COLUMN id SET DEFAULT nextval('{seq_name}'::regclass)")
cursor.execute(f"ALTER SEQUENCE {seq_name} OWNED BY {table}.id")
```

**影响：** 标识符通过 f-string 拼入 SQL，虽然当前来源为内部 `information_schema`，但模式脆弱，后续改动可能引入注入风险。

**修复：** 使用 `psycopg2.sql` 模块安全拼接标识符，或 `sql_security.validate_table_name()` 校验。

---

## 🟡 MEDIUM — 中等（14个）

### M1. `db_utils.py` 约 4250 行（超出 500 行限制 8.5 倍）

| 项目 | 内容 |
|------|------|
| **文件** | `db_utils.py` |
| **类别** | 代码质量 |

**影响：** 严重违反项目规范（Python 文件 < 500 行）。难以维护、审查和测试。

**修复：** 拆分为功能模块：`db_conn.py`（连接管理）, `db_migrations.py`（表创建/迁移）, `db_queries.py`（通用查询）, `db_users.py`（用户操作）, `db_products.py`（产品操作）等。

---

### M2. `logic.py` 约 1846 行 + 超长函数

| 项目 | 内容 |
|------|------|
| **文件** | `logic.py:17-361`（`calculate_logistic_cost` ~344 行）, `calculate_pricing` 同样超长 |
| **类别** | 代码质量 |

**影响：** 违反函数 < 100 行规范。逻辑复杂难以追踪，bug 难以定位。

**修复：** 拆分为小型辅助函数：`_calc_base_fee()`, `_calc_continue_fee()`, `_calc_insurance()`, `_apply_discounts()` 等。

---

### M3. 函数返回类型不一致

| 项目 | 内容 |
|------|------|
| **文件** | `logic.py:17-65` |
| **类别** | 代码质量 |

**问题：** `debug=True` 返回元组 `(cost, debug_info)`，`debug=False` 返回标量 `cost`。调用方必须处理两种类型。

**修复：** 统一返回 dict `{"cost": value, "debug": [...]}`，或始终返回 `(cost, debug_info)` 其中 debug_info 可为 None。

---

### M4. 费率转换启发式歧义

| 项目 | 内容 |
|------|------|
| **文件** | `api/routes/pricing.py:88-96` |
| **类别** | 逻辑 Bug |

**问题：** `to_rate()` 用 `>=1` 启发式判断百分数（8 → 0.08），但 0.08 和 8% 容易混淆。

**修复：** API 边界强制标准化，所有费率为 `[0,1]` 浮点数，在 Pydantic 模型中校验。

---

### M5. `_is_postgresql_connection` 默认返回 True

| 项目 | 内容 |
|------|------|
| **文件** | `db_utils.py:88-111` |
| **类别** | 代码质量 |

**问题：** 检测逻辑失败时默认假设 PostgreSQL，可能对 mock/其他 DB 执行 PG 专用 SQL。

**修复：** 默认返回 False，或用显式配置标志 `DB_TYPE=postgresql`。

---

### M6. 内存速率限制器

| 项目 | 内容 |
|------|------|
| **文件** | `api/middleware/rate_limit.py` |
| **类别** | 安全 / 性能 |

**问题：**
- 单进程内存存储，多 worker 部署无效
- 不处理 `X-Forwarded-For`（反向代理后所有请求同一 IP）
- key 无上限，可被大量 IP 耗内存

**修复：** 替换为 Redis 速率限制器或 API 网关级限流。

---

### M7. SSE 进度端点无认证

| 项目 | 内容 |
|------|------|
| **文件** | `api/routes/pricing.py` `/progress` 端点 |
| **类别** | 安全漏洞 |

**问题：** `/progress` 端点无 `Depends(get_current_user_id)`，任何人可连接 SSE 流。

**修复：** 添加认证依赖。

---

### M8. 多个列表端点无分页

| 项目 | 内容 |
|------|------|
| **文件** | `products.py`, `logistics.py`, `orders.py`, `admin.py` |
| **类别** | API 设计 |

**问题：** `get_products`, `get_logistics`, `get_orders` 等返回全量列表，无 `limit/offset`。

**修复：** 添加 `limit` + `offset` 查询参数，设合理默认值和上限。

---

### M9. 会话 HMAC 密钥开发回退

| 项目 | 内容 |
|------|------|
| **文件** | `session_security.py:527-541` |
| **类别** | 安全漏洞 |

**问题：** 非生产模式使用 `"default-dev-secret-key-change-in-production"`。

**修复：** 所有环境都强制要求环境变量，移除默认值。

---

### M10. API 错误格式不一致

| 项目 | 内容 |
|------|------|
| **文件** | `settings.py`, `subscriptions.py` 等多个路由文件 |
| **类别** | API 设计 |

**问题：** 部分用 `JSONResponse({"message": ...})`，部分用 `HTTPException(detail=...)`，客户端处理困难。

**修复：** 统一使用 `HTTPException(status_code=xxx, detail=...)`。

---

### M11. LogisticsPage loading 状态丢失（前端 UX bug）

| 项目 | 内容 |
|------|------|
| **文件** | `frontend/src/pages/LogisticsPage.jsx:134` |
| **类别** | 前端 |

**问题代码：**
```javascript
const [, setLoading] = useState(false)  // ← loading 值被丢弃！
```

**影响：** 用户看不到加载状态，UI 无反馈。

**修复：** `const [loading, setLoading] = useState(false)` + 渲染加载指示器。

---

### M12. 前端多处静默吞没 API 错误

| 项目 | 内容 |
|------|------|
| **文件** | `PricingPage.jsx:250-252` 等多处 |
| **类别** | 前端 |

**问题代码：**
```javascript
productsAPI.getAll().then(data => ...).catch(() => {})  // ← 错误被吞没
```

**修复：** `.catch(e => { toast.error('加载失败'); console.error(e) })`

---

### M13. 前端 toast 直接暴露服务端错误详情

| 项目 | 内容 |
|------|------|
| **文件** | `UserManagementPage.jsx`, `RegisterPage.jsx`, `LogisticsPage.jsx` 等 |
| **类别** | 安全 / UX |

**问题代码：**
```javascript
toast.error(error.response?.data?.detail || '操作失败')
```

**影响：** 服务端异常详情（可能含堆栈、SQL 错误）直接展示给用户。

**修复：** 在 `api.js` 拦截器统一规范化错误消息，仅展示安全的用户友好提示。

---

### M14. `_cleanup_duplicate_rows` 游标未关闭

| 项目 | 内容 |
|------|------|
| **文件** | `db_utils.py:~4034` |
| **类别** | 数据库泄漏 |

**问题代码：**
```python
cursor = conn.cursor()  # 创建新游标
cursor.execute(...)
conn.commit()
# ← 缺少 cursor.close()！db_adapter 只关闭它自己创建的游标
```

**修复：** 在 `finally` 中 `cursor.close()`，或复用调用者传入的游标。

---

## 🔵 LOW — 低（10个）

### L1. 占位 `pass` 代码
- **文件**: `security/tokens.py:~15,21,27`, `api/models/schemas.py:62,143`, `security/utils.py:24`
- **问题**: 空函数体或未实现的占位代码

### L2. DashboardPage useEffect 无取消机制
- **文件**: `frontend/src/pages/DashboardPage.jsx:13-31`
- **问题**: 异步请求无 AbortController，组件卸载后可能 setState

### L3. SideMenu/Sidebar setInterval fetch 无 AbortController
- **文件**: `frontend/src/components/SideMenu.jsx:31-48`
- **问题**: 每 5 分钟 fetch 汇率，有 clearInterval 但无 abort 进行中的请求

### L4. TooltipIcon timeout 组件卸载后未清除
- **文件**: `frontend/src/pages/LogisticsPage.jsx:80-106`
- **问题**: setTimeout 在组件卸载后可能触发 setState
- **修复**: 添加 `useEffect(() => () => clearTimeout(ref.current), [])`

### L5. 多处 `.map` 使用 index 作为 key
- **文件**: `DashboardPage.jsx:71`, `PricingPage.jsx:711`, `CostPieChart.jsx:55` 等
- **问题**: 列表变动时可能导致 React 渲染不正确

### L6. 多处 `console.error` 遗留在生产代码中
- **文件**: `SettingsPage.jsx:63,80,92`, `DashboardPage.jsx:26`, `SideMenu.jsx:38`
- **修复**: 替换为集中式日志或按 NODE_ENV 条件输出

### L7. apiClient 无超时配置
- **文件**: `frontend/src/services/api.js`
- **问题**: axios 默认无超时，请求可能永久挂起
- **修复**: `axios.create({ timeout: 15000 })`

### L8. CostPieChart total=0 时返回 null
- **文件**: `frontend/src/components/charts/CostPieChart.jsx:20-21`
- **问题**: 无空状态 UI，布局可能跳动
- **修复**: 显示"无数据"占位

### L9. SettingsPage 硬编码备份路径
- **文件**: `frontend/src/pages/SettingsPage.jsx:537-538`
- **问题**: UI 显示硬编码的本地路径字符串

### L10. 疑似未使用依赖
- **文件**: `frontend/package.json`
- `framer-motion`, `recharts` 在代码中未找到 import
- **修复**: 运行 `npx depcheck` 确认后移除

---

## 📊 统计汇总

| 严重度 | 数量 | 安全 | 代码质量 | 前端 | DB/性能 | API 设计 |
|--------|------|------|---------|------|---------|---------|
| CRITICAL | 6 | 3 | 1 | 2 | 0 | 0 |
| HIGH | 12 | 6 | 2 | 0 | 1 | 3 |
| MEDIUM | 14 | 2 | 3 | 3 | 1 | 5 |
| LOW | 10 | 0 | 1 | 8 | 0 | 1 |
| **合计** | **42** | **11** | **7** | **13** | **2** | **9** |

---

## 🎯 修复优先级建议

### P0 — 立即修复（本周内）
1. **C1** — 移除认证回退（安全紧急，可被远程利用）
2. **C2** — 移除硬编码管理员密码
3. **C3** — 修复货币转换逻辑（财务影响）
4. **H1** — SQL 标识符注入防护
5. **H3** — 备份下载目录穿越防护
6. **H4** — JWT 密钥强制环境变量

### P1 — 短期修复（两周内）
7. **C4, H9** — 清理 bare except（安全+会话模块优先）
8. **H2** — CORS 收紧
9. **H5** — 全局异常处理器修复
10. **H6** — 密码重置安全化
11. **C5** — 添加 ErrorBoundary
12. **C6** — XSS 消毒
13. **H8** — await 缺失修复
14. **H10** — 并发会话检查修复

### P2 — 中期修复（一个月内）
15. **M1, M2** — 大文件/长函数拆分
16. **H7** — async/sync 端点统一
17. **M6** — 速率限制器升级
18. **M8** — 列表分页
19. **M10** — API 错误格式统一
20. **M11-M13** — 前端 UX 改进

### P3 — 长期改进
21. **L1-L10** — 代码清理、前端小修
22. **M3-M5** — 返回类型/检测逻辑优化
23. **H11, H12** — 密码/SQL 标识符加固

---

## 📁 涉及文件清单

### 后端（需修改）
```
api/dependencies.py         — C1: 移除认证回退
api/main.py                 — H2: CORS, H5: 异常处理器
api/routes/admin.py         — H1: SQL 注入, H6: 密码重置
api/routes/logistics.py     — H1: SQL 注入, H8: await
api/routes/pricing.py       — C3: 货币转换, M4: 费率, M7: SSE 认证
api/routes/settings.py      — H3: 目录穿越
api/middleware/rate_limit.py — M6: 速率限制器
security/tokens.py          — H4: JWT 密钥
session_security.py         — C4: 异常吞没, H10: 并发检查, M9: HMAC 密钥
db_utils.py                 — C2: 默认密码, H9/H12: 异常/SQL, M1: 拆分, M14: 游标
logic.py                    — M2: 拆分, M3: 返回类型
conftest.py                 — H11: 硬编码密码
```

### 前端（需修改）
```
frontend/src/pages/RegisterPage.jsx         — C6: XSS
frontend/src/pages/LogisticsPage.jsx        — M11: loading, L4: timeout
frontend/src/pages/PricingPage.jsx          — M12: 错误吞没, L5: key
frontend/src/pages/DashboardPage.jsx        — L2: useEffect, L5: key, L6: console
frontend/src/pages/SettingsPage.jsx         — L6: console, L9: 硬编码路径
frontend/src/pages/UserManagementPage.jsx   — M13: 错误暴露
frontend/src/services/api.js                — L7: timeout, M13: 错误规范化
frontend/src/components/SideMenu.jsx        — L3: AbortController, L6: console
frontend/src/components/charts/CostPieChart.jsx — L8: 空状态
frontend/src/App.jsx                        — C5: ErrorBoundary
```
