#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据库升级脚本 - 添加订阅升级相关字段和表
"""

import sqlite3
import sys
import os

def upgrade_database(db_path='logistics.db'):
    """升级数据库，添加订阅升级相关字段"""
    
    print("=" * 70)
    print("数据库升级 - 订阅升级系统")
    print("=" * 70)
    
    if not os.path.exists(db_path):
        print(f"❌ 数据库文件不存在: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 1. 检查并添加 users 表的字段
        print("\n【1. 检查 users 表字段】")
        cursor.execute('PRAGMA table_info(users)')
        existing_columns = {col[1] for col in cursor.fetchall()}
        
        new_fields = {
            'billing_cycle': 'TEXT DEFAULT "month"',  # 计费周期
            'last_paid_amount': 'REAL DEFAULT 0',  # 上次支付金额
            'subscription_start': 'INTEGER',  # 订阅开始时间
        }
        
        for field_name, field_def in new_fields.items():
            if field_name not in existing_columns:
                sql = f"ALTER TABLE users ADD COLUMN {field_name} {field_def}"
                print(f"  添加字段: {field_name}")
                cursor.execute(sql)
                print(f"  ✅ {field_name}")
            else:
                print(f"  ⏭️  {field_name} 已存在")
        
        conn.commit()
        
        # 2. 创建升级历史表
        print("\n【2. 创建 subscription_upgrade_history 表】")
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='subscription_upgrade_history'
        """)
        
        if cursor.fetchone():
            print("  ⏭️  表已存在")
        else:
            cursor.execute("""
                CREATE TABLE subscription_upgrade_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    from_plan TEXT NOT NULL,
                    to_plan TEXT NOT NULL,
                    from_cycle TEXT,
                    to_cycle TEXT,
                    upgrade_time INTEGER NOT NULL,
                    remaining_value REAL DEFAULT 0,
                    difference_paid REAL DEFAULT 0,
                    target_price REAL NOT NULL,
                    payment_order_id TEXT,
                    created_at INTEGER DEFAULT (strftime('%s', 'now')),
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)
            conn.commit()
            print("  ✅ 表创建成功")
        
        # 3. 更新现有用户数据（设置默认值）
        print("\n【3. 更新现有用户数据】")
        
        # 为已有的付费用户设置 last_paid_amount
        cursor.execute("""
            SELECT id, subscription_type, efficiency_promo_used
            FROM users
            WHERE subscription_type IN ('efficiency', 'professional')
              AND last_paid_amount = 0
        """)
        
        users_to_update = cursor.fetchall()
        
        for user_id, sub_type, promo_used in users_to_update:
            # 根据套餐类型估算上次支付金额
            if sub_type == 'efficiency':
                # 效率版：如果用过首月优惠，设为14.9，否则设为1
                amount = 14.9 if promo_used else 1.0
            elif sub_type == 'professional':
                amount = 149.0
            else:
                amount = 0
            
            cursor.execute("""
                UPDATE users
                SET last_paid_amount = ?,
                    billing_cycle = 'month'
                WHERE id = ?
            """, (amount, user_id))
            
            print(f"  更新用户 {user_id}: last_paid_amount={amount}")
        
        conn.commit()
        print(f"  ✅ 更新了 {len(users_to_update)} 个用户")
        
        # 4. 验证升级
        print("\n【4. 验证升级结果】")
        cursor.execute('PRAGMA table_info(users)')
        final_columns = {col[1] for col in cursor.fetchall()}
        
        for field in new_fields.keys():
            if field in final_columns:
                print(f"  ✅ {field}")
            else:
                print(f"  ❌ {field} 缺失")
        
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='subscription_upgrade_history'
        """)
        if cursor.fetchone():
            print("  ✅ subscription_upgrade_history 表")
        else:
            print("  ❌ subscription_upgrade_history 表缺失")
        
        conn.close()
        
        print("\n" + "=" * 70)
        print("✅ 数据库升级完成")
        print("=" * 70)
        return True
        
    except Exception as e:
        print(f"\n❌ 升级失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else 'logistics.db'
    
    if not os.path.exists(db_path):
        print(f"❌ 数据库文件不存在: {db_path}")
        print(f"用法: python {sys.argv[0]} <database.db>")
        sys.exit(1)
    
    success = upgrade_database(db_path)
    sys.exit(0 if success else 1)

