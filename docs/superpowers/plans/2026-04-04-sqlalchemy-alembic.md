# SQLAlchemy ORM + Alembic 全量重构实现计划

## Goal
将整个数据库层从 raw SQL + psycopg2 替换为 SQLAlchemy ORM + Alembic 迁移 + asyncpg 异步驱动。

## Architecture
- **ORM**: SQLAlchemy 2.0 (Mapped[] + mapped_column)
- **迁移**: Alembic (async env.py)
- **驱动**: asyncpg (替换 psycopg2-binary)
- **会话**: AsyncSession, 请求级依赖注入 (get_db)
- **commit**: get_db 自动 commit/rollback, db/ 函数用 flush() 拿 ID

## Tech
- Python 3.10+, FastAPI, PostgreSQL
- sqlalchemy[asyncio], asyncpg, alembic
- pytest-asyncio, httpx (测试)
- 文件约束: 函数 < 100行, 文件 < 500行, 测试 < 800行

## Design Spec
`docs/superpowers/specs/2026-04-04-sqlalchemy-alembic-design.md`

## 关键勘误（设计规格 vs 实际代码）
1. `get_db_url()` 是正确的函数名（规格中写成 `get_database_url()` 是错误的）
2. `api/main.py` 使用 `lifespan` context manager（规格写成 `@app.on_event("startup")` 是错误的）
3. User 模型有 30 列（规格中写 13 列只是示例，不完整）
4. `exchange_rates` 表不存在于生产库，但 `db/exchange.py` 引用它 — 需要在 ORM 模型中定义，初始迁移会包含它
5. 路由 `subscriptions.py` 引用 `status/sort/code/name` 列名，但生产库是 `is_active/sort_order/plan_code/plan_name` — 现有代码已经处理了这个映射，ORM 模型按生产库列名定义

---

## 文件结构总览

### 新增文件 (15)
```
models/__init__.py              # Base + 导出所有模型
models/user.py                  # User(30), Plan(17), SubscriptionUpgradeHistory(12)
models/product.py               # Product(30)
models/logistics.py             # Logistics(35)
models/order.py                 # PaymentOrder(15)
models/config.py                # SystemConfig(5), ExchangeRate(4) — exchange_rates 是新表
models/session.py               # ActiveSession(9), LoginAttempt(6), UserLockout(3), TrustedDevice(8)
models/log.py                   # UserLoginLog(7), UserBehaviorLog(5), AdminActionLog(7), AlertRecord(10), AlertConfig(8), PasswordRecoveryLog(8), AuditLog(5)
models/cache.py                 # StatisticsCache(6)
database.py                     # async engine + session factory + get_db + run_migrations
alembic.ini                     # Alembic 配置
alembic/env.py                  # async 迁移运行器
alembic/script.py.mako          # 迁移模板
alembic/versions/               # 空目录，autogenerate 生成初始迁移
db/logistics_crud.py            # 物流 CRUD (6 函数)
db/sessions_crud.py             # 会话安全 DB 操作 (约 10 函数)
```

### 改写文件 (25+)
```
# db/ 包 — 函数签名 + 内部全部改写
db/__init__.py, db/users.py, db/products.py, db/admin.py, db/admin_helpers.py
db/logging_utils.py, db/statistics.py, db/subscriptions.py, db/plans.py
db/config.py, db/exchange.py

# 路由 — async + session 注入
api/dependencies.py, api/routes/admin.py, api/routes/auth.py
api/routes/logistics.py, api/routes/orders.py, api/routes/pricing.py
api/routes/settings.py, api/routes/statistics.py, api/routes/subscriptions.py
api/routes/products.py

# 根模块 — 手动 session 管理
payment_handler.py, session_security.py, session_security_enhanced.py
api/main.py

# 测试
conftest.py, tests/conftest.py (如有), 多个 test_*.py 文件
```

### 删除文件 (9)
```
db_adapter.py, db_utils.py, db/connection.py, db/helpers.py, db/_proxy.py, db/schema.py
tests/test_db_adapter_critical_exceptions.py
tests/test_db_adapter_connection_pool_critical.py
tests/test_connection_pool_concurrency_critical.py
```

### 不动文件
```
db/password.py (纯 bcrypt), db/session.py (纯内存), db_config.py (复用)
security/, pricing/, frontend/
```

---

## Task 1: 安装依赖 + 创建 models/ 包

### 1.1 安装新依赖

```bash
pip install "sqlalchemy[asyncio]" asyncpg alembic pytest-asyncio httpx
```

更新 `requirements.txt`（如存在）添加：
```
sqlalchemy[asyncio]
asyncpg
alembic
pytest-asyncio
httpx
```

### 1.2 创建 `models/__init__.py`

```python
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# 导入所有模型，确保 Base.metadata 包含全部表
from models.user import User, Plan, SubscriptionUpgradeHistory  # noqa: E402, F401
from models.product import Product  # noqa: E402, F401
from models.logistics import Logistics  # noqa: E402, F401
from models.order import PaymentOrder  # noqa: E402, F401
from models.config import SystemConfig, ExchangeRate  # noqa: E402, F401
from models.session import (  # noqa: E402, F401
    ActiveSession, LoginAttempt, UserLockout, TrustedDevice,
)
from models.log import (  # noqa: E402, F401
    UserLoginLog, UserBehaviorLog, AdminActionLog,
    AlertRecord, AlertConfig, PasswordRecoveryLog, AuditLog,
)
from models.cache import StatisticsCache  # noqa: E402, F401

__all__ = [
    "Base",
    "User", "Plan", "SubscriptionUpgradeHistory",
    "Product",
    "Logistics",
    "PaymentOrder",
    "SystemConfig", "ExchangeRate",
    "ActiveSession", "LoginAttempt", "UserLockout", "TrustedDevice",
    "UserLoginLog", "UserBehaviorLog", "AdminActionLog",
    "AlertRecord", "AlertConfig", "PasswordRecoveryLog", "AuditLog",
    "StatisticsCache",
]
```

### 1.3 创建 `models/user.py` — User(30列), Plan(17列), SubscriptionUpgradeHistory(12列)

```python
from typing import Optional
from sqlalchemy import String, Integer, Float, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column
from models import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[Optional[str]] = mapped_column(
        String, unique=True,
    )
    password: Mapped[Optional[str]] = mapped_column(String)
    role: Mapped[Optional[str]] = mapped_column(String)
    email: Mapped[Optional[str]] = mapped_column(String, unique=True)
    preferred_mode: Mapped[Optional[str]] = mapped_column(
        String, server_default=text("'fast'"),
    )
    user_type: Mapped[Optional[str]] = mapped_column(
        String, server_default=text("'permanent'"),
    )
    expiry_date: Mapped[Optional[str]] = mapped_column(String)
    remaining_calculations: Mapped[Optional[int]] = mapped_column(
        Integer, server_default=text("'-1'"),
    )
    first_login_date: Mapped[Optional[str]] = mapped_column(String)
    test_days_remaining: Mapped[Optional[int]] = mapped_column(
        Integer, server_default=text("0"),
    )
    subscription_type: Mapped[Optional[str]] = mapped_column(
        String, server_default=text("'free'"),
    )
    subscription_expires: Mapped[Optional[int]] = mapped_column(Integer)
    efficiency_promo_used: Mapped[Optional[int]] = mapped_column(
        Integer, server_default=text("0"),
    )
    created_at: Mapped[Optional[str]] = mapped_column(
        String, server_default=text("''"),
    )
    last_login: Mapped[Optional[str]] = mapped_column(String)
    is_test_user: Mapped[Optional[int]] = mapped_column(
        Integer, server_default=text("0"),
    )
    billing_cycle: Mapped[Optional[str]] = mapped_column(
        String, server_default=text("'month'"),
    )
    last_paid_amount: Mapped[Optional[float]] = mapped_column(
        Float, server_default=text("0"),
    )
    subscription_start: Mapped[Optional[int]] = mapped_column(Integer)
    security_q1: Mapped[Optional[str]] = mapped_column(String)
    security_a1: Mapped[Optional[str]] = mapped_column(String)
    security_q2: Mapped[Optional[str]] = mapped_column(String)
    security_a2: Mapped[Optional[str]] = mapped_column(String)
    reset_locked_until: Mapped[Optional[float]] = mapped_column(Float)
    reset_attempt_count: Mapped[Optional[int]] = mapped_column(
        Integer, server_default=text("0"),
    )
    reset_last_attempt: Mapped[Optional[float]] = mapped_column(Float)
    logistics_templates_limit: Mapped[Optional[int]] = mapped_column(
        Integer, server_default=text("'-1'"),
    )
    is_auto_renew: Mapped[Optional[int]] = mapped_column(
        Integer, server_default=text("0"),
    )
    is_frozen: Mapped[Optional[int]] = mapped_column(
        Integer, server_default=text("0"),
    )


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_code: Mapped[str] = mapped_column(
        String, unique=True, nullable=False,
    )
    plan_name: Mapped[str] = mapped_column(String, nullable=False)
    display_price_month: Mapped[float] = mapped_column(
        Float, nullable=False,
    )
    display_price_year: Mapped[float] = mapped_column(
        Float, nullable=False,
    )
    actual_price_month: Mapped[float] = mapped_column(
        Float, nullable=False,
    )
    actual_price_year: Mapped[float] = mapped_column(
        Float, nullable=False,
    )
    test_price_month: Mapped[float] = mapped_column(
        Float, nullable=False, server_default=text("0"),
    )
    test_price_year: Mapped[float] = mapped_column(
        Float, nullable=False, server_default=text("0"),
    )
    calc_limit: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("'-1'"),
    )
    logistics_limit: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1"),
    )
    description: Mapped[Optional[str]] = mapped_column(String)
    features: Mapped[Optional[str]] = mapped_column(String)
    is_active: Mapped[Optional[int]] = mapped_column(
        Integer, server_default=text("1"),
    )
    sort_order: Mapped[Optional[int]] = mapped_column(
        Integer, server_default=text("0"),
    )
    created_at: Mapped[Optional[int]] = mapped_column(
        Integer,
        server_default=text("date_part('epoch'::text, now())"),
    )
    updated_at: Mapped[Optional[int]] = mapped_column(
        Integer,
        server_default=text("date_part('epoch'::text, now())"),
    )


class SubscriptionUpgradeHistory(Base):
    __tablename__ = "subscription_upgrade_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    from_plan: Mapped[str] = mapped_column(String, nullable=False)
    to_plan: Mapped[str] = mapped_column(String, nullable=False)
    from_cycle: Mapped[Optional[str]] = mapped_column(String)
    to_cycle: Mapped[Optional[str]] = mapped_column(String)
    upgrade_time: Mapped[int] = mapped_column(Integer, nullable=False)
    remaining_value: Mapped[Optional[float]] = mapped_column(
        Float, server_default=text("0"),
    )
    difference_paid: Mapped[Optional[float]] = mapped_column(
        Float, server_default=text("0"),
    )
    target_price: Mapped[float] = mapped_column(Float, nullable=False)
    payment_order_id: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[Optional[int]] = mapped_column(
        Integer,
        server_default=text("date_part('epoch'::text, now())"),
    )
```

### 1.4 创建 `models/product.py` — Product(30列)

```python
from typing import Optional
from sqlalchemy import String, Integer, Float, text
from sqlalchemy.orm import Mapped, mapped_column
from models import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String)
    russian_name: Mapped[Optional[str]] = mapped_column(String)
    category: Mapped[Optional[str]] = mapped_column(String)
    model: Mapped[Optional[str]] = mapped_column(String)
    unit_price: Mapped[Optional[float]] = mapped_column(Float)
    weight_g: Mapped[Optional[int]] = mapped_column(Integer)
    length_cm: Mapped[Optional[int]] = mapped_column(Integer)
    width_cm: Mapped[Optional[int]] = mapped_column(Integer)
    height_cm: Mapped[Optional[int]] = mapped_column(Integer)
    is_cylinder: Mapped[Optional[int]] = mapped_column(Integer)
    cylinder_diameter: Mapped[Optional[float]] = mapped_column(Float)
    cylinder_length: Mapped[Optional[float]] = mapped_column(Float)
    has_battery: Mapped[Optional[int]] = mapped_column(Integer)
    battery_capacity_wh: Mapped[Optional[float]] = mapped_column(Float)
    battery_capacity_mah: Mapped[Optional[int]] = mapped_column(Integer)
    battery_voltage: Mapped[Optional[float]] = mapped_column(Float)
    has_msds: Mapped[Optional[int]] = mapped_column(Integer)
    has_liquid: Mapped[Optional[int]] = mapped_column(Integer)
    shipping_fee: Mapped[Optional[float]] = mapped_column(Float)
    labeling_fee: Mapped[Optional[float]] = mapped_column(Float)
    promotion_discount: Mapped[Optional[float]] = mapped_column(
        Float, server_default=text("0.05"),
    )
    promotion_cost_rate: Mapped[Optional[float]] = mapped_column(
        Float, server_default=text("0.115"),
    )
    target_profit_margin: Mapped[Optional[float]] = mapped_column(
        Float, server_default=text("0.5"),
    )
    commission_rate: Mapped[Optional[float]] = mapped_column(
        Float, server_default=text("0.17"),
    )
    withdrawal_fee_rate: Mapped[Optional[float]] = mapped_column(
        Float, server_default=text("0.01"),
    )
    payment_processing_fee: Mapped[Optional[float]] = mapped_column(
        Float, server_default=text("0.01"),
    )
    return_rate: Mapped[Optional[float]] = mapped_column(
        Float, server_default=text("0"),
    )
    vat_rate: Mapped[Optional[float]] = mapped_column(
        Float, server_default=text("0"),
    )
    is_test_data: Mapped[Optional[int]] = mapped_column(
        Integer, server_default=text("0"),
    )
```

### 1.5 创建 `models/logistics.py` — Logistics(35列)

```python
from typing import Optional
from sqlalchemy import String, Integer, Float, text
from sqlalchemy.orm import Mapped, mapped_column
from models import Base


class Logistics(Base):
    __tablename__ = "logistics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String)
    type: Mapped[Optional[str]] = mapped_column(String)
    min_days: Mapped[Optional[int]] = mapped_column(Integer)
    max_days: Mapped[Optional[int]] = mapped_column(Integer)
    price_limit: Mapped[Optional[float]] = mapped_column(Float)
    price_limit_rub: Mapped[Optional[float]] = mapped_column(Float)
    price_min: Mapped[Optional[float]] = mapped_column(
        Float, server_default=text("0"),
    )
    price_min_rub: Mapped[Optional[float]] = mapped_column(
        Float, server_default=text("0"),
    )
    base_fee: Mapped[Optional[float]] = mapped_column(
        Float, server_default=text("0"),
    )
    min_weight: Mapped[Optional[int]] = mapped_column(Integer)
    max_weight: Mapped[Optional[int]] = mapped_column(Integer)
    max_sum_of_sides: Mapped[Optional[int]] = mapped_column(Integer)
    max_longest_side: Mapped[Optional[int]] = mapped_column(Integer)
    max_second_side: Mapped[Optional[int]] = mapped_column(
        Integer, server_default=text("0"),
    )
    min_second_side: Mapped[Optional[int]] = mapped_column(
        Integer, server_default=text("0"),
    )
    min_length: Mapped[Optional[int]] = mapped_column(
        Integer, server_default=text("0"),
    )
    max_cylinder_sum: Mapped[Optional[int]] = mapped_column(
        Integer, server_default=text("0"),
    )
    min_cylinder_sum: Mapped[Optional[int]] = mapped_column(
        Integer, server_default=text("0"),
    )
    max_cylinder_length: Mapped[Optional[int]] = mapped_column(
        Integer, server_default=text("0"),
    )
    min_cylinder_length: Mapped[Optional[int]] = mapped_column(
        Integer, server_default=text("0"),
    )
    volume_mode: Mapped[Optional[str]] = mapped_column(
        String, server_default=text("'none'"),
    )
    longest_side_threshold: Mapped[Optional[int]] = mapped_column(
        Integer, server_default=text("0"),
    )
    allow_battery: Mapped[Optional[int]] = mapped_column(Integer)
    allow_liquid: Mapped[Optional[int]] = mapped_column(Integer)
    battery_capacity_limit_wh: Mapped[Optional[float]] = mapped_column(
        Float, server_default=text("0"),
    )
    require_msds: Mapped[Optional[int]] = mapped_column(
        Integer, server_default=text("0"),
    )
    fee_mode: Mapped[Optional[str]] = mapped_column(
        String, server_default=text("'base_plus_continue'"),
    )
    first_fee: Mapped[Optional[float]] = mapped_column(
        Float, server_default=text("0"),
    )
    first_weight_g: Mapped[Optional[int]] = mapped_column(
        Integer, server_default=text("0"),
    )
    continue_fee: Mapped[Optional[float]] = mapped_column(
        Float, server_default=text("0"),
    )
    continue_unit: Mapped[Optional[str]] = mapped_column(
        String, server_default=text("'100'"),
    )
    volume_coefficient: Mapped[Optional[float]] = mapped_column(
        Float, server_default=text("5000"),
    )
    delivery_method: Mapped[Optional[str]] = mapped_column(
        String, server_default=text("'unknown'"),
    )
    priority_group: Mapped[Optional[str]] = mapped_column(
        String, server_default=text("'D'"),
    )
    price_limit_currency: Mapped[Optional[str]] = mapped_column(
        String, server_default=text("'RUB'"),
    )
    price_min_currency: Mapped[Optional[str]] = mapped_column(
        String, server_default=text("'RUB'"),
    )
    is_active: Mapped[Optional[int]] = mapped_column(
        Integer, server_default=text("1"),
    )
```

### 1.6 创建 `models/order.py` — PaymentOrder(15列)

```python
from typing import Optional
from sqlalchemy import String, Integer, Float, text
from sqlalchemy.orm import Mapped, mapped_column
from models import Base


class PaymentOrder(Base):
    __tablename__ = "payment_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[str] = mapped_column(
        String, unique=True, nullable=False,
    )
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    duration: Mapped[Optional[str]] = mapped_column(String)
    status: Mapped[Optional[str]] = mapped_column(
        String, server_default=text("'PENDING'"),
    )
    wechat_transaction_id: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[Optional[int]] = mapped_column(Integer)
    order_type: Mapped[Optional[str]] = mapped_column(String)
    is_upgrade: Mapped[Optional[int]] = mapped_column(
        Integer, server_default=text("0"),
    )
    upgrade_from_plan: Mapped[Optional[str]] = mapped_column(String)
    upgrade_to_plan: Mapped[Optional[str]] = mapped_column(String)
    remaining_value: Mapped[Optional[float]] = mapped_column(
        Float, server_default=text("0"),
    )
```

### 1.7 创建 `models/config.py` — SystemConfig(5列), ExchangeRate(4列 — 新表)

```python
from typing import Optional
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Float, text
from sqlalchemy.orm import Mapped, mapped_column
from models import Base


class SystemConfig(Base):
    __tablename__ = "system_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    config_key: Mapped[str] = mapped_column(
        String, unique=True, nullable=False,
    )
    config_value: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String)
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP"),
    )


class ExchangeRate(Base):
    """汇率缓存表 — 生产库尚不存在，初始迁移会创建。"""
    __tablename__ = "exchange_rates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    currency_pair: Mapped[str] = mapped_column(
        String, unique=True, nullable=False,
    )
    rate: Mapped[float] = mapped_column(Float, nullable=False)
    last_updated: Mapped[Optional[datetime]] = mapped_column(DateTime)
    source: Mapped[Optional[str]] = mapped_column(String)
```

### 1.8 创建 `models/session.py` — ActiveSession(9列), LoginAttempt(6列), UserLockout(3列), TrustedDevice(8列)

```python
from typing import Optional
from sqlalchemy import (
    String, Integer, Float, Boolean, UniqueConstraint, text,
)
from sqlalchemy.orm import Mapped, mapped_column
from models import Base


class ActiveSession(Base):
    __tablename__ = "active_sessions"

    session_id: Mapped[str] = mapped_column(
        String, primary_key=True,
    )
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[float] = mapped_column(Float, nullable=False)
    last_activity: Mapped[float] = mapped_column(Float, nullable=False)
    last_rotation: Mapped[Optional[float]] = mapped_column(
        Float, server_default=text("0"),
    )
    ip_address: Mapped[Optional[str]] = mapped_column(String)
    user_agent: Mapped[Optional[str]] = mapped_column(String)
    is_active: Mapped[Optional[bool]] = mapped_column(
        Boolean, server_default=text("true"),
    )
    device_fingerprint: Mapped[Optional[str]] = mapped_column(String)


class LoginAttempt(Base):
    __tablename__ = "login_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    identifier: Mapped[str] = mapped_column(String, nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String)
    timestamp: Mapped[float] = mapped_column(Float, nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    user_agent: Mapped[Optional[str]] = mapped_column(String)


class UserLockout(Base):
    __tablename__ = "user_lockouts"

    identifier: Mapped[str] = mapped_column(
        String, primary_key=True, unique=True,
    )
    locked_until: Mapped[float] = mapped_column(Float, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False)


class TrustedDevice(Base):
    __tablename__ = "trusted_devices"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "device_fingerprint",
            name="trusted_devices_user_id_device_fingerprint_key",
        ),
        UniqueConstraint(
            "user_id", "device_fingerprint",
            name="trusted_devices_user_device_key",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    ip_address: Mapped[str] = mapped_column(String, nullable=False)
    device_fingerprint: Mapped[str] = mapped_column(
        String, nullable=False,
    )
    user_agent: Mapped[Optional[str]] = mapped_column(String)
    trusted_at: Mapped[float] = mapped_column(Float, nullable=False)
    last_used: Mapped[float] = mapped_column(Float, nullable=False)
    is_active: Mapped[Optional[bool]] = mapped_column(
        Boolean, server_default=text("true"),
    )
```

### 1.9 创建 `models/log.py` — 7个模型

```python
from typing import Optional
from datetime import datetime
from sqlalchemy import String, Integer, Float, DateTime, text
from sqlalchemy.orm import Mapped, mapped_column
from models import Base


class UserLoginLog(Base):
    __tablename__ = "user_login_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    login_time: Mapped[int] = mapped_column(Integer, nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String)
    user_agent: Mapped[Optional[str]] = mapped_column(String)
    device_type: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[Optional[int]] = mapped_column(
        Integer,
        server_default=text("date_part('epoch'::text, now())"),
    )


class UserBehaviorLog(Base):
    __tablename__ = "user_behavior_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    behavior_type: Mapped[str] = mapped_column(String, nullable=False)
    behavior_detail: Mapped[Optional[str]] = mapped_column(String)
    calculation_mode: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[Optional[int]] = mapped_column(
        Integer,
        server_default=text("date_part('epoch'::text, now())"),
    )


class AdminActionLog(Base):
    __tablename__ = "admin_action_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    admin_id: Mapped[int] = mapped_column(Integer, nullable=False)
    action_type: Mapped[str] = mapped_column(String, nullable=False)
    action_detail: Mapped[Optional[str]] = mapped_column(String)
    target_user_id: Mapped[Optional[int]] = mapped_column(Integer)
    target_type: Mapped[Optional[str]] = mapped_column(String)
    ip_address: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[Optional[int]] = mapped_column(
        Integer,
        server_default=text("date_part('epoch'::text, now())"),
    )


class AlertRecord(Base):
    __tablename__ = "alert_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    alert_type: Mapped[str] = mapped_column(String, nullable=False)
    alert_level: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    threshold_value: Mapped[Optional[float]] = mapped_column(Float)
    actual_value: Mapped[Optional[float]] = mapped_column(Float)
    status: Mapped[Optional[str]] = mapped_column(
        String, server_default=text("'unhandled'"),
    )
    handled_by: Mapped[Optional[int]] = mapped_column(Integer)
    handled_at: Mapped[Optional[int]] = mapped_column(Integer)
    handle_note: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[Optional[int]] = mapped_column(
        Integer,
        server_default=text("date_part('epoch'::text, now())"),
    )


class AlertConfig(Base):
    __tablename__ = "alert_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    metric_name: Mapped[str] = mapped_column(String, nullable=False)
    threshold_value: Mapped[Optional[float]] = mapped_column(Float)
    comparison_type: Mapped[Optional[str]] = mapped_column(String)
    is_enabled: Mapped[Optional[int]] = mapped_column(
        Integer, server_default=text("1"),
    )
    notification_method: Mapped[Optional[str]] = mapped_column(
        String, server_default=text("'system'"),
    )
    created_at: Mapped[Optional[int]] = mapped_column(
        Integer,
        server_default=text("date_part('epoch'::text, now())"),
    )
    updated_at: Mapped[Optional[int]] = mapped_column(
        Integer,
        server_default=text("date_part('epoch'::text, now())"),
    )


class PasswordRecoveryLog(Base):
    __tablename__ = "password_recovery_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String, nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    success: Mapped[Optional[int]] = mapped_column(
        Integer, server_default=text("0"),
    )
    attempt_count: Mapped[Optional[int]] = mapped_column(
        Integer, server_default=text("0"),
    )
    admin_name: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[Optional[int]] = mapped_column(
        Integer,
        server_default=text("date_part('epoch'::text, now())"),
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    admin_id: Mapped[int] = mapped_column(Integer, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String, nullable=False)
    details: Mapped[Optional[str]] = mapped_column(String)
    timestamp: Mapped[Optional[datetime]] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP"),
    )
```

### 1.10 创建 `models/cache.py` — StatisticsCache(6列)

```python
from typing import Optional
from sqlalchemy import String, Integer, text
from sqlalchemy.orm import Mapped, mapped_column
from models import Base


class StatisticsCache(Base):
    __tablename__ = "statistics_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cache_key: Mapped[str] = mapped_column(
        String, unique=True, nullable=False,
    )
    cache_data: Mapped[str] = mapped_column(String, nullable=False)
    expires_at: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[Optional[int]] = mapped_column(
        Integer,
        server_default=text("date_part('epoch'::text, now())"),
    )
    updated_at: Mapped[Optional[int]] = mapped_column(
        Integer,
        server_default=text("date_part('epoch'::text, now())"),
    )
```

### 验证
```bash
python -c "from models import Base; print(f'Tables: {len(Base.metadata.tables)}'); print(list(Base.metadata.tables.keys()))"
# 期望输出: Tables: 20 (19 已有表 + 1 exchange_rates 新表)

python -m flake8 models/
```

### Commit
```
git add models/ requirements.txt
git commit -m "feat: add SQLAlchemy ORM models for all 20 tables"
```

---

## Task 2: 创建 database.py — 异步引擎 + 会话工厂 + 迁移

### 2.1 创建 `database.py`

```python
import logging
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)

from db_config import get_db_url

logger = logging.getLogger(__name__)

_sync_url = get_db_url()
_async_url = _sync_url.replace(
    "postgresql://", "postgresql+asyncpg://",
)

engine = create_async_engine(
    _async_url,
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
    """请求级会话依赖。自动 commit/rollback。"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def run_migrations() -> None:
    """同步调用 Alembic upgrade head。在 app startup 时调用。"""
    from alembic.config import Config
    from alembic import command
    import os

    alembic_ini = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "alembic.ini",
    )
    alembic_cfg = Config(alembic_ini)
    command.upgrade(alembic_cfg, "head")
    logger.info("Alembic migrations applied successfully")
```

### 验证
```bash
python -m flake8 database.py
python -c "from database import engine, AsyncSessionLocal, get_db, run_migrations; print('OK')"
```

### Commit
```
git add database.py
git commit -m "feat: add async database engine and session management"
```

---

## Task 3: 配置 Alembic

### 3.1 创建 `alembic.ini`

```ini
[alembic]
script_location = alembic
prepend_sys_path = .

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

注意：`sqlalchemy.url` 不写在 ini 中，由 env.py 动态设置。

### 3.2 创建 `alembic/env.py`

```python
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 动态设置 URL，不硬编码
from db_config import get_db_url  # noqa: E402
_sync_url = get_db_url()
_async_url = _sync_url.replace(
    "postgresql://", "postgresql+asyncpg://",
)
config.set_main_option("sqlalchemy.url", _async_url)

from models import Base  # noqa: E402
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """离线模式：生成 SQL 脚本。"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """在线模式：使用 async engine 执行迁移。"""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

### 3.3 创建 `alembic/script.py.mako`

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

### 3.4 生成初始迁移并 stamp

```bash
# 确保 alembic/versions/ 目录存在
mkdir -p alembic/versions

# 生成迁移（会包含 exchange_rates 的 CREATE TABLE + 其余 19 表的 noop）
alembic revision --autogenerate -m "initial schema"

# 检查生成的迁移文件：
# - 已有的 19 张表不应有 CREATE TABLE（它们已存在）
# - exchange_rates 应该有 CREATE TABLE（新表）
# 如果 autogenerate 对已有表生成了 CREATE TABLE，需要手动清理

# 在生产库标记基线
alembic stamp head
```

**关键**：autogenerate 对比 metadata vs DB。19 张已有表应 match（如果 ORM 模型正确），只有 `exchange_rates` 是新表。如果有 diff，说明模型定义有误，需要修正。

### 验证
```bash
python -m flake8 alembic/env.py
alembic heads  # 应显示一个 head revision
alembic current  # 应显示 head（因为 stamp 了）
```

### Commit
```
git add alembic.ini alembic/
git commit -m "feat: configure Alembic with async support and initial migration"
```

---

## Task 4: 改写 db/ 包 — 核心模块

**通用改写规则**（适用于 Task 4-5 所有 db/ 文件）：
1. 删除 `from db._proxy import _db` 和所有 `_db.xxx` 调用
2. 删除 `from db.helpers import adapt_sql` 和所有 `adapt_sql()` 调用
3. 删除 `with _db.get_db_connection() as (conn, c):` 块
4. 函数加 `async def`，第一个参数加 `session: AsyncSession`
5. SQL → ORM（select/insert/update/delete 用 SQLAlchemy 表达式）
6. `conn.commit()` → 删除（get_db 管理）
7. 需要 ID 时 → `session.flush()` 后读 `obj.id`
8. `c.fetchone()` → `result.scalar_one_or_none()` 或 `result.one_or_none()`
9. `c.fetchall()` → `result.scalars().all()` 或 `result.all()`
10. 每个文件顶部加 `from sqlalchemy.ext.asyncio import AsyncSession`
11. 每个文件顶部加对应模型的 import

### 4.1 改写 `db/config.py`

**改写前签名**：`get_system_config(key)`, `set_system_config(key, value, description)`, `is_registration_open()`

**改写后**：

```python
import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.config import SystemConfig

logger = logging.getLogger(__name__)


async def get_system_config(
    session: AsyncSession, key: str,
) -> Optional[str]:
    """获取系统配置值。"""
    stmt = select(SystemConfig.config_value).where(
        SystemConfig.config_key == key,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def set_system_config(
    session: AsyncSession,
    key: str,
    value: str,
    description: str = "",
) -> None:
    """设置系统配置（upsert）。"""
    stmt = select(SystemConfig).where(
        SystemConfig.config_key == key,
    )
    result = await session.execute(stmt)
    config = result.scalar_one_or_none()
    if config:
        config.config_value = value
        if description:
            config.description = description
    else:
        config = SystemConfig(
            config_key=key,
            config_value=value,
            description=description,
        )
        session.add(config)


async def is_registration_open(session: AsyncSession) -> bool:
    """检查是否允许注册。"""
    value = await get_system_config(session, "registration_open")
    return value != "0"


async def get_all_config(session: AsyncSession) -> list[dict]:
    """获取所有系统配置（给管理面板用）。"""
    stmt = select(SystemConfig).order_by(SystemConfig.config_key)
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "config_key": r.config_key,
            "config_value": r.config_value,
            "description": r.description,
            "updated_at": (
                r.updated_at.isoformat() if r.updated_at else None
            ),
        }
        for r in rows
    ]
```

### 4.2 改写 `db/exchange.py`

```python
import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.config import ExchangeRate

logger = logging.getLogger(__name__)


async def get_exchange_rate_fallback(
    session: AsyncSession, currency_pair: str,
) -> Optional[float]:
    """从数据库读取汇率 fallback 值。"""
    try:
        stmt = select(ExchangeRate.rate).where(
            ExchangeRate.currency_pair == currency_pair,
        )
        result = await session.execute(stmt)
        value = result.scalar_one_or_none()
        return float(value) if value is not None else None
    except Exception:
        logger.debug("从数据库获取汇率失败", exc_info=True)
        return None


async def update_exchange_rate_fallback(
    session: AsyncSession,
    currency_pair: str,
    rate: float,
    source: str = "",
) -> None:
    """更新汇率 fallback 值（upsert）。"""
    try:
        from datetime import datetime, timezone
        stmt = select(ExchangeRate).where(
            ExchangeRate.currency_pair == currency_pair,
        )
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()
        now = datetime.now(timezone.utc)
        if record:
            record.rate = rate
            record.last_updated = now
            record.source = source
        else:
            record = ExchangeRate(
                currency_pair=currency_pair,
                rate=rate,
                last_updated=now,
                source=source,
            )
            session.add(record)
    except Exception:
        logger.debug("更新汇率 fallback 失败", exc_info=True)
```

### 4.3 改写 `db/plans.py`

**改写前签名**（8 函数）：`get_plans()`, `get_plan_by_code(code)`, `get_plan_by_id(plan_id)`, `create_plan(data)`, `update_plan(plan_id, data)`, `delete_plan(plan_id)`, `toggle_plan_active(plan_id)`, `get_plan_price(plan_code, billing_cycle)`

**改写后**：

```python
import logging
from typing import Optional

from sqlalchemy import select, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import Plan

logger = logging.getLogger(__name__)


def _plan_to_dict(plan: Plan) -> dict:
    """Plan ORM 对象转字典。"""
    return {
        "id": plan.id,
        "plan_code": plan.plan_code,
        "plan_name": plan.plan_name,
        "display_price_month": plan.display_price_month,
        "display_price_year": plan.display_price_year,
        "actual_price_month": plan.actual_price_month,
        "actual_price_year": plan.actual_price_year,
        "test_price_month": plan.test_price_month,
        "test_price_year": plan.test_price_year,
        "calc_limit": plan.calc_limit,
        "logistics_limit": plan.logistics_limit,
        "description": plan.description,
        "features": plan.features,
        "is_active": plan.is_active,
        "sort_order": plan.sort_order,
        "created_at": plan.created_at,
        "updated_at": plan.updated_at,
    }


async def get_plans(session: AsyncSession) -> list[dict]:
    """获取所有计划。"""
    stmt = select(Plan).order_by(Plan.sort_order)
    result = await session.execute(stmt)
    return [_plan_to_dict(p) for p in result.scalars().all()]


async def get_plan_by_code(
    session: AsyncSession, code: str,
) -> Optional[dict]:
    """根据 plan_code 获取计划。"""
    stmt = select(Plan).where(Plan.plan_code == code)
    result = await session.execute(stmt)
    plan = result.scalar_one_or_none()
    return _plan_to_dict(plan) if plan else None


async def get_plan_by_id(
    session: AsyncSession, plan_id: int,
) -> Optional[dict]:
    """根据 ID 获取计划。"""
    plan = await session.get(Plan, plan_id)
    return _plan_to_dict(plan) if plan else None


async def create_plan(
    session: AsyncSession, data: dict,
) -> int:
    """创建计划，返回新 ID。"""
    plan = Plan(**data)
    session.add(plan)
    await session.flush()
    return plan.id


async def update_plan(
    session: AsyncSession, plan_id: int, data: dict,
) -> bool:
    """更新计划。"""
    plan = await session.get(Plan, plan_id)
    if not plan:
        return False
    for key, value in data.items():
        if hasattr(plan, key):
            setattr(plan, key, value)
    return True


async def delete_plan(
    session: AsyncSession, plan_id: int,
) -> bool:
    """删除计划。"""
    plan = await session.get(Plan, plan_id)
    if not plan:
        return False
    await session.delete(plan)
    return True


async def toggle_plan_active(
    session: AsyncSession, plan_id: int,
) -> Optional[int]:
    """切换计划启用状态，返回新状态。"""
    plan = await session.get(Plan, plan_id)
    if not plan:
        return None
    plan.is_active = 0 if plan.is_active == 1 else 1
    return plan.is_active


async def get_plan_price(
    session: AsyncSession,
    plan_code: str,
    billing_cycle: str = "month",
) -> Optional[float]:
    """获取计划价格。"""
    stmt = select(Plan).where(Plan.plan_code == plan_code)
    result = await session.execute(stmt)
    plan = result.scalar_one_or_none()
    if not plan:
        return None
    if billing_cycle == "year":
        return plan.actual_price_year
    return plan.actual_price_month
```

### 4.4 改写 `db/logging_utils.py`

```python
import logging
import time
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from models.log import (
    UserLoginLog, UserBehaviorLog, AdminActionLog, AlertRecord,
)

logger = logging.getLogger(__name__)


async def log_user_login(
    session: AsyncSession,
    user_id: int,
    ip_address: str = "",
    user_agent: str = "",
    device_type: str = "",
) -> None:
    """记录用户登录。"""
    try:
        record = UserLoginLog(
            user_id=user_id,
            login_time=int(time.time()),
            ip_address=ip_address,
            user_agent=user_agent,
            device_type=device_type,
        )
        session.add(record)
    except Exception:
        logger.debug("记录用户登录失败", exc_info=True)


async def log_user_behavior(
    session: AsyncSession,
    user_id: int,
    behavior_type: str,
    behavior_detail: str = "",
    calculation_mode: str = "",
) -> None:
    """记录用户行为。"""
    try:
        record = UserBehaviorLog(
            user_id=user_id,
            behavior_type=behavior_type,
            behavior_detail=behavior_detail,
            calculation_mode=calculation_mode,
        )
        session.add(record)
    except Exception:
        logger.debug("记录用户行为失败", exc_info=True)


async def log_admin_action(
    session: AsyncSession,
    admin_id: int,
    action_type: str,
    action_detail: str = "",
    target_user_id: Optional[int] = None,
    target_type: str = "",
    ip_address: str = "",
) -> None:
    """记录管理员操作。"""
    try:
        record = AdminActionLog(
            admin_id=admin_id,
            action_type=action_type,
            action_detail=action_detail,
            target_user_id=target_user_id,
            target_type=target_type,
            ip_address=ip_address,
        )
        session.add(record)
    except Exception:
        logger.debug("记录管理员操作失败", exc_info=True)


async def create_alert(
    session: AsyncSession,
    alert_type: str,
    alert_level: str,
    description: str,
    threshold_value: Optional[float] = None,
    actual_value: Optional[float] = None,
) -> Optional[int]:
    """创建告警记录，返回 ID。"""
    try:
        record = AlertRecord(
            alert_type=alert_type,
            alert_level=alert_level,
            description=description,
            threshold_value=threshold_value,
            actual_value=actual_value,
        )
        session.add(record)
        await session.flush()
        return record.id
    except Exception:
        logger.debug("创建告警失败", exc_info=True)
        return None
```

### 4.5 改写 `db/statistics.py`

这是最复杂的模块（聚合查询）。改写后代码较长，每个聚合函数独立。

**改写后**：

```python
import json
import logging
import time
from typing import Optional

from sqlalchemy import select, func, case, text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from models.cache import StatisticsCache
from models.user import User
from models.product import Product
from models.order import PaymentOrder
from models.log import UserLoginLog, UserBehaviorLog

logger = logging.getLogger(__name__)


# ── 缓存操作 ──

async def get_statistics_cache(
    session: AsyncSession, cache_key: str,
) -> Optional[str]:
    """获取统计缓存（未过期的）。"""
    now = int(time.time())
    stmt = select(StatisticsCache.cache_data).where(
        StatisticsCache.cache_key == cache_key,
        StatisticsCache.expires_at > now,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def set_statistics_cache(
    session: AsyncSession,
    cache_key: str,
    data: str,
    ttl: int = 300,
) -> None:
    """设置统计缓存（upsert）。"""
    now = int(time.time())
    stmt = select(StatisticsCache).where(
        StatisticsCache.cache_key == cache_key,
    )
    result = await session.execute(stmt)
    record = result.scalar_one_or_none()
    if record:
        record.cache_data = data
        record.expires_at = now + ttl
        record.updated_at = now
    else:
        record = StatisticsCache(
            cache_key=cache_key,
            cache_data=data,
            expires_at=now + ttl,
        )
        session.add(record)


async def clear_expired_cache(session: AsyncSession) -> int:
    """清除过期缓存，返回删除数。"""
    from sqlalchemy import delete as sa_delete
    now = int(time.time())
    stmt = sa_delete(StatisticsCache).where(
        StatisticsCache.expires_at <= now,
    )
    result = await session.execute(stmt)
    return result.rowcount


async def clear_all_statistics_cache(session: AsyncSession) -> int:
    """清除所有统计缓存。"""
    from sqlalchemy import delete as sa_delete
    stmt = sa_delete(StatisticsCache)
    result = await session.execute(stmt)
    return result.rowcount


# ── 统计查询（给路由 statistics.py 用）──

async def get_dashboard_stats(session: AsyncSession) -> dict:
    """获取仪表盘统计数据（用户数、产品数、订单数等）。"""
    # 总用户数
    total_users = await session.scalar(
        select(func.count(User.id)),
    )
    # 按 subscription_type 分组
    type_stmt = select(
        User.subscription_type,
        func.count(User.id),
    ).group_by(User.subscription_type)
    type_result = await session.execute(type_stmt)
    users_by_type = {
        row[0] or "free": row[1] for row in type_result.all()
    }
    # 总产品数
    total_products = await session.scalar(
        select(func.count(Product.id)),
    )
    # 已付款订单数
    paid_orders = await session.scalar(
        select(func.count(PaymentOrder.id)).where(
            PaymentOrder.status == "SUCCESS",
        ),
    )
    return {
        "total_users": total_users or 0,
        "users_by_type": users_by_type,
        "total_products": total_products or 0,
        "paid_orders": paid_orders or 0,
    }


async def count_total_users(session: AsyncSession) -> int:
    """总用户数。"""
    result = await session.scalar(select(func.count(User.id)))
    return result or 0


async def count_users_by_type(session: AsyncSession) -> dict:
    """按 subscription_type 统计用户数。"""
    stmt = select(
        User.subscription_type, func.count(User.id),
    ).group_by(User.subscription_type)
    result = await session.execute(stmt)
    return {row[0] or "free": row[1] for row in result.all()}


async def count_paid_orders(session: AsyncSession) -> int:
    """已支付订单数。"""
    result = await session.scalar(
        select(func.count(PaymentOrder.id)).where(
            PaymentOrder.status == "SUCCESS",
        ),
    )
    return result or 0


async def get_revenue_stats(session: AsyncSession) -> dict:
    """营收统计。"""
    total = await session.scalar(
        select(func.sum(PaymentOrder.amount)).where(
            PaymentOrder.status == "SUCCESS",
        ),
    )
    return {"total_revenue": total or 0}
```

**注意**：route `statistics.py` 中有 ~15 个不同的聚合查询。上面覆盖了核心函数。剩余的聚合查询需要在实施时根据路由文件的具体 SQL 逐个添加。这里不逐一列出（会超出计划文件 500 行限制），实施时 subagent 需要对照路由文件补全。

### 验证（Task 4 整体）
```bash
python -m flake8 db/config.py db/exchange.py db/plans.py db/logging_utils.py db/statistics.py
```

### Commit
```
git add db/config.py db/exchange.py db/plans.py db/logging_utils.py db/statistics.py
git commit -m "refactor: rewrite db/config, exchange, plans, logging, statistics to async ORM"
```

---

## Task 5: 改写 db/ 包 — 用户/产品/管理模块

### 5.1 改写 `db/users.py`

**关键函数和改写要点**：

- `create_user(session, username, password, role, email)` → `User(...)` + `session.add` + `flush`
- `verify_user(session, username, password)` → `select(User).where(User.username == username)` + `check_password()`
- `update_user_password(session, user_id, new_password)` → `session.get(User, user_id)` + 修改 `.password`
- `delete_user(session, user_id)` → `session.delete(user)`
- `get_user_preferred_mode(session, user_id)` → `select(User.preferred_mode).where(User.id == user_id)`
- `update_user_preferred_mode(session, user_id, mode)` → `user.preferred_mode = mode`

**新增函数**（从路由提取）：
- `find_by_username(session, username)` → `select(User).where(User.username == username)`
- `get_user_by_id(session, user_id)` → `session.get(User, user_id)`
- `get_user_role(session, user_id)` → `select(User.role).where(User.id == user_id)`

每个函数的具体 ORM 代码在实施时编写，遵循 Task 4 中的通用改写规则。函数签名必须保持 `async def xxx(session: AsyncSession, ...)` 格式。

**重要**：`verify_user` 保留 `from db.password import check_password` 调用（db/password.py 不改）。

### 5.2 改写 `db/products.py`

**关键函数**：

- `add_product(session, user_id, data)` → `Product(**data, user_id=user_id)` + `session.add`
- `get_all_products_for_user(session, user_id)` → `select(Product).where(Product.user_id == user_id)`
- `get_product_by_id(session, product_id, user_id)` → `select(Product).where(Product.id == product_id, Product.user_id == user_id)`
- `delete_product(session, product_id, user_id)` → `.delete()`
- `batch_delete_products(session, ids, user_id)` → `delete().where(Product.id.in_(ids))`
- `update_product(session, product_id, user_id, data)` → `setattr` 循环
- `batch_update_pricing_params(session, user_id, params)` → 查出所有产品，循环更新

### 5.3 改写 `db/admin.py` + `db/admin_helpers.py`

**最复杂的模块之一**。`admin.py` 有 12 函数，`admin_helpers.py` 有 5 个查询构建辅助函数。

**关键改写点**：
- `get_all_users` 有动态排序/分页/筛选 → 用 ORM 构建动态查询
- `admin_helpers._build_users_filter` → 返回 SQLAlchemy `where` 条件列表
- `admin_helpers._get_users_query` → 返回构建好的 `select(User)` 语句
- `_format_user_row` → 从 `User` ORM 对象提取 dict
- `authenticate_admin(session, username, password)` → 和 `verify_user` 类似
- `batch_update_users(session, user_ids, updates)` → 循环 `session.get` + `setattr`

### 5.4 改写 `db/subscriptions.py`

**12 函数，4 个直接用 DB**：
- `get_user_subscription_info(session, user_id)` → `select(User).where(User.id == user_id)`，返回订阅相关字段
- `update_user_subscription(session, user_id, data)` → `setattr` 循环
- `check_user_subscription_status(session, user_id)` → 查询 + 内部状态判断
- `decrement_user_calculations(session, user_id)` → `user.remaining_calculations -= 1`
- 其余 8 个函数是纯逻辑（不查 DB），只改签名加 `session` 参数即可

### 5.5 新建 `db/logistics_crud.py`

**完全新建**（路由 `logistics.py` 的 raw SQL 提取到此文件）：

```python
import logging
from typing import Optional

from sqlalchemy import select, func, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from models.logistics import Logistics

logger = logging.getLogger(__name__)


async def get_logistics_list(
    session: AsyncSession,
    user_id: int,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """获取用户的物流列表 + 总数。"""
    # 总数
    count_stmt = select(func.count(Logistics.id)).where(
        Logistics.user_id == user_id,
    )
    total = await session.scalar(count_stmt) or 0
    # 列表
    stmt = (
        select(Logistics)
        .where(Logistics.user_id == user_id)
        .order_by(Logistics.id.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [_logistics_to_dict(r) for r in rows], total


async def get_logistics_by_id(
    session: AsyncSession,
    logistics_id: int,
    user_id: int,
) -> Optional[dict]:
    """获取单个物流记录。"""
    stmt = select(Logistics).where(
        Logistics.id == logistics_id,
        Logistics.user_id == user_id,
    )
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    return _logistics_to_dict(row) if row else None


async def create_logistics(
    session: AsyncSession,
    user_id: int,
    data: dict,
) -> int:
    """创建物流记录，返回 ID。"""
    record = Logistics(user_id=user_id, **data)
    session.add(record)
    await session.flush()
    return record.id


async def update_logistics(
    session: AsyncSession,
    logistics_id: int,
    user_id: int,
    fields: dict,
) -> bool:
    """更新物流记录。"""
    stmt = select(Logistics).where(
        Logistics.id == logistics_id,
        Logistics.user_id == user_id,
    )
    result = await session.execute(stmt)
    record = result.scalar_one_or_none()
    if not record:
        return False
    for key, value in fields.items():
        if hasattr(record, key):
            setattr(record, key, value)
    return True


async def delete_logistics(
    session: AsyncSession,
    logistics_id: int,
    user_id: int,
) -> bool:
    """删除单个物流记录。"""
    stmt = select(Logistics).where(
        Logistics.id == logistics_id,
        Logistics.user_id == user_id,
    )
    result = await session.execute(stmt)
    record = result.scalar_one_or_none()
    if not record:
        return False
    await session.delete(record)
    return True


async def batch_delete_logistics(
    session: AsyncSession,
    ids: list[int],
    user_id: int,
) -> int:
    """批量删除物流记录，返回删除数。"""
    stmt = sa_delete(Logistics).where(
        Logistics.id.in_(ids),
        Logistics.user_id == user_id,
    )
    result = await session.execute(stmt)
    return result.rowcount


def _logistics_to_dict(record: Logistics) -> dict:
    """Logistics ORM 对象转字典。"""
    return {
        c.name: getattr(record, c.name)
        for c in Logistics.__table__.columns
    }
```

### 5.6 新建 `db/sessions_crud.py`

**完全新建**（从 `session_security.py` 等提取的 DB 操作）。包含约 10 个函数：

关键函数列表：
- `count_active_sessions(session, user_id)` → `select(func.count(...)).where(is_active == True)`
- `get_oldest_active_session(session, user_id)` → `select(...).order_by(created_at).limit(1)`
- `deactivate_session(session, session_id)` → `record.is_active = False`
- `insert_session(session, session_id, user_id, ip, ua, fingerprint, now)` → `ActiveSession(...)`
- `get_session(session, session_id)` → `session.get(ActiveSession, session_id)`
- `update_session_activity(session, session_id, now)` → `record.last_activity = now`
- `deactivate_all_sessions(session, user_id)` → `update().where()`
- `get_login_attempts(session, identifier, since)` → `select(...).where(timestamp > since)`
- `add_login_attempt(session, identifier, ip, success, ua)` → `LoginAttempt(...)`
- `get_lockout(session, identifier)` → `session.get(UserLockout, identifier)`
- `set_lockout(session, identifier, until, count)` → upsert
- `remove_lockout(session, identifier)` → delete
- `get_trusted_device(session, user_id, fingerprint)` → select with composite where
- `add_trusted_device(session, ...)` → `TrustedDevice(...)`

实施时根据 `session_security.py` 的具体 SQL 逐个实现。

### 验证（Task 5 整体）
```bash
python -m flake8 db/users.py db/products.py db/admin.py db/admin_helpers.py db/subscriptions.py db/logistics_crud.py db/sessions_crud.py
```

### Commit
```
git add db/users.py db/products.py db/admin.py db/admin_helpers.py db/subscriptions.py db/logistics_crud.py db/sessions_crud.py
git commit -m "refactor: rewrite remaining db/ modules to async ORM"
```

---

## Task 6: 改写 db/__init__.py + 删除旧文件

### 6.1 改写 `db/__init__.py`

删除所有旧导出（get_db_connection, adapt_sql 等），保留新模块导出。

```python
# db/__init__.py
# 用户相关
from db.users import (  # noqa: F401
    create_user, verify_user, update_user_password,
    delete_user, get_user_preferred_mode,
    update_user_preferred_mode, find_by_username,
    get_user_by_id, get_user_role,
)
# 产品相关
from db.products import (  # noqa: F401
    add_product, get_all_products_for_user,
    get_product_by_id, delete_product,
    batch_delete_products, update_product,
    batch_update_pricing_params,
)
# 管理员相关
from db.admin import (  # noqa: F401
    authenticate_admin, get_all_users,
    get_user_detail, update_user_subscription_admin,
    freeze_user, unfreeze_user, delete_user_admin,
    batch_update_users, get_audit_logs,
    reset_user_password,
)
# 日志相关
from db.logging_utils import (  # noqa: F401
    log_user_login, log_user_behavior,
    log_admin_action, create_alert,
)
# 统计相关
from db.statistics import (  # noqa: F401
    get_statistics_cache, set_statistics_cache,
    clear_expired_cache, clear_all_statistics_cache,
    get_dashboard_stats,
)
# 订阅相关
from db.subscriptions import (  # noqa: F401
    get_user_subscription_info,
    update_user_subscription,
    check_user_subscription_status,
    decrement_user_calculations,
)
# 计划相关
from db.plans import (  # noqa: F401
    get_plans, get_plan_by_code, get_plan_by_id,
    create_plan, update_plan, delete_plan,
    toggle_plan_active, get_plan_price,
)
# 系统配置
from db.config import (  # noqa: F401
    get_system_config, set_system_config,
    is_registration_open, get_all_config,
)
# 汇率
from db.exchange import (  # noqa: F401
    get_exchange_rate_fallback,
    update_exchange_rate_fallback,
)
# 物流 CRUD
from db.logistics_crud import (  # noqa: F401
    get_logistics_list, get_logistics_by_id,
    create_logistics, update_logistics,
    delete_logistics, batch_delete_logistics,
)
# 会话安全 CRUD
from db.sessions_crud import *  # noqa: F401, F403
# 密码（不改）
from db.password import *  # noqa: F401, F403
```

### 6.2 删除旧文件

```bash
git rm db/connection.py db/helpers.py db/_proxy.py db/schema.py
git rm db_adapter.py db_utils.py
git rm tests/test_db_adapter_critical_exceptions.py
git rm tests/test_db_adapter_connection_pool_critical.py
git rm tests/test_connection_pool_concurrency_critical.py
```

### 6.3 清理所有对旧模块的引用

全局搜索并删除以下 import：
- `from db._proxy import _db`
- `from db.helpers import adapt_sql`
- `from db.connection import get_db_connection`
- `from db_adapter import`
- `from db_utils import`
- `import db_adapter`
- `import db_utils`

### 验证
```bash
python -m flake8 db/__init__.py
python -c "import db; print('db package import OK')"
# 确认删除的文件无残留引用
python -c "import db_adapter" 2>&1 | findstr "ModuleNotFoundError"
```

### Commit
```
git add db/__init__.py
git commit -m "refactor: update db/__init__.py exports and remove legacy files"
```

---

## Task 7: 改写路由层

**通用改写规则**：
1. `def xxx(...)` → `async def xxx(...)`
2. 添加 `db: AsyncSession = Depends(get_db)` 参数
3. `from database import get_db` 添加到 import
4. `from sqlalchemy.ext.asyncio import AsyncSession` 添加到 import
5. 路由内 raw SQL → 调用 db/ 函数（`await db.xxx(session, ...)`）
6. 路由内不出现 `session.execute()`

### 7.1 改写 `api/dependencies.py`

```python
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from security.tokens import decode_token
from models.user import User

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/auth/login", auto_error=False,
)


async def get_current_user_id(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> int:
    """从 JWT 提取 user_id，验证用户存在。"""
    if not token:
        raise HTTPException(status_code=401, detail="未提供认证令牌")
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="无效的认证令牌")
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="令牌中缺少用户ID")
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    if user.is_frozen == 1:
        raise HTTPException(status_code=403, detail="账户已冻结")
    return user_id


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """返回完整 User 对象。"""
    if not token:
        raise HTTPException(status_code=401, detail="未提供认证令牌")
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="无效的认证令牌")
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="令牌中缺少用户ID")
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user


async def require_admin(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> int:
    """要求管理员权限，返回 admin user_id。"""
    user_id = await get_current_user_id(token=token, db=db)
    user = await db.get(User, user_id)
    if not user or user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user_id
```

**注意**：现有 `dependencies.py` 可能有 fallback token 逻辑，实施时需要保留其逻辑，只改 DB 访问方式。

### 7.2 改写各路由文件

每个路由文件的改写模式相同，不逐一写出完整代码。**实施指南**：

**`api/routes/logistics.py`**（最简单，全部 raw SQL）：
- 5 个 endpoint 的 SQL 全部替换为 `await db.logistics_crud.xxx(db, ...)`
- 添加 `db: AsyncSession = Depends(get_db)` 到每个 endpoint

**`api/routes/auth.py`**：
- `register` endpoint 有 1 个 raw SQL → 改为 `await db.users.create_user(db, ...)`
- `login` endpoint 改为 `await db.users.verify_user(db, ...)`

**`api/routes/products.py`**：
- 改动最小，已经调用 db/ 函数，只需加 `async` + `session` 参数

**`api/routes/admin.py`**：
- 最重的路由之一，5 个 endpoint 有 raw SQL
- 全部提取到 `db/admin.py` 的对应函数

**`api/routes/statistics.py`**：
- 最重的路由，~15 个 COUNT/SUM 查询
- 全部提取到 `db/statistics.py`

**`api/routes/settings.py`**：
- 2 个 endpoint 的 SQL → `db/config.py` 的 `get_all_config` / `set_system_config`

**`api/routes/subscriptions.py`**：
- 2 个 endpoint → `db/subscriptions.py` / `db/plans.py`

**`api/routes/orders.py`**：
- 1 个 endpoint → 新建 `db/orders.py`（如果还没有）

**`api/routes/pricing.py`**：
- 2 个函数有 raw SQL（查 products）→ `db/products.py`

### 验证
```bash
python -m flake8 api/dependencies.py api/routes/
```

### Commit
```
git add api/dependencies.py api/routes/
git commit -m "refactor: convert all routes to async with session injection"
```

---

## Task 8: 改写根模块

### 8.1 改写 `api/main.py` — 添加启动迁移

```python
# 在 lifespan 中添加 run_migrations 调用
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时：执行数据库迁移
    from database import run_migrations
    try:
        run_migrations()
    except Exception as e:
        print(f"[lifespan] 数据库迁移失败: {e}")
        raise  # 迁移失败不应启动

    # 启动时：启动自动备份服务
    try:
        from postgres_backup_service import start_backup_service
        start_backup_service()
    except Exception as e:
        print(f"[lifespan] 启动备份服务失败: {e}")

    yield

    # 关闭时：停止自动备份服务 + 关闭引擎
    try:
        from postgres_backup_service import stop_backup_service
        stop_backup_service()
    except Exception as e:
        print(f"[lifespan] 停止备份服务失败: {e}")

    from database import engine
    await engine.dispose()
```

**同时删除** `api/main.py` 中可能存在的 `from db.schema import init_db` 或 `init_db()` 调用。

### 8.2 改写 `payment_handler.py`

手动创建 session（不在请求上下文中）：

```python
from database import AsyncSessionLocal

# 所有数据库操作改为：
async def handle_payment_callback(...):
    async with AsyncSessionLocal() as session:
        try:
            # 调用 db/ 函数
            await some_db_function(session, ...)
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

### 8.3 改写 `session_security.py` + `session_security_enhanced.py`

同样使用 `AsyncSessionLocal` 手动管理 session，调用 `db/sessions_crud.py` 的函数。

### 验证
```bash
python -m flake8 api/main.py payment_handler.py session_security.py session_security_enhanced.py
```

### Commit
```
git add api/main.py payment_handler.py session_security.py session_security_enhanced.py session_security_helpers.py
git commit -m "refactor: convert root modules to async ORM with manual session management"
```

---

## Task 9: 改写测试 + conftest.py

### 9.1 改写 `conftest.py` — 测试 fixture 体系

```python
import os
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    create_async_engine, async_sessionmaker, AsyncSession,
)

from models import Base
from database import get_db

# 测试数据库 URL
TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:***REMOVED-PG-PWD***@localhost:5432/logistics",
)

test_engine = create_async_engine(TEST_DB_URL, echo=False)
TestSessionLocal = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False,
)


@pytest_asyncio.fixture
async def db_session():
    """每个测试一个事务，结束回滚。"""
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
    """注入测试 session 的 AsyncClient。"""
    from api.main import app

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test",
    ) as ac:
        yield ac
    app.dependency_overrides.clear()
```

**注意**：现有 `conftest.py` 有复杂的 backup service mocking 和 test user cleanup。实施时需要保留这些逻辑，只改 DB 连接方式。需要仔细审查现有 conftest 的每个 fixture，逐一迁移。

### 9.2 改写测试文件

**删除 3 个文件**（Task 6 已处理）：
- `test_db_adapter_critical_exceptions.py`
- `test_db_adapter_connection_pool_critical.py`
- `test_connection_pool_concurrency_critical.py`

**改写其余测试文件**（约 15-20 个文件）：

通用改写：
1. `def test_xxx(...)` → `async def test_xxx(db_session, ...)` 或 `async def test_xxx(client, ...)`
2. 直接调用 db 函数 → `await db.xxx(db_session, ...)`
3. `client.post(...)` → `await client.post(...)`（httpx AsyncClient）
4. 所有 `mock.patch` 中的 db 函数路径需要更新
5. 添加 `@pytest.mark.asyncio` 装饰器

### 9.3 更新 `pytest.ini`

确保 asyncio 模式配置正确：

```ini
[pytest]
asyncio_mode = auto
```

### 验证
```bash
python -m pytest --tb=short -x  # 先跑通
python -m pytest --tb=short     # 全部测试
python -m flake8 conftest.py tests/
```

### Commit
```
git add conftest.py tests/ pytest.ini
git commit -m "refactor: convert test suite to async with transaction rollback isolation"
```

---

## Task 10: 依赖清理 + 最终验证

### 10.1 移除 psycopg2-binary

确认零引用后：
```bash
pip uninstall psycopg2-binary -y
```

从 `requirements.txt` 中删除 `psycopg2-binary`。

### 10.2 全局验证

```bash
# Lint
python -m flake8

# 后端测试
python -m pytest --tb=short

# 前端测试
cd frontend && npx vitest run && cd ..

# 确认 Alembic
alembic current
alembic heads

# 启动测试
python -c "from api.main import app; print('App import OK')"
```

### 10.3 确认测试数量

| 指标 | 改造前 | 改造后预期 |
|------|--------|-----------|
| pytest | 988 | ~950-970 (删除 3 个 adapter 测试文件) |
| vitest | 169 | 169 (不变) |
| E2E | 260 | 260 (不变) |

### Commit
```
git add requirements.txt
git commit -m "chore: remove psycopg2-binary, finalize async ORM migration"
```

---

## Task 执行顺序总览

| Task | 内容 | 预计文件数 | 难度 | 依赖 |
|------|------|-----------|------|------|
| 1 | models/ 包 (20个模型) | 10 | 中 | 无 |
| 2 | database.py | 1 | 低 | Task 1 |
| 3 | Alembic 配置 + 初始迁移 | 4 | 中 | Task 1+2 |
| 4 | db/ 核心模块改写 (config/exchange/plans/logging/statistics) | 5 | 中 | Task 1 |
| 5 | db/ 用户/产品/管理模块 + 新建 logistics_crud/sessions_crud | 7 | 高 | Task 1 |
| 6 | db/__init__.py + 删除旧文件 | 10+ | 低 | Task 4+5 |
| 7 | 路由层改写 (dependencies + 10 个路由) | 11 | 高 | Task 4+5+6 |
| 8 | 根模块改写 (main/payment/session_security) | 4 | 中 | Task 5+6 |
| 9 | 测试改写 (conftest + 15-20 个测试文件) | 20 | 最高 | Task 1-8 |
| 10 | 依赖清理 + 最终验证 | 1 | 低 | Task 1-9 |

## Subagent 分配建议

推荐按以下方式分配 subagent：

| Subagent | Tasks | 理由 |
|----------|-------|------|
| Agent A | Task 1+2+3 | 基础设施，必须先完成 |
| Agent B | Task 4+5 (可并行) | db/ 改写，互不依赖 |
| Agent C | Task 6 | 清理，等 B 完成后 |
| Agent D | Task 7+8 | 路由+根模块，等 C 完成后 |
| Agent E | Task 9+10 | 测试，等全部完成后 |

**注意**：Task 4 和 Task 5 理论上可以并行（不同文件），但都依赖 Task 1（模型）。实际执行时建议串行以避免合并冲突。

---

## 风险点与应对

| 风险 | 影响 | 应对 |
|------|------|------|
| ORM 模型与生产库 schema 不匹配 | Alembic autogenerate 产生意外 DDL | Task 3 中仔细检查迁移文件，只允许 exchange_rates 的 CREATE |
| 路由 subscriptions.py 的列名映射 | 查询结果字段名错误 | 检查现有代码的列名映射逻辑，在 ORM 查询后保持一致 |
| 测试中 mock 路径变更 | 大量测试失败 | 全局搜索 mock.patch 中的旧路径，逐一更新 |
| asyncpg 与 psycopg2 行为差异 | 类型转换、NULL 处理可能不同 | 跑完整测试套件发现并修复 |
| session_security 的手动 session 管理 | 事务泄漏 | 严格使用 `async with AsyncSessionLocal() as session:` 模式 |
| 文件行数超限 (statistics.py) | 超过 500 行限制 | 拆分为 statistics_cache.py + statistics_queries.py |
