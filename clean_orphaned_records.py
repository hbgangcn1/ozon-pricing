#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
清理数据库中的孤立记录
"""

import sqlite3
import sys


def clean_orphaned_records(db_path, dry_run=True):
    """清理孤立记录
    
    Args:
        db_path: 数据库路径
        dry_run: 如果为True，只显示将要删除的记录数，不实际删除
    """
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()

        print("=" * 70)
        if dry_run:
            print("🔍 模拟运行：只检查，不删除")
        else:
            print("⚠️  实际运行：将删除孤立记录")
        print("=" * 70)

        total_deleted = 0

        # 1. 清理 active_sessions 表中的孤立记录
        print("\n1️⃣ 清理 active_sessions 表中的孤立记录:")
        c.execute("""
            SELECT COUNT(*) FROM active_sessions
            WHERE user_id NOT IN (SELECT id FROM users)
        """)
        orphaned = c.fetchone()[0]
        
        if orphaned > 0:
            print(f"   发现 {orphaned} 条孤立记录")
            if not dry_run:
                c.execute("""
                    DELETE FROM active_sessions
                    WHERE user_id NOT IN (SELECT id FROM users)
                """)
                deleted = c.rowcount
                print(f"   ✅ 已删除 {deleted} 条记录")
                total_deleted += deleted
            else:
                print(f"   [模拟] 将删除 {orphaned} 条记录")
        else:
            print("   ✅ 没有孤立记录")

        # 2. 清理 products 表中的孤立记录
        print("\n2️⃣ 清理 products 表中的孤立记录:")
        c.execute("""
            SELECT COUNT(*) FROM products
            WHERE user_id NOT IN (SELECT id FROM users)
        """)
        orphaned = c.fetchone()[0]
        
        if orphaned > 0:
            print(f"   发现 {orphaned} 条孤立记录")
            if not dry_run:
                c.execute("""
                    DELETE FROM products
                    WHERE user_id NOT IN (SELECT id FROM users)
                """)
                deleted = c.rowcount
                print(f"   ✅ 已删除 {deleted} 条记录")
                total_deleted += deleted
            else:
                print(f"   [模拟] 将删除 {orphaned} 条记录")
        else:
            print("   ✅ 没有孤立记录")

        # 3. 清理 logistics 表中的孤立记录
        print("\n3️⃣ 清理 logistics 表中的孤立记录:")
        c.execute("""
            SELECT COUNT(*) FROM logistics
            WHERE user_id NOT IN (SELECT id FROM users)
        """)
        orphaned = c.fetchone()[0]
        
        if orphaned > 0:
            print(f"   发现 {orphaned} 条孤立记录")
            if not dry_run:
                c.execute("""
                    DELETE FROM logistics
                    WHERE user_id NOT IN (SELECT id FROM users)
                """)
                deleted = c.rowcount
                print(f"   ✅ 已删除 {deleted} 条记录")
                total_deleted += deleted
            else:
                print(f"   [模拟] 将删除 {orphaned} 条记录")
        else:
            print("   ✅ 没有孤立记录")

        # 4. 清理 payment_orders 表中的孤立记录
        print("\n4️⃣ 清理 payment_orders 表中的孤立记录:")
        c.execute("""
            SELECT COUNT(*) FROM payment_orders
            WHERE user_id NOT IN (SELECT id FROM users)
        """)
        orphaned = c.fetchone()[0]
        
        if orphaned > 0:
            print(f"   发现 {orphaned} 条孤立记录")
            if not dry_run:
                c.execute("""
                    DELETE FROM payment_orders
                    WHERE user_id NOT IN (SELECT id FROM users)
                """)
                deleted = c.rowcount
                print(f"   ✅ 已删除 {deleted} 条记录")
                total_deleted += deleted
            else:
                print(f"   [模拟] 将删除 {orphaned} 条记录")
        else:
            print("   ✅ 没有孤立记录")

        # 5. 清理 subscription_upgrade_history 表（如果存在）
        try:
            print("\n5️⃣ 清理 subscription_upgrade_history 表中的孤立记录:")
            c.execute("""
                SELECT COUNT(*) FROM subscription_upgrade_history
                WHERE user_id NOT IN (SELECT id FROM users)
            """)
            orphaned = c.fetchone()[0]
            
            if orphaned > 0:
                print(f"   发现 {orphaned} 条孤立记录")
                if not dry_run:
                    c.execute("""
                        DELETE FROM subscription_upgrade_history
                        WHERE user_id NOT IN (SELECT id FROM users)
                    """)
                    deleted = c.rowcount
                    print(f"   ✅ 已删除 {deleted} 条记录")
                    total_deleted += deleted
                else:
                    print(f"   [模拟] 将删除 {orphaned} 条记录")
            else:
                print("   ✅ 没有孤立记录")
        except sqlite3.OperationalError:
            print("   ℹ️  表不存在，跳过")

        print("\n" + "=" * 70)
        if not dry_run:
            conn.commit()
            print(f"✅ 清理完成！共删除 {total_deleted} 条孤立记录")
        else:
            print("💡 这是模拟运行，没有实际删除任何记录")
            print("💡 如需实际清理，请运行: python clean_orphaned_records.py "
                  "<db_path> --execute")
        print("=" * 70)

        conn.close()

    except Exception as e:
        print(f"❌ 清理失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python clean_orphaned_records.py <db_path> [--execute]")
        print("示例: python clean_orphaned_records.py pricing_system.db")
        print("     python clean_orphaned_records.py pricing_system.db --execute")
        sys.exit(1)

    db_path = sys.argv[1]
    dry_run = "--execute" not in sys.argv

    print(f"📊 清理数据库: {db_path}\n")
    clean_orphaned_records(db_path, dry_run)

