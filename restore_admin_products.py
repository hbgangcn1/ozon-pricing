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

                    # 读取备份与当前库的列定义，求交集进行字段级恢复
                    cursor.execute('PRAGMA table_info(products)')
                    backup_cols = [row[1] for row in cursor.fetchall()]

                    conn_current = sqlite3.connect(db_path)
                    cursor_current = conn_current.cursor()
                    cursor_current.execute('PRAGMA table_info(products)')
                    current_cols_rows = cursor_current.fetchall()
                    current_cols = [row[1] for row in current_cols_rows]

                    # 优先使用常见字段，确保 id 与 user_id 存在
                    common_cols = [c for c in backup_cols if c in current_cols]
                    if 'id' not in common_cols and 'id' in current_cols:
                        common_cols.insert(0, 'id')
                    if ('user_id' not in common_cols and
                            'user_id' in current_cols):
                        common_cols.insert(1, 'user_id')

                    cols_sql = ', '.join(common_cols)
                    placeholders = ', '.join(['?' for _ in common_cols])

                    # 按交集列读取并恢复 admin 产品
                    cursor.execute(
                        f"SELECT {cols_sql} FROM products WHERE user_id = 1"
                    )
                    products = cursor.fetchall()

                    if products:
                        cursor_current.executemany(
                            f"INSERT OR REPLACE INTO products ({cols_sql}) "
                            f"VALUES ({placeholders})",
                            products
                        )
                        conn_current.commit()

                    conn_current.close()
                    conn.close()

                    print(f"✅ 已恢复 {len(products)} 个产品")
                    return

            except Exception as e:
                print(f"❌ 检查备份失败: {e}")

    print("❌ 未找到包含admin产品的备份")


if __name__ == "__main__":
    restore_admin_products()
