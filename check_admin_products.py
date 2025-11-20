#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查admin用户的产品列表
"""

import sqlite3
import os

db_path = 'pricing_system.db'

if not os.path.exists(db_path):
    print(f"❌ 数据库文件不存在: {db_path}")
    exit(1)

print(f"✅ 数据库文件存在: {db_path}")
print(f"📊 文件大小: {os.path.getsize(db_path):,} bytes")
print()

try:
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # 查询admin用户
    c.execute("SELECT id, username, role FROM users WHERE role = 'admin'")
    admins = c.fetchall()

    if not admins:
        print("❌ 未找到admin用户")
        conn.close()
        exit(1)

    print("👤 Admin用户列表:")
    for admin in admins:
        print(f"  ID: {admin[0]}, 用户名: {admin[1]}, 角色: {admin[2]}")
    print()

    # 获取第一个admin用户的ID
    admin_id = admins[0][0]
    print(f"🔍 检查用户ID {admin_id} 的产品列表...")
    print()

    # 查询产品数量
    c.execute("SELECT COUNT(*) FROM products WHERE user_id = ?", (admin_id,))
    count = c.fetchone()[0]

    print(f"📦 Admin用户的产品数量: {count}")
    print()

    if count > 0:
        # 查询产品详情
        c.execute("""
            SELECT id, name, unit_price, weight_g, length_cm, width_cm, height_cm
            FROM products
            WHERE user_id = ?
            ORDER BY id
            LIMIT 20
        """, (admin_id,))
        products = c.fetchall()

        print("📋 产品列表（前20个）:")
        print("-" * 80)
        print(f"{'ID':<6} {'名称':<30} {'单价':<10} {'重量(g)':<10} {'尺寸(cm)':<20}")
        print("-" * 80)
        for p in products:
            product_id = p[0]
            name = p[1] or '(无名称)'
            unit_price = p[2] or 0
            weight = p[3] or 0
            length = p[4] or 0
            width = p[5] or 0
            height = p[6] or 0
            size = f"{length}×{width}×{height}" if length and width and height else "N/A"
            print(f"{product_id:<6} {name[:28]:<30} {unit_price:<10.2f} {weight:<10} {size:<20}")
        print("-" * 80)

        if count > 20:
            print(f"\n... 还有 {count - 20} 个产品未显示")
    else:
        print("⚠️  Admin用户没有产品")

    conn.close()
    print("\n✅ 检查完成")

except sqlite3.Error as e:
    print(f"❌ 数据库错误: {e}")
    exit(1)
except Exception as e:
    print(f"❌ 错误: {e}")
    exit(1)

