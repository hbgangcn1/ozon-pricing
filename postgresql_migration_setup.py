# -*- coding: utf-8 -*-
"""
PostgreSQL迁移和配置脚本
将SQLite数据库迁移到PostgreSQL并优化配置
"""

import os
import sqlite3
from typing import Dict, Any

# 尝试导入PostgreSQL相关模块
try:
    import psycopg2  # noqa: F401
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    print("警告: psycopg2未安装，无法使用PostgreSQL功能")
    print("请运行: pip install psycopg2-binary")

# 加载环境变量
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    load_dotenv = None


class PostgreSQLMigrator:
    """PostgreSQL迁移器"""

    def __init__(self, sqlite_path: str, postgres_config: Dict[str, Any]):
        self.sqlite_path = sqlite_path
        self.postgres_config = postgres_config
        self.connection_pool = None

    def create_connection_pool(self):
        """创建PostgreSQL连接池"""
        if not PSYCOPG2_AVAILABLE:
            raise RuntimeError("PostgreSQL驱动未安装")

        from psycopg2 import pool
        self.connection_pool = pool.ThreadedConnectionPool(
            minconn=5,
            maxconn=20,
            host=self.postgres_config['host'],
            port=self.postgres_config['port'],
            database=self.postgres_config['database'],
            user=self.postgres_config['user'],
            password=self.postgres_config['password']
        )
        print("PostgreSQL连接池创建成功")

    def create_tables(self):
        """创建PostgreSQL表结构"""
        if not self.connection_pool:
            self.create_connection_pool()

        conn = self.connection_pool.getconn()
        cursor = conn.cursor()

        try:
            # 创建表结构
            tables_sql = [
                # 用户表
                """
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(255) UNIQUE NOT NULL,
                    password VARCHAR(255) NOT NULL,
                    role VARCHAR(50) DEFAULT 'user',
                    email VARCHAR(255) UNIQUE,
                    user_type VARCHAR(50) DEFAULT 'free',
                    remaining_calculations INTEGER DEFAULT 100,
                    remaining_days INTEGER DEFAULT 30,
                    is_frozen BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP
                )
                """,

                # 产品表
                """
                CREATE TABLE IF NOT EXISTS products (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id)
                        ON DELETE CASCADE,
                    name VARCHAR(255) NOT NULL,
                    russian_name VARCHAR(255),
                    category VARCHAR(100),
                    unit_price DECIMAL(10,2),
                    weight_g INTEGER,
                    length_mm INTEGER,
                    width_mm INTEGER,
                    height_mm INTEGER,
                    package_type VARCHAR(50),
                    has_battery BOOLEAN DEFAULT FALSE,
                    has_flammable BOOLEAN DEFAULT FALSE,
                    has_msds BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,

                # 物流表
                """
                CREATE TABLE IF NOT EXISTS logistics (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id)
                        ON DELETE CASCADE,
                    name VARCHAR(255) NOT NULL,
                    type VARCHAR(50) NOT NULL,
                    min_days INTEGER,
                    max_days INTEGER,
                    min_weight DECIMAL(10,2),
                    max_weight DECIMAL(10,2),
                    min_volume DECIMAL(10,2),
                    max_volume DECIMAL(10,2),
                    weight_factor DECIMAL(10,6),
                    volume_factor DECIMAL(10,6),
                    price_min DECIMAL(10,2),
                    battery_limit INTEGER DEFAULT 0,
                    flammable_limit INTEGER DEFAULT 0,
                    msds_required BOOLEAN DEFAULT FALSE,
                    volume_mode VARCHAR(50) DEFAULT 'none',
                    volume_coefficient DECIMAL(10,2) DEFAULT 5000,
                    fuel_surcharge_rate DECIMAL(5,4) DEFAULT 0,
                    remote_area_surcharge DECIMAL(5,4) DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,

                # 支付订单表
                """
                CREATE TABLE IF NOT EXISTS payment_orders (
                    id SERIAL PRIMARY KEY,
                    order_id VARCHAR(255) UNIQUE NOT NULL,
                    user_id INTEGER NOT NULL REFERENCES users(id)
                        ON DELETE CASCADE,
                    amount INTEGER NOT NULL,
                    description TEXT NOT NULL,
                    status VARCHAR(50) DEFAULT 'PENDING',
                    plan_code VARCHAR(50),
                    duration_days INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    paid_at TIMESTAMP
                )
                """,

                # 套餐表
                """
                CREATE TABLE IF NOT EXISTS plans (
                    id SERIAL PRIMARY KEY,
                    plan_code VARCHAR(50) UNIQUE NOT NULL,
                    plan_name VARCHAR(100) NOT NULL,
                    display_price_month DECIMAL(10,2) NOT NULL,
                    display_price_year DECIMAL(10,2) NOT NULL,
                    actual_price_month INTEGER NOT NULL,
                    actual_price_year INTEGER NOT NULL,
                    calculations_limit INTEGER DEFAULT -1,
                    logistics_limit INTEGER DEFAULT -1,
                    products_limit INTEGER DEFAULT -1,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,

                # 系统配置表
                """
                CREATE TABLE IF NOT EXISTS system_config (
                    id SERIAL PRIMARY KEY,
                    config_key VARCHAR(100) UNIQUE NOT NULL,
                    config_value TEXT NOT NULL,
                    description TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,

                # 统计缓存表
                """
                CREATE TABLE IF NOT EXISTS statistics_cache (
                    id SERIAL PRIMARY KEY,
                    cache_key VARCHAR(255) UNIQUE NOT NULL,
                    cache_data TEXT NOT NULL,
                    expires_at BIGINT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,

                # 用户行为日志表
                """
                CREATE TABLE IF NOT EXISTS user_behavior_log (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id)
                        ON DELETE CASCADE,
                    behavior_type VARCHAR(100) NOT NULL,
                    behavior_detail TEXT,
                    calculation_mode VARCHAR(50),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,

                # 管理员操作日志表
                """
                CREATE TABLE IF NOT EXISTS admin_action_log (
                    id SERIAL PRIMARY KEY,
                    admin_id INTEGER NOT NULL REFERENCES users(id)
                        ON DELETE CASCADE,
                    action_type VARCHAR(100) NOT NULL,
                    action_detail TEXT,
                    target_user_id INTEGER REFERENCES users(id)
                        ON DELETE SET NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,

                # 告警记录表
                """
                CREATE TABLE IF NOT EXISTS alert_records (
                    id SERIAL PRIMARY KEY,
                    alert_type VARCHAR(100) NOT NULL,
                    alert_level VARCHAR(50) NOT NULL,
                    description TEXT NOT NULL,
                    threshold_value DECIMAL(10,2),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            ]

            for table_sql in tables_sql:
                cursor.execute(table_sql)
                table_name = table_sql.split('CREATE TABLE IF NOT EXISTS')[1] \
                    .split('(')[0].strip()
                print(f"创建表: {table_name}")

            conn.commit()
            print("PostgreSQL表结构创建完成")

        except Exception as e:
            conn.rollback()
            print(f"创建表结构失败: {e}")
            raise
        finally:
            cursor.close()
            self.connection_pool.putconn(conn)

    def create_indexes(self):
        """创建PostgreSQL索引"""
        if not self.connection_pool:
            self.create_connection_pool()

        conn = self.connection_pool.getconn()
        cursor = conn.cursor()

        try:
            indexes = [
                # 用户表索引
                "CREATE INDEX IF NOT EXISTS idx_users_username "
                "ON users(username)",
                "CREATE INDEX IF NOT EXISTS idx_users_email "
                "ON users(email)",
                "CREATE INDEX IF NOT EXISTS idx_users_role "
                "ON users(role)",
                "CREATE INDEX IF NOT EXISTS idx_users_user_type "
                "ON users(user_type)",
                "CREATE INDEX IF NOT EXISTS idx_users_created_at "
                "ON users(created_at)",

                # 产品表索引
                "CREATE INDEX IF NOT EXISTS idx_products_user_id "
                "ON products(user_id)",
                "CREATE INDEX IF NOT EXISTS idx_products_name "
                "ON products(name)",
                "CREATE INDEX IF NOT EXISTS idx_products_weight "
                "ON products(weight_g)",
                "CREATE INDEX IF NOT EXISTS idx_products_category "
                "ON products(category)",
                "CREATE INDEX IF NOT EXISTS idx_products_user_weight "
                "ON products(user_id, weight_g)",

                # 物流表索引
                "CREATE INDEX IF NOT EXISTS idx_logistics_user_id "
                "ON logistics(user_id)",
                "CREATE INDEX IF NOT EXISTS idx_logistics_type "
                "ON logistics(type)",
                "CREATE INDEX IF NOT EXISTS idx_logistics_weight_range "
                "ON logistics(min_weight, max_weight)",
                "CREATE INDEX IF NOT EXISTS idx_logistics_volume_range "
                "ON logistics(min_volume, max_volume)",
                "CREATE INDEX IF NOT EXISTS idx_logistics_user_type_weight "
                "ON logistics(user_id, type, min_weight, max_weight)",

                # 支付订单表索引
                "CREATE INDEX IF NOT EXISTS idx_payment_orders_user_id "
                "ON payment_orders(user_id)",
                "CREATE INDEX IF NOT EXISTS idx_payment_orders_status "
                "ON payment_orders(status)",
                "CREATE INDEX IF NOT EXISTS idx_payment_orders_created_at "
                "ON payment_orders(created_at)",
                "CREATE INDEX IF NOT EXISTS idx_payment_orders_order_id "
                "ON payment_orders(order_id)",
                "CREATE INDEX IF NOT EXISTS idx_payment_orders_user_status "
                "ON payment_orders(user_id, status)",

                # 其他表索引
                "CREATE INDEX IF NOT EXISTS idx_user_behavior_log_user_id "
                "ON user_behavior_log(user_id)",
                "CREATE INDEX IF NOT EXISTS idx_user_behavior_log_type "
                "ON user_behavior_log(behavior_type)",
                "CREATE INDEX IF NOT EXISTS idx_user_behavior_log_created_at "
                "ON user_behavior_log(created_at)",
                "CREATE INDEX IF NOT EXISTS idx_admin_action_log_admin_id "
                "ON admin_action_log(admin_id)",
                "CREATE INDEX IF NOT EXISTS idx_admin_action_log_created_at "
                "ON admin_action_log(created_at)",
                "CREATE INDEX IF NOT EXISTS idx_statistics_cache_key "
                "ON statistics_cache(cache_key)",
                "CREATE INDEX IF NOT EXISTS idx_statistics_cache_expires "
                "ON statistics_cache(expires_at)",
            ]

            for index_sql in indexes:
                cursor.execute(index_sql)
                print(f"创建索引: {index_sql.split('idx_')[1].split(' ')[0]}")

            conn.commit()
            print("PostgreSQL索引创建完成")

        except Exception as e:
            conn.rollback()
            print(f"创建索引失败: {e}")
            raise
        finally:
            cursor.close()
            self.connection_pool.putconn(conn)

    def migrate_data(self):
        """迁移数据从SQLite到PostgreSQL"""
        if not self.connection_pool:
            self.create_connection_pool()

        # 连接SQLite数据库
        sqlite_conn = sqlite3.connect(self.sqlite_path)
        sqlite_conn.row_factory = sqlite3.Row

        # 连接PostgreSQL数据库
        pg_conn = self.connection_pool.getconn()
        pg_cursor = pg_conn.cursor()

        # 初始化SQLite游标
        sqlite_cursor = sqlite_conn.cursor()

        try:
            # 获取SQLite中的所有表
            sqlite_cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            tables = [row[0] for row in sqlite_cursor.fetchall()]

            print(f"发现 {len(tables)} 个表需要迁移")

            for table in tables:
                if table == 'sqlite_sequence':
                    continue

                print(f"迁移表: {table}")

                # 获取表结构
                sqlite_cursor.execute(f"PRAGMA table_info({table})")
                columns = [row[1] for row in sqlite_cursor.fetchall()]

                # 获取数据
                sqlite_cursor.execute(f"SELECT * FROM {table}")
                rows = sqlite_cursor.fetchall()

                if not rows:
                    print(f"  表 {table} 为空，跳过")
                    continue

                # 构建INSERT语句
                placeholders = ', '.join(['%s'] * len(columns))
                insert_sql = (
                    f"INSERT INTO {table} ({', '.join(columns)}) "
                    f"VALUES ({placeholders})"
                )

                # 批量插入数据
                batch_size = 1000
                for i in range(0, len(rows), batch_size):
                    batch = rows[i:i + batch_size]
                    pg_cursor.executemany(insert_sql, batch)
                    print(f"  插入 {len(batch)} 条记录")

                print(f"  表 {table} 迁移完成，共 {len(rows)} 条记录")

            pg_conn.commit()
            print("数据迁移完成")

        except Exception as e:
            pg_conn.rollback()
            print(f"数据迁移失败: {e}")
            raise
        finally:
            sqlite_cursor.close()
            sqlite_conn.close()
            pg_cursor.close()
            self.connection_pool.putconn(pg_conn)

    def optimize_postgresql(self):
        """优化PostgreSQL配置"""
        if not self.connection_pool:
            self.create_connection_pool()

        conn = self.connection_pool.getconn()
        cursor = conn.cursor()

        try:
            # PostgreSQL优化配置
            optimizations = [
                # 更新统计信息
                "ANALYZE",

                # 设置连接参数
                "SET shared_preload_libraries = 'pg_stat_statements'",
                "SET track_activity_query_size = 2048",
                "SET pg_stat_statements.track = 'all'",

                # 内存配置建议
                "-- shared_buffers = 256MB (建议设置为系统内存的25%)",
                "-- effective_cache_size = 1GB (建议设置为系统内存的75%)",
                "-- work_mem = 4MB (每个查询操作的内存)",
                "-- maintenance_work_mem = 64MB (维护操作的内存)",
            ]

            for optimization in optimizations:
                if not optimization.startswith('--'):
                    cursor.execute(optimization)
                    print(f"执行优化: {optimization}")

            conn.commit()
            print("PostgreSQL优化配置完成")

        except Exception as e:
            print(f"PostgreSQL优化失败: {e}")
        finally:
            cursor.close()
            self.connection_pool.putconn(conn)

    def close(self):
        """关闭连接池"""
        if self.connection_pool:
            self.connection_pool.closeall()
            print("PostgreSQL连接池已关闭")


def create_env_file():
    """创建PostgreSQL环境配置文件"""
    env_content = """# 数据库配置
DB_TYPE=postgresql

# PostgreSQL配置
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=logistics
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password_here
POSTGRES_OPTIONS=

# 连接池配置
DB_POOL_SIZE=20
DB_POOL_MAX=50
DB_TIMEOUT=30

# 其他配置
POLICE_FILING_MODE=false
"""

    with open('.env.postgresql', 'w', encoding='utf-8') as f:
        f.write(env_content)

    print("PostgreSQL环境配置文件已创建: .env.postgresql")
    print("请修改其中的数据库连接信息")


def main():
    """主函数"""
    print("PostgreSQL迁移和配置工具")
    print("=" * 50)

    # 检查PostgreSQL驱动
    if not PSYCOPG2_AVAILABLE:
        print("错误: 请先安装PostgreSQL驱动")
        print("运行命令: pip install psycopg2-binary")
        return

    # 创建环境配置文件
    create_env_file()

    # 配置信息
    sqlite_path = "logistics.db"
    postgres_config = {
        'host': os.getenv('POSTGRES_HOST', 'localhost'),
        'port': int(os.getenv('POSTGRES_PORT', '5432')),
        'database': os.getenv('POSTGRES_DB', 'logistics'),
        'user': os.getenv('POSTGRES_USER', 'postgres'),
        'password': os.getenv('POSTGRES_PASSWORD', ''),
    }

    # 检查SQLite数据库是否存在
    if not os.path.exists(sqlite_path):
        print(f"错误: SQLite数据库文件不存在: {sqlite_path}")
        return

    # 创建迁移器
    migrator = PostgreSQLMigrator(sqlite_path, postgres_config)

    try:
        print("1. 创建PostgreSQL表结构...")
        migrator.create_tables()

        print("2. 创建PostgreSQL索引...")
        migrator.create_indexes()

        print("3. 迁移数据...")
        migrator.migrate_data()

        print("4. 优化PostgreSQL配置...")
        migrator.optimize_postgresql()

        print("PostgreSQL迁移完成！")
        print("请将 .env.postgresql 重命名为 .env 以启用PostgreSQL")

    except Exception as e:
        print(f"迁移失败: {e}")
    finally:
        migrator.close()


if __name__ == "__main__":
    main()
