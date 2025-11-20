#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
查看PostgreSQL备份文件内容
"""

import subprocess
import sys
import os
import tempfile
import psycopg2
from contextlib import closing

try:
    from db_config import POSTGRES_CONFIG
except ImportError:
    print("❌ 无法加载数据库配置")
    sys.exit(1)


def list_backup_contents(backup_path):
    """列出备份文件的内容"""
    print(f"📋 备份文件内容列表: {backup_path}")
    print("-" * 80)

    cmd = [
        "pg_restore",
        "--list",
        backup_path
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"❌ 列出备份内容失败: {e}")
        print(f"错误输出: {e.stderr}")
        return False
    except FileNotFoundError:
        print("❌ pg_restore 命令未找到，请确保PostgreSQL已安装")
        return False

    return True


def inspect_backup_data(backup_path):
    """检查备份文件中的数据"""
    if not os.path.exists(backup_path):
        print(f"❌ 备份文件不存在: {backup_path}")
        return False

    print(f"\n🔍 检查备份文件: {backup_path}")
    print("=" * 80)

    # 使用临时schema而不是临时数据库
    temp_schema = f"temp_inspect_{os.getpid()}"
    dsn = (
        f"host={POSTGRES_CONFIG.get('host', 'localhost')} "
        f"port={POSTGRES_CONFIG.get('port', 5432)} "
        f"dbname={POSTGRES_CONFIG.get('database', 'postgres')} "
        f"user={POSTGRES_CONFIG.get('user', 'postgres')}"
    )
    password = POSTGRES_CONFIG.get("password", "")
    if password:
        dsn += f" password={password}"

    try:
        # 连接到数据库创建临时schema
        with closing(psycopg2.connect(dsn)) as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                # 删除临时schema（如果存在）
                cur.execute(f"DROP SCHEMA IF EXISTS {temp_schema} CASCADE")
                # 创建临时schema
                cur.execute(f"CREATE SCHEMA {temp_schema}")
                print(f"✅ 已创建临时schema: {temp_schema}")

        # 恢复备份到临时schema
        print("📥 正在恢复备份到临时schema...")
        restore_cmd = [
            "pg_restore",
            "-h", POSTGRES_CONFIG.get("host", "localhost"),
            "-p", str(POSTGRES_CONFIG.get("port", 5432)),
            "-U", POSTGRES_CONFIG.get("user", "postgres"),
            "--no-owner",
            "--no-privileges",
            "--schema", temp_schema,
            "--dbname", POSTGRES_CONFIG.get("database", "postgres"),
            backup_path
        ]

        env = os.environ.copy()
        if password:
            env["PGPASSWORD"] = password

        result = subprocess.run(
            restore_cmd,
            env=env,
            capture_output=True,
            text=True,
            check=False  # 不检查，因为可能有警告
        )

        if result.returncode != 0:
            print(f"⚠️ 恢复过程中有警告或错误:")
            if result.stderr:
                print(result.stderr)
        else:
            print("✅ 备份已恢复到临时schema")

        # 连接到数据库查询数据（使用临时schema）
        with closing(psycopg2.connect(dsn)) as conn:
            with conn.cursor() as cur:
                # 设置搜索路径到临时schema
                cur.execute(f"SET search_path TO {temp_schema}, public")

                # 1. 查询所有用户
                print("\n" + "=" * 80)
                print("👥 备份文件中的用户列表:")
                print("-" * 80)
                try:
                    cur.execute("""
                        SELECT id, username, role, email, user_type
                        FROM users
                        ORDER BY id
                    """)
                    users = cur.fetchall()
                    if users:
                        print(f"{'ID':<6} {'用户名':<20} {'角色':<10} {'邮箱':<30} {'类型':<10}")
                        print("-" * 80)
                        for user in users:
                            user_id = user[0]
                            username = user[1] or '(无)'
                            role = user[2] or '(无)'
                            email = user[3] or '(无)'
                            user_type = user[4] or '(无)'
                            print(
                                f"{user_id:<6} {username:<20} {role:<10} "
                                f"{email[:28]:<30} {user_type:<10}"
                            )
                        print(f"\n总计: {len(users)} 个用户")
                    else:
                        print("⚠️ 未找到用户")
                except psycopg2.Error as e:
                    print(f"❌ 查询用户失败: {e}")

                # 2. 查询admin用户的产品
                print("\n" + "=" * 80)
                print("📦 Admin用户的产品列表:")
                print("-" * 80)
                try:
                    # 先查找admin用户ID
                    cur.execute("""
                        SELECT id FROM users
                        WHERE role = 'admin' OR username = 'admin'
                        LIMIT 1
                    """)
                    admin_result = cur.fetchone()
                    if admin_result:
                        admin_id = admin_result[0]
                        print(f"Admin用户ID: {admin_id}\n")

                        cur.execute("""
                            SELECT id, name, unit_price, weight_g,
                                   length_cm, width_cm, height_cm
                            FROM products
                            WHERE user_id = %s
                            ORDER BY id
                        """, (admin_id,))
                        products = cur.fetchall()

                        if products:
                            print(
                                f"{'ID':<6} {'名称':<30} {'单价':<10} "
                                f"{'重量(g)':<10} {'尺寸(cm)':<20}"
                            )
                            print("-" * 80)
                            for p in products:
                                product_id = p[0]
                                name = p[1] or '(无名称)'
                                unit_price = p[2] or 0
                                weight = p[3] or 0
                                length = p[4] or 0
                                width = p[5] or 0
                                height = p[6] or 0
                                size = (
                                    f"{length}×{width}×{height}"
                                    if length and width and height
                                    else "N/A"
                                )
                                print(
                                    f"{product_id:<6} {name[:28]:<30} "
                                    f"{unit_price:<10.2f} {weight:<10} {size:<20}"
                                )
                            print(f"\n总计: {len(products)} 个产品")
                        else:
                            print("⚠️ Admin用户没有产品")
                    else:
                        print("⚠️ 未找到admin用户")
                except psycopg2.Error as e:
                    print(f"❌ 查询产品失败: {e}")

                # 3. 统计信息
                print("\n" + "=" * 80)
                print("📊 备份文件统计信息:")
                print("-" * 80)
                try:
                    # 统计各表记录数
                    tables = [
                        'users', 'products', 'logistics',
                        'plans', 'payment_orders', 'active_sessions'
                    ]
                    for table in tables:
                        try:
                            cur.execute(f"SELECT COUNT(*) FROM {table}")
                            count = cur.fetchone()[0]
                            print(f"  {table}: {count} 条记录")
                        except psycopg2.Error:
                            print(f"  {table}: 表不存在或无法访问")
                except Exception as e:
                    print(f"❌ 统计失败: {e}")

        # 清理临时schema
        print("\n" + "=" * 80)
        print("🧹 正在清理临时schema...")
        with closing(psycopg2.connect(dsn)) as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                # 删除临时schema
                cur.execute(f"DROP SCHEMA IF EXISTS {temp_schema} CASCADE")
                print(f"✅ 已删除临时schema: {temp_schema}")

    except psycopg2.Error as e:
        print(f"❌ 数据库操作失败: {e}")
        # 尝试清理临时schema
        try:
            with closing(psycopg2.connect(dsn)) as conn:
                conn.autocommit = True
                with conn.cursor() as cur:
                    cur.execute(f"DROP SCHEMA IF EXISTS {temp_schema} CASCADE")
        except Exception:
            pass
        return False
    except Exception as e:
        print(f"❌ 操作失败: {e}")
        return False

    return True


def main():
    if len(sys.argv) < 2:
        print("用法: python inspect_backup.py <备份文件路径>")
        print("示例: python inspect_backup.py backups/postgres/pre_restore_backup_20251114_190452.dump")
        sys.exit(1)

    backup_path = sys.argv[1]

    # 列出备份内容
    print("=" * 80)
    list_backup_contents(backup_path)

    # 检查备份数据
    inspect_backup_data(backup_path)

    print("\n" + "=" * 80)
    print("✅ 检查完成")


if __name__ == "__main__":
    main()

