#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查生产数据库是否具备所需字段
在生产服务器部署前运行此脚本
"""

import sqlite3
import sys

def check_database_fields(db_path='logistics.db'):
    """检查数据库字段是否完整"""
    
    print("=" * 60)
    print("生产数据库字段检查")
    print("=" * 60)
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 检查 users 表的字段
        print("\n【检查 users 表】")
        cursor.execute('PRAGMA table_info(users)')
        existing_columns = {col[1] for col in cursor.fetchall()}
        
        required_fields = {
            'subscription_type': 'TEXT DEFAULT \'free\'',
            'subscription_expires': 'INTEGER',
            'efficiency_promo_used': 'INTEGER DEFAULT 0'
        }
        
        missing_fields = []
        for field in required_fields:
            if field in existing_columns:
                print(f"  ✅ {field} - 存在")
            else:
                print(f"  ❌ {field} - 缺失")
                missing_fields.append(field)
        
        # 检查 payment_orders 表
        print("\n【检查 payment_orders 表】")
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='payment_orders'"
        )
        table_exists = cursor.fetchone()
        
        if table_exists:
            print("  ✅ payment_orders 表存在")
            
            # 检查 duration 字段
            cursor.execute('PRAGMA table_info(payment_orders)')
            payment_cols = {col[1] for col in cursor.fetchall()}
            
            if 'duration' in payment_cols:
                print("  ✅ duration 字段存在")
            else:
                print("  ❌ duration 字段缺失")
                missing_fields.append('payment_orders.duration')
        else:
            print("  ❌ payment_orders 表不存在")
            missing_fields.append('payment_orders table')
        
        conn.close()
        
        # 总结
        print("\n" + "=" * 60)
        if missing_fields:
            print("【结论】数据库需要升级")
            print(f"缺失字段/表: {', '.join(missing_fields)}")
            print("\n【建议操作】")
            print("1. 方案A（推荐）：重启应用，init_db() 会自动添加缺失字段")
            print("2. 方案B（手动）：运行 python fix_database_fields.py")
            return False
        else:
            print("【结论】✅ 数据库字段完整，可以直接部署新代码")
            print("\n【建议操作】")
            print("直接重启应用即可，无需额外操作")
            return True
            
    except Exception as e:
        print(f"\n❌ 检查失败: {e}")
        return False


if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else 'logistics.db'
    
    import os
    if not os.path.exists(db_path):
        print(f"❌ 错误：数据库文件不存在: {db_path}")
        print(f"\n提示：")
        print(f"  1. 检查当前目录: ls -lh *.db")
        print(f"  2. 查找数据库: find . -name '*.db'")
        print(f"  3. 指定路径: python {sys.argv[0]} /path/to/your.db")
        sys.exit(1)
    
    print(f"数据库路径: {db_path}\n")
    
    result = check_database_fields(db_path)
    sys.exit(0 if result else 1)

