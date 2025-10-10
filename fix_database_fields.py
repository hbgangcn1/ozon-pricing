#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""修复数据库字段问题"""

import sqlite3
import sys
import os

# 获取数据库路径
db_path = sys.argv[1] if len(sys.argv) > 1 else 'logistics.db'

# 检查数据库文件是否存在
if not os.path.exists(db_path):
    print(f"❌ 错误：数据库文件不存在: {db_path}")
    print(f"\n提示：")
    print(f"  1. 检查当前目录: ls -lh *.db")
    print(f"  2. 查找数据库: find . -name '*.db'")
    print(f"  3. 指定路径: python {sys.argv[0]} /path/to/your.db")
    sys.exit(1)

print(f"使用数据库: {db_path}\n")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 获取users表的当前字段
cursor.execute('PRAGMA table_info(users)')
existing_columns = {col[1] for col in cursor.fetchall()}

print('======== 当前users表字段 ========')
for col in sorted(existing_columns):
    print(f'  - {col}')

# 需要添加的字段
new_fields = {
    "subscription_type": "TEXT DEFAULT 'free'",
    "subscription_expires": "INTEGER",
    "efficiency_promo_used": "INTEGER DEFAULT 0"
}

print('\n======== 添加缺失字段 ========')
added_count = 0
for field_name, field_def in new_fields.items():
    if field_name not in existing_columns:
        try:
            sql = f"ALTER TABLE users ADD COLUMN {field_name} {field_def}"
            print(f'执行: {sql}')
            cursor.execute(sql)
            added_count += 1
            print(f'✅ 成功添加字段: {field_name}')
        except Exception as e:
            print(f'❌ 添加字段 {field_name} 失败: {e}')
    else:
        print(f'⏭️  字段已存在: {field_name}')

conn.commit()

# 检查payment_orders表是否存在
cursor.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name='payment_orders'"
)
if not cursor.fetchone():
    print('\n======== 创建payment_orders表 ========')
    cursor.execute('''
        CREATE TABLE payment_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT UNIQUE NOT NULL,
            user_id INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            description TEXT,
            duration TEXT,
            status TEXT DEFAULT 'PENDING',
            created_at INTEGER,
            updated_at INTEGER,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    conn.commit()
    print('✅ payment_orders表创建成功')
else:
    print('\n⏭️  payment_orders表已存在')
    # 检查是否有duration字段
    cursor.execute('PRAGMA table_info(payment_orders)')
    payment_cols = {col[1] for col in cursor.fetchall()}
    if 'duration' not in payment_cols:
        cursor.execute('ALTER TABLE payment_orders ADD COLUMN duration TEXT')
        conn.commit()
        print('✅ 添加duration字段到payment_orders表')

# 验证更新
cursor.execute('PRAGMA table_info(users)')
final_columns = {col[1] for col in cursor.fetchall()}

print('\n======== 更新后users表字段 ========')
for col in sorted(final_columns):
    marker = '🆕' if col in new_fields else '  '
    print(f'{marker} - {col}')

print(f'\n总共添加了 {added_count} 个新字段')

conn.close()

