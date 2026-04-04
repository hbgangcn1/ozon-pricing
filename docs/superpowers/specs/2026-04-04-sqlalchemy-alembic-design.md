# SQLAlchemy ORM + Alembic 全量重构设计规格

**日期**: 2026-04-04
**方案**: 方案 B — 直接替换，保持扁平 db/ 结构
**范围**: 40-50 文件，~4500 行代码改写/删除

---

## 1. 目标

将整个数据库层从 raw SQL + psycopg2 替换为 SQLAlchemy ORM + Alembic 迁移 + asyncpg 异步驱动。

**核心诉求**:
- 所有路由转为 `async def`，使用 `AsyncSession` 依赖注入
- 所有 raw SQL 替换为 ORM 查询
- Alembic 管理 schema 迁移，应用启动时自动执行 `upgrade head`
- 一次性替换，不保留兼容层

---

## 2. 目录结构

```
logistics/
├── models/                    # 新增：SQLAlchemy ORM 模型
│   ├── __init__.py            # Base + 导出所有模型
│   ├── user.py                # User, Plan, SubscriptionUpgradeHistory
│   ├── product.py             # Product
│   ├── logistics.py           # Logistics
│   ├── order.py               # PaymentOrder
│   ├── config.py              # SystemConfig, ExchangeRate
│   ├── session.py             # ActiveSession, LoginAttempt, UserLockout, TrustedDevice
│   ├── log.py                 # UserLoginLog, UserBehaviorLog, AdminActionLog, AlertRecord, AlertConfig, PasswordRecoveryLog
│   └── cache.py               # StatisticsCache
│
├── database.py                # 新增：async engine + AsyncSessionLocal + get_db 依赖
├── alembic.ini                # 新增：Alembic 配置
├── alembic/                   # 新增：Alembic 迁移目录
│   ├── env.py                 # async 迁移运行，导入 Base.metadata
│   ├── script.py.mako         # 迁移模板
│   └── versions/
│       └── 001_initial_schema.py
│
├── db/                        # 保留结构，内部全部改写
│   ├── __init__.py            # 导出不变，函数签名加 session 参数
│   ├── users.py               # raw SQL → ORM (async)
│   ├── products.py            # raw SQL → ORM (async)
│   ├── admin.py               # raw SQL → ORM (async)
│   ├── admin_helpers.py       # raw SQL → ORM (async)
│   ├── logging_utils.py       # raw SQL → ORM (async)
│   ├── statistics.py          # raw SQL → ORM (async)
│   ├── subscriptions.py       # raw SQL → ORM (async)
│   ├── plans.py               # raw SQL → ORM (async)
│   ├── config.py              # raw SQL → ORM (async)
│   ├── exchange.py            # raw SQL → ORM (async)
│   ├── password.py            # 不改（纯 bcrypt）
│   ├── session.py             # 不改（纯内存状态）
│   ├── connection.py          # 删除
│   ├── helpers.py             # 删除
│   ├── _proxy.py              # 删除
│   └── schema.py              # 删除
│
├── db_adapter.py              # 删除
├── db_utils.py                # 删除
└── db_config.py               # 保留（database.py 复用其 get_database_url()）
```

---

## 3. database.py — 异步引擎与会话管理

```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from collections.abc import AsyncGenerator
from db_config import get_database_url

engine = create_async_engine(
    get_database_url().replace("postgresql://", "postgresql+asyncpg://"),
    pool_size=20,
    max_overflow=10,
    pool_recycle=3600,
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

**决策**:

| 项目 | 决策 | 理由 |
|------|------|------|
| 驱动 | asyncpg | 异步 PostgreSQL 唯一生产级选择 |
| 连接池 | SQLAlchemy 内置 (pool_size=20) | 替代 db_adapter.py 手写连接池 |
| session 生命周期 | 请求级，get_db 依赖注入 | 替代 `with get_db_connection() as (conn, c):` |
| commit 策略 | get_db 自动 commit/rollback | 路由函数无需手动 commit |
| expire_on_commit | False | commit 后仍可读属性 |

---

## 4. ORM 模型定义

使用 SQLAlchemy 2.0 语法：`Mapped[]` + `mapped_column()`。

### Base

```python
# models/__init__.py
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass
```

### 模型清单（19 个模型，8 个文件）

| 文件 | 模型 | 表名 | 列数 |
|------|------|------|------|
| user.py | User | users | 13 |
| user.py | Plan | plans | 8 |
| user.py | SubscriptionUpgradeHistory | subscription_upgrade_history | 6 |
| product.py | Product | products | 12 |
| logistics.py | Logistics | logistics | 约 20（含计费参数、限制条件等） |
| order.py | PaymentOrder | payment_orders | 10 |
| config.py | SystemConfig | system_config | 3 |
| config.py | ExchangeRate | exchange_rates | 4 |
| session.py | ActiveSession | active_sessions | 6 |
| session.py | LoginAttempt | login_attempts | 5 |
| session.py | UserLockout | user_lockouts | 4 |
| session.py | TrustedDevice | trusted_devices | 5 |
| log.py | UserLoginLog | user_login_log | 5 |
| log.py | UserBehaviorLog | user_behavior_log | 5 |
| log.py | AdminActionLog | admin_action_log | 6 |
| log.py | AlertRecord | alert_records | 6 |
| log.py | AlertConfig | alert_config | 4 |
| log.py | PasswordRecoveryLog | password_recovery_log | 5 |
| cache.py | StatisticsCache | statistics_cache | 5 |

### 模型定义决策

| 项目 | 决策 | 理由 |
|------|------|------|
| 时间戳字段类型 | `Mapped[Optional[str]]` | 生产数据存文本，不改列类型 |
| is_frozen / is_auto_renew | `Mapped[int]` | 生产数据存 INTEGER 0/1 |
| relationship | 不定义 | 当前无 JOIN 查询模式，后续按需添加 |
| `__tablename__` | 与生产库一致 | Alembic autogenerate 不产生 diff |
| 列定义来源 | 从生产库 information_schema 读取 | 确保与实际 schema 100% 一致 |

### User 模型示例

```python
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="user")
    preferred_mode: Mapped[Optional[str]] = mapped_column(String(20))
    subscription_type: Mapped[str] = mapped_column(String(20), default="free")
    subscription_expires: Mapped[Optional[str]] = mapped_column(String(50))
    daily_calculations_remaining: Mapped[int] = mapped_column(default=5)
    total_calculations: Mapped[int] = mapped_column(default=0)
    is_auto_renew: Mapped[int] = mapped_column(default=0)
    is_frozen: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[Optional[str]] = mapped_column(String(50))
    last_login: Mapped[Optional[str]] = mapped_column(String(50))
```

---

## 5. db/ 包改写策略

### 函数签名变化

所有 db/ 函数：
1. 变为 `async def`
2. 第一个参数加 `session: AsyncSession`
3. 内部从 raw SQL 改为 ORM 操作
4. 不调用 `session.commit()`（由 get_db 统一管理）
5. 需要拿自增 id 时用 `session.flush()`

```python
# 改造前
def create_user(username, password, role="user"):
    with get_db_connection() as (conn, c):
        c.execute(adapt_sql(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)"
        ), (username, hashed, role))
        conn.commit()
        return c.lastrowid

# 改造后
async def create_user(session: AsyncSession, username: str, password: str, role: str = "user") -> int:
    user = User(username=username, password=hash_password(password), role=role)
    session.add(user)
    await session.flush()
    return user.id
```

### 各模块改写清单

| 模块 | 函数数 | 难度 | 说明 |
|------|--------|------|------|
| db/users.py | ~12 | 中 | verify_user 需 select().where()，密码验证逻辑保留 |
| db/products.py | ~8 | 低 | 标准 CRUD，batch_update 用循环 ORM |
| db/admin.py | ~10 | 中 | get_all_users 有动态排序/筛选 |
| db/admin_helpers.py | ~5 | 中 | 查询构建器改为 ORM 动态构建 |
| db/logging_utils.py | ~6 | 低 | 纯 INSERT |
| db/statistics.py | ~5 | 高 | 复杂聚合用 func.count()/func.sum() |
| db/subscriptions.py | ~5 | 中 | 日期比较逻辑保留 |
| db/plans.py | ~6 | 低 | 标准 CRUD |
| db/config.py | ~3 | 低 | key-value 表 |
| db/exchange.py | ~2 | 低 | 单表读写 |
| db/password.py | 4 | 不改 | 纯 bcrypt |
| db/session.py | 3 | 不改 | 纯内存状态 |

### db/__init__.py

保持所有导出名不变。删除的导出：
- `get_db_connection`, `get_db`, `DBConnection`
- `adapt_sql`, `get_placeholder`
- `_connection_counter` 等连接池相关
- `_is_postgresql_connection`, `_ensure_serial_columns` 等适配层函数

### commit 策略

| 操作 | 方式 | 说明 |
|------|------|------|
| INSERT 需要 id | `session.flush()` | 写入 DB 拿 id，不 commit |
| 普通读 | `await session.execute(select(...))` | 无需 flush/commit |
| 事务边界 | get_db 自动 commit/rollback | db/ 函数内部不 commit |
| 批量操作 | `session.add_all()` + `flush()` | 如 batch_update |

---

## 6. Alembic 配置与初始迁移

### 文件结构

```
alembic.ini          # sqlalchemy.url 从 db_config 读取
alembic/
├── env.py           # async 迁移，导入 Base.metadata
├── script.py.mako
└── versions/
    └── 001_initial_schema.py
```

### env.py 关键配置

```python
from models import Base
from database import engine

target_metadata = Base.metadata

async def run_async_migrations():
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)

def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()
```

### 初始迁移策略：stamp baseline

生产库已有数据，不能 CREATE TABLE。

```bash
# 生成初始迁移文件
alembic revision --autogenerate -m "initial schema"
# 不执行迁移，标记生产库已在此版本
alembic stamp head
```

### 启动时自动迁移

```python
# database.py
def run_migrations():
    """同步函数：Alembic CLI 本身是同步的，无需 async。"""
    from alembic.config import Config
    from alembic import command
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")

# api/main.py — 在 startup 事件中调用
@app.on_event("startup")
async def startup():
    run_migrations()  # 同步调用，阻塞启动直到迁移完成（符合预期）
```

注意：Alembic 的 `command.upgrade()` 是同步 API，内部自己管理数据库连接（不复用应用的 async engine）。这是 Alembic 的标准用法。

### init_db() 的处理

现有 `db/schema.py` 的 `init_db()` 在启动时执行 `CREATE TABLE IF NOT EXISTS`。改造后：
- `init_db()` 调用删除，由 `run_migrations()` 替代
- `api/main.py` 的 startup 事件中只调用 `run_migrations()`
- 所有 schema 变更通过 Alembic 迁移管理

### alembic.ini URL

不硬编码，env.py 中从 db_config 读取：

```python
# env.py
from db_config import get_database_url
config.set_main_option(
    "sqlalchemy.url",
    get_database_url().replace("postgresql://", "postgresql+asyncpg://"),
)
```

### 日常开发工作流

```bash
# 改了 models/ 后：
alembic revision --autogenerate -m "add xxx column"
# 检查迁移文件 → 重启应用（startup 自动 upgrade head）
```

---

## 7. 路由层改造

### 统一模式

```python
# 改造前
@router.post("/xxx")
def some_endpoint(user_id: int = Depends(get_current_user_id)):
    with get_db_connection() as (conn, c):
        c.execute(adapt_sql("SELECT ..."), (user_id,))
        rows = c.fetchall()
    return {"data": rows}

# 改造后
@router.post("/xxx")
async def some_endpoint(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await some_function(db, user_id)
    return {"data": result}
```

**规则**: 路由函数内不出现任何 SQL、不出现 session.execute()。所有数据操作通过 db/ 函数。

### api/dependencies.py

```python
# 改造后
async def get_current_user_id(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> int:
    payload = decode_token(token)
    user_id = payload.get("user_id")
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user_id
```

### 各路由文件改造

| 路由文件 | 改造内容 |
|----------|----------|
| auth.py | 全改为 db 函数调用 |
| admin.py | 新增 db/admin.py 函数封装 raw SQL |
| statistics.py | 新增 db/statistics.py 函数封装聚合查询 |
| logistics.py | 新增 db/ 对应函数 |
| orders.py | 新增 db/ 对应函数 |
| pricing.py | raw SQL 部分提取到 db/ |
| products.py | 改动最小，加 async + session 传参 |
| settings.py | SQL 部分提取到 db/config.py |
| subscriptions.py | 提取到 db/subscriptions.py |
| exchange.py | 几乎不改（无直接 DB） |

### 根模块（非 FastAPI 请求上下文）

`payment_handler.py`, `session_security.py`, `session_security_helpers.py`, `session_security_enhanced.py` 不在请求上下文中，手动创建 session：

```python
from database import AsyncSessionLocal

async def some_security_function():
    async with AsyncSessionLocal() as session:
        try:
            result = await db_function(session, ...)
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

---

## 8. 测试改造

### 测试 session 机制

```python
# conftest.py
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from httpx import AsyncClient
from models import Base
from database import get_db

test_engine = create_async_engine(TEST_DATABASE_URL)
TestSessionLocal = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

@pytest_asyncio.fixture
async def db_session():
    async with test_engine.connect() as conn:
        trans = await conn.begin()
        session = TestSessionLocal(bind=conn)
        try:
            yield session
        finally:
            await trans.rollback()
            await session.close()

@pytest_asyncio.fixture
async def client(db_session):
    from api.main import app
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
```

### 测试隔离

| 方式 | 说明 |
|------|------|
| 事务 rollback | 每测试一个事务，结束回滚 |
| 依赖覆盖 | `app.dependency_overrides[get_db]` 注入测试 session |
| 无需 clean_db | 不再需要 DELETE FROM 清理 |

### 测试文件改造

| 测试文件 | 操作 | 难度 |
|----------|------|------|
| conftest.py + tests/conftest.py | fixture 体系重建 | 高 |
| test_admin_functions_comprehensive.py | raw SQL → async db 函数 | 中 |
| test_db_utils_*.py (5 个) | 加 session 参数，改 async | 中 |
| test_integration_*.py (4 个) | 改用 async client | 中 |
| test_real_database.py | raw SQL → ORM | 中 |
| test_passwords.py | 少量 DB 操作 | 低 |
| test_password_recovery.py | 少量 DB 操作 | 低 |
| test_db_adapter_critical_exceptions.py | 删除 | — |
| test_db_adapter_connection_pool_critical.py | 删除 | — |
| test_connection_pool_concurrency_critical.py | 删除 | — |

### 测试数量预期

| 指标 | 改造前 | 改造后 |
|------|--------|--------|
| 后端 pytest | 988 | ~950-970 (删除 3 个 adapter/pool 测试文件) |
| 前端 vitest | 169 | 169 (不变) |
| E2E playwright | 260 | 260 (不变) |

### 新增测试依赖

- `pytest-asyncio`
- `httpx` (AsyncClient)

---

## 9. 删除清单

| 文件 | 理由 |
|------|------|
| db_adapter.py | 连接池 + adapt_sql，被 SQLAlchemy 替代 |
| db_utils.py | shim，不再需要 |
| db/connection.py | get_db_connection()，被 database.py 替代 |
| db/helpers.py | adapt_sql wrapper 等，不再需要 |
| db/_proxy.py | lazy proxy，不再需要 |
| db/schema.py | CREATE TABLE，被 models/ + Alembic 替代 |
| tests/test_db_adapter_critical_exceptions.py | 测已删模块 |
| tests/test_db_adapter_connection_pool_critical.py | 测已删模块 |
| tests/test_connection_pool_concurrency_critical.py | 测已删模块 |

---

## 10. 新增依赖

| 包 | 用途 | 替代 |
|----|------|------|
| sqlalchemy[asyncio] | ORM + 异步支持 | — |
| asyncpg | 异步 PostgreSQL 驱动 | psycopg2-binary |
| alembic | schema 迁移管理 | 手写 CREATE TABLE |
| pytest-asyncio | async 测试支持 | — |
| httpx | AsyncClient 测试 | requests/TestClient |

psycopg2-binary 在全部改完、确认零引用后移除。

---

## 11. 生产部署

### 首次部署

```bash
pip install asyncpg "sqlalchemy[asyncio]" alembic pytest-asyncio httpx
alembic stamp head    # 标记生产库为基线
# 重启应用（startup 自动 upgrade head，首次无新迁移）
```

### 后续部署

```bash
git pull
# 重启应用（startup 自动 upgrade head）
```

---

## 12. 保留不动的文件

| 文件 | 理由 |
|------|------|
| db/password.py | 纯 bcrypt，不涉及 SQL |
| db/session.py | 纯内存状态 |
| db_config.py | database.py 复用 get_database_url() |
| security/tokens.py | JWT，不涉及 DB |
| security/utils.py | 安全工具，不涉及 DB |
| pricing/ | 定价计算纯逻辑 |

---

## 13. 约束

- Python 函数 < 100 行
- Python 文件 < 500 行
- 测试文件 < 800 行
- 所有代码通过 `python -m flake8`
- 所有测试通过 `python -m pytest --tb=short`
- 前端测试通过 `npx vitest run`
- E2E 测试通过（HTTP 层不受后端重构影响）
