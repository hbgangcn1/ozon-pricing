# -*- coding: utf-8 -*-
"""
SQLite 到 PostgreSQL 数据迁移脚本
自动迁移所有数据并保持数据一致性
"""

import os
import sys
import sqlite3
import time
from typing import List, Tuple


def check_postgresql_available():
    """检查PostgreSQL驱动是否可用"""
    try:
        import psycopg2  # type: ignore[import]
        return True, psycopg2
    except ImportError:
        return False, None


def get_sqlite_connection(db_path: str):
    """获取SQLite连接"""
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"SQLite数据库文件不存在: {db_path}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def get_postgresql_connection(psycopg2):
    """获取PostgreSQL连接"""
    from db_config import POSTGRES_CONFIG

    conn = psycopg2.connect(
        host=POSTGRES_CONFIG['host'],
        port=POSTGRES_CONFIG['port'],
        database=POSTGRES_CONFIG['database'],
        user=POSTGRES_CONFIG['user'],
        password=POSTGRES_CONFIG['password']
    )
    return conn


def get_all_tables(sqlite_conn) -> List[str]:
    """获取SQLite中所有表名"""
    cursor = sqlite_conn.cursor()
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table'
        AND name NOT LIKE 'sqlite_%'
        ORDER BY name
    """)

    tables = [row[0] for row in cursor.fetchall()]
    return tables


def get_table_schema(sqlite_conn, table_name: str) -> List[Tuple]:
    """获取表结构"""
    cursor = sqlite_conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    return cursor.fetchall()


def get_table_data(sqlite_conn, table_name: str) -> List[Tuple]:
    """获取表数据"""
    cursor = sqlite_conn.cursor()
    cursor.execute(f"SELECT * FROM {table_name}")
    return cursor.fetchall()


def migrate_table(
    sqlite_conn,
    pg_conn,
    table_name: str,
    dry_run: bool = False
):
    """
    迁移单个表

    Args:
        sqlite_conn: SQLite连接
        pg_conn: PostgreSQL连接
        table_name: 表名
        dry_run: 是否为试运行模式
    """
    print(f"\n{'[试运行]' if dry_run else ''}正在迁移表: {table_name}")

    # 获取表结构
    schema = get_table_schema(sqlite_conn, table_name)
    columns = [col[1] for col in schema]

    print(f"  字段: {', '.join(columns)}")

    # 获取数据
    rows = get_table_data(sqlite_conn, table_name)
    print(f"  记录数: {len(rows)}")

    if len(rows) == 0:
        print(f"  ⚠️  表 {table_name} 为空，跳过")
        return

    if dry_run:
        print("  ✓ 试运行模式，不执行实际迁移")
        return

    # 清空PostgreSQL中的表（可选）
    pg_cursor = pg_conn.cursor()
    try:
        pg_cursor.execute(f"TRUNCATE TABLE {table_name} CASCADE")
        print("  已清空目标表")
    except Exception as e:
        print(f"  ⚠️  清空表失败: {e}，继续插入...")

    # 插入数据
    placeholders = ', '.join(['%s'] * len(columns))
    insert_sql = (
        f"INSERT INTO {table_name} ({', '.join(columns)}) "
        f"VALUES ({placeholders})"
    )

    success_count = 0
    error_count = 0

    for row in rows:
        try:
            # 转换数据类型
            values = []
            for val in row:
                if val is None:
                    values.append(None)
                else:
                    values.append(val)

            pg_cursor.execute(insert_sql, values)
            success_count += 1
        except Exception as e:
            error_count += 1
            if error_count <= 3:  # 只显示前3个错误
                print(f"  ❌ 插入失败: {e}")

    pg_conn.commit()
    print(f"  ✓ 成功: {success_count}, 失败: {error_count}")


def reset_sequences(pg_conn, table_name: str, id_column: str = 'id'):
    """重置PostgreSQL序列"""
    try:
        pg_cursor = pg_conn.cursor()

        # 查找最大ID
        pg_cursor.execute(f"SELECT MAX({id_column}) FROM {table_name}")
        result = pg_cursor.fetchone()
        max_id = result[0] if result[0] else 0

        # 重置序列
        sequence_name = f"{table_name}_{id_column}_seq"
        pg_cursor.execute(
            f"SELECT setval('{sequence_name}', {max_id + 1}, false)"
        )

        pg_conn.commit()
        print(f"  ✓ 序列已重置: {sequence_name} -> {max_id + 1}")
    except Exception as e:
        print(f"  ⚠️  重置序列失败: {e}")


def main():
    """主函数"""
    print("=" * 60)
    print("SQLite -> PostgreSQL 数据迁移工具")
    print("=" * 60)

    # 检查参数
    dry_run = '--dry-run' in sys.argv or '-n' in sys.argv
    if dry_run:
        print("\n⚠️  试运行模式：只检查不实际迁移\n")

    # 1. 检查PostgreSQL驱动
    print("\n[1/6] 检查PostgreSQL驱动...")
    available, psycopg2 = check_postgresql_available()
    if not available:
        print("❌ 错误: psycopg2未安装")
        print("请运行: pip install psycopg2-binary")
        sys.exit(1)
    print("✓ PostgreSQL驱动已安装")

    # 2. 连接SQLite
    print("\n[2/6] 连接SQLite数据库...")
    sqlite_path = os.getenv('SQLITE_DB_PATH', 'pricing_system.db')
    try:
        sqlite_conn = get_sqlite_connection(sqlite_path)
        print(f"✓ 已连接: {sqlite_path}")
    except Exception as e:
        print(f"❌ SQLite连接失败: {e}")
        sys.exit(1)

    # 3. 连接PostgreSQL
    print("\n[3/6] 连接PostgreSQL数据库...")
    try:
        pg_conn = get_postgresql_connection(psycopg2)
        print("✓ PostgreSQL连接成功")
    except Exception as e:
        print(f"❌ PostgreSQL连接失败: {e}")
        print("\n请检查:")
        print("  1. PostgreSQL是否已启动")
        print("  2. .env文件中的配置是否正确")
        print("  3. 数据库和用户是否已创建")
        sys.exit(1)

    # 4. 初始化PostgreSQL表结构
    print("\n[4/6] 初始化PostgreSQL表结构...")
    if not dry_run:
        try:
            # 临时设置环境变量为PostgreSQL
            original_db_type = os.getenv('DB_TYPE')
            os.environ['DB_TYPE'] = 'postgresql'

            from db_utils import init_db
            init_db()
            print("✓ 表结构已创建")

            # 恢复原始设置
            if original_db_type:
                os.environ['DB_TYPE'] = original_db_type
        except Exception as e:
            print(f"❌ 初始化表结构失败: {e}")
            sys.exit(1)
    else:
        print("✓ 试运行模式，跳过")

    # 5. 获取所有表
    print("\n[5/6] 获取表列表...")
    tables = get_all_tables(sqlite_conn)
    print(f"✓ 发现 {len(tables)} 个表")
    print(f"  表列表: {', '.join(tables)}")

    # 6. 迁移数据
    print("\n[6/6] 开始迁移数据...")
    print("-" * 60)

    start_time = time.time()

    # 按照依赖顺序迁移表
    migration_order = [
        'users',
        'plans',
        'products',
        'logistics',
        'payment_orders',
        'subscription_upgrade_history',
        'user_login_log',
        'user_behavior_log',
        'admin_action_log',
        'alert_records',
        'statistics_cache',
        'alert_config',
        'system_config',
    ]

    # 先迁移已知顺序的表
    for table in migration_order:
        if table in tables:
            try:
                migrate_table(sqlite_conn, pg_conn, table, dry_run)

                # 重置序列
                if not dry_run and table in [
                    'users', 'plans', 'products',
                    'logistics', 'payment_orders'
                ]:
                    reset_sequences(pg_conn, table)

            except Exception as e:
                print(f"  ❌ 迁移失败: {e}")
                import traceback
                traceback.print_exc()

    # 迁移其他表
    other_tables = [t for t in tables if t not in migration_order]
    for table in other_tables:
        try:
            migrate_table(sqlite_conn, pg_conn, table, dry_run)
        except Exception as e:
            print(f"  ❌ 迁移失败: {e}")

    elapsed = time.time() - start_time

    # 7. 完成
    print("\n" + "=" * 60)
    if dry_run:
        print("✓ 试运行完成！")
        print("\n如果检查无误，请运行以下命令执行实际迁移:")
        print("  python migrate_to_postgresql.py")
    else:
        print("✓ 数据迁移完成！")
        print(f"\n耗时: {elapsed:.2f} 秒")
        print("\n后续步骤:")
        print("  1. 修改 .env 文件: DB_TYPE=postgresql")
        print("  2. 重启应用: python app.py")
        print("  3. 测试所有功能是否正常")
        print(
            "  4. 备份SQLite数据库: "
            "cp pricing_system.db pricing_system.db.backup"
        )
    print("=" * 60)

    # 关闭连接
    sqlite_conn.close()
    pg_conn.close()


if __name__ == "__main__":
    main()
