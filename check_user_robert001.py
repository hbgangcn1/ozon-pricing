#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查用户 robert001 的详细信息
"""

import sqlite3
import sys


def check_user(db_path):
    """检查用户 robert001 的信息"""
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()

        # 查询所有列的信息
        c.execute("PRAGMA table_info(users)")
        columns = c.fetchall()
        print("=" * 60)
        print("users 表结构：")
        for col in columns:
            print(f"  {col[1]} ({col[2]})")
        print("=" * 60)

        # 查询 robert001 用户
        c.execute(
            "SELECT * FROM users WHERE username = ?",
            ('robert001',)
        )
        user = c.fetchone()

        if not user:
            print("❌ 用户 robert001 不存在")
            return

        print("\n✅ 找到用户 robert001：")
        print("-" * 60)

        # 显示每个字段的值
        for i, col in enumerate(columns):
            col_name = col[1]
            col_value = user[i]
            print(f"  {col_name:25s} = {col_value}")

        print("-" * 60)

        # 特别检查 role 字段
        c.execute(
            "SELECT id, username, role FROM users WHERE username = ?",
            ('robert001',)
        )
        user_simple = c.fetchone()

        print("\n🔍 关键字段检查：")
        print(f"  ID: {user_simple[0]}")
        print(f"  Username: {user_simple[1]}")
        print(f"  Role: '{user_simple[2]}' (type: {type(user_simple[2])})")
        print(f"  Role == 'admin': {user_simple[2] == 'admin'}")
        print(f"  Role == 'user': {user_simple[2] == 'user'}")

        conn.close()

    except Exception as e:
        print(f"❌ 检查失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # 默认使用生产数据库
    db_path = "pricing_system.db"

    if len(sys.argv) > 1:
        db_path = sys.argv[1]

    print(f"📊 检查数据库: {db_path}\n")
    check_user(db_path)

