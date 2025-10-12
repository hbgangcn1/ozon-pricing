#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查用户 robert001 的所有关联数据
"""

import sqlite3
import sys


def check_user_relations(db_path, user_id):
    """检查用户的所有关联数据"""
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()

        print(f"🔍 检查用户 ID={user_id} 的关联数据\n")
        print("=" * 60)

        # 检查各个表的关联数据
        tables_to_check = [
            ("products", "user_id"),
            ("active_sessions", "user_id"),
            ("logistics", "user_id"),
            ("payment_orders", "user_id"),
            ("subscription_upgrade_history", "user_id"),
        ]

        for table_name, column_name in tables_to_check:
            try:
                c.execute(
                    f"SELECT COUNT(*) FROM {table_name} "
                    f"WHERE {column_name} = ?",
                    (user_id,)
                )
                count = c.fetchone()[0]
                status = "✅" if count == 0 else f"⚠️  {count} 条记录"
                print(f"{table_name:35s} : {status}")
            except sqlite3.OperationalError as e:
                print(f"{table_name:35s} : ❌ 表不存在或列不存在")

        print("=" * 60)

        # 检查 login_attempts 和 user_lockouts（使用 identifier）
        c.execute(
            "SELECT username FROM users WHERE id = ?", (user_id,)
        )
        user = c.fetchone()
        if user:
            username = user[0]
            print(f"\n用户名: {username}")
            print("=" * 60)

            try:
                c.execute(
                    "SELECT COUNT(*) FROM login_attempts "
                    "WHERE identifier = ?",
                    (username,)
                )
                count = c.fetchone()[0]
                status = "✅" if count == 0 else f"⚠️  {count} 条记录"
                print(f"{'login_attempts':35s} : {status}")
            except sqlite3.OperationalError:
                print(f"{'login_attempts':35s} : ❌ 表不存在")

            try:
                c.execute(
                    "SELECT COUNT(*) FROM user_lockouts "
                    "WHERE identifier = ?",
                    (username,)
                )
                count = c.fetchone()[0]
                status = "✅" if count == 0 else f"⚠️  {count} 条记录"
                print(f"{'user_lockouts':35s} : {status}")
            except sqlite3.OperationalError:
                print(f"{'user_lockouts':35s} : ❌ 表不存在")

        print("=" * 60)

        # 检查所有表的外键约束
        print("\n🔗 检查外键约束：")
        print("=" * 60)

        c.execute("PRAGMA foreign_key_list(products)")
        fks = c.fetchall()
        if fks:
            print("products 表的外键：")
            for fk in fks:
                print(f"  -> {fk}")

        c.execute("PRAGMA foreign_key_list(subscription_upgrade_history)")
        fks = c.fetchall()
        if fks:
            print("\nsubscription_upgrade_history 表的外键：")
            for fk in fks:
                print(f"  -> {fk}")

        conn.close()

    except Exception as e:
        print(f"❌ 检查失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    db_path = "pricing_system.db"
    user_id = 2453  # robert001

    if len(sys.argv) > 1:
        user_id = int(sys.argv[1])

    if len(sys.argv) > 2:
        db_path = sys.argv[2]

    print(f"📊 检查数据库: {db_path}\n")
    check_user_relations(db_path, user_id)

