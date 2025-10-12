#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查数据库中的孤立记录（外键指向不存在的用户）
"""

import sqlite3
import sys


def check_orphaned_records(db_path):
    """检查孤立记录"""
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()

        print("=" * 70)
        print("🔍 检查数据库中的孤立记录")
        print("=" * 70)

        issues_found = False

        # 1. 检查 active_sessions 表中的孤立记录
        print("\n1️⃣ 检查 active_sessions 表:")
        c.execute("""
            SELECT COUNT(*) FROM active_sessions
            WHERE user_id NOT IN (SELECT id FROM users)
        """)
        orphaned = c.fetchone()[0]
        if orphaned > 0:
            print(f"   ⚠️  发现 {orphaned} 条孤立的会话记录")
            issues_found = True
            
            # 显示详细信息
            c.execute("""
                SELECT id, user_id, session_token, last_activity
                FROM active_sessions
                WHERE user_id NOT IN (SELECT id FROM users)
                LIMIT 5
            """)
            for row in c.fetchall():
                print(f"      ID={row[0]}, user_id={row[1]}, "
                      f"token={row[2][:20]}...")
        else:
            print("   ✅ 没有孤立记录")

        # 2. 检查 products 表中的孤立记录
        print("\n2️⃣ 检查 products 表:")
        c.execute("""
            SELECT COUNT(*) FROM products
            WHERE user_id NOT IN (SELECT id FROM users)
        """)
        orphaned = c.fetchone()[0]
        if orphaned > 0:
            print(f"   ⚠️  发现 {orphaned} 条孤立的产品记录")
            issues_found = True
        else:
            print("   ✅ 没有孤立记录")

        # 3. 检查 logistics 表中的孤立记录
        print("\n3️⃣ 检查 logistics 表:")
        c.execute("""
            SELECT COUNT(*) FROM logistics
            WHERE user_id NOT IN (SELECT id FROM users)
        """)
        orphaned = c.fetchone()[0]
        if orphaned > 0:
            print(f"   ⚠️  发现 {orphaned} 条孤立的物流记录")
            issues_found = True
        else:
            print("   ✅ 没有孤立记录")

        # 4. 检查 payment_orders 表中的孤立记录
        print("\n4️⃣ 检查 payment_orders 表:")
        c.execute("""
            SELECT COUNT(*) FROM payment_orders
            WHERE user_id NOT IN (SELECT id FROM users)
        """)
        orphaned = c.fetchone()[0]
        if orphaned > 0:
            print(f"   ⚠️  发现 {orphaned} 条孤立的支付订单记录")
            issues_found = True
        else:
            print("   ✅ 没有孤立记录")

        # 5. 检查 subscription_upgrade_history 表（如果存在）
        try:
            print("\n5️⃣ 检查 subscription_upgrade_history 表:")
            c.execute("""
                SELECT COUNT(*) FROM subscription_upgrade_history
                WHERE user_id NOT IN (SELECT id FROM users)
            """)
            orphaned = c.fetchone()[0]
            if orphaned > 0:
                print(f"   ⚠️  发现 {orphaned} 条孤立的升级历史记录")
                issues_found = True
            else:
                print("   ✅ 没有孤立记录")
        except sqlite3.OperationalError:
            print("   ℹ️  表不存在，跳过")

        print("\n" + "=" * 70)
        if issues_found:
            print("⚠️  发现孤立记录！这些记录可能导致外键约束错误。")
            print("\n建议操作：")
            print("1. 备份数据库")
            print("2. 运行清理脚本删除孤立记录")
        else:
            print("✅ 数据库完整性检查通过！")
        print("=" * 70)

        conn.close()

    except Exception as e:
        print(f"❌ 检查失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    db_path = "pricing_system.db"

    if len(sys.argv) > 1:
        db_path = sys.argv[1]

    print(f"📊 检查数据库: {db_path}\n")
    check_orphaned_records(db_path)

