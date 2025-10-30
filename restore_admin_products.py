#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
恢复admin用户的产品
"""

import sqlite3
import os
import glob


def restore_admin_products():
    """恢复admin用户的产品"""
    print("🔧 恢复admin用户的产品...")

    db_path = 'pricing_system.db'
    backup_dir = 'backups'

    # 查找最新的备份
    if os.path.exists(backup_dir):
        backup_files = glob.glob(os.path.join(backup_dir, '*.db'))
        backup_files.sort(key=os.path.getmtime, reverse=True)

        print(f"找到 {len(backup_files)} 个备份文件")

        # 查找包含admin产品的备份
        for backup_file in backup_files:
            try:
                conn = sqlite3.connect(backup_file)
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT COUNT(*) FROM products WHERE user_id = 1'
                )
                admin_products_count = cursor.fetchone()[0]

                if admin_products_count > 0:
                    print(
                        f"✅ 在备份中找到admin产品: "
                        f"{os.path.basename(backup_file)}"
                    )

                    # 获取admin用户的产品
                    cursor.execute(
                        'SELECT * FROM products WHERE user_id = 1'
                    )
                    products = cursor.fetchall()

                    conn.close()

                    # 恢复产品到当前数据库
                    conn_current = sqlite3.connect(db_path)
                    cursor_current = conn_current.cursor()

                    for product in products:
                        cursor_current.execute('''
                            INSERT OR REPLACE INTO products (
                                id, user_id, name, category, weight_g,
                                unit_price, description
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', product[:7])

                    conn_current.commit()
                    conn_current.close()

                    print(f"✅ 已恢复 {len(products)} 个产品")
                    return

            except Exception as e:
                print(f"❌ 检查备份失败: {e}")

    print("❌ 未找到包含admin产品的备份")


if __name__ == "__main__":
    restore_admin_products()
