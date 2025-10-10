#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
诊断续费问题
在生产服务器上运行，检查实际数据
"""

import sqlite3
import sys
from datetime import datetime

def diagnose_issue(username=None, db_path='logistics.db'):
    """诊断续费问题"""
    
    print("=" * 70)
    print("订阅续费问题诊断")
    print("=" * 70)
    print(f"数据库路径: {db_path}")
    print("=" * 70)
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 1. 检查数据库字段
        print("\n【1. 检查数据库字段】")
        cursor.execute('PRAGMA table_info(users)')
        existing_columns = {col[1] for col in cursor.fetchall()}
        
        critical_fields = ['subscription_type', 'subscription_expires', 
                          'efficiency_promo_used', 'user_type']
        
        for field in critical_fields:
            status = "✅" if field in existing_columns else "❌"
            print(f"  {status} {field}")
        
        # 2. 检查payment_orders表
        print("\n【2. 检查payment_orders表】")
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='payment_orders'"
        )
        if cursor.fetchone():
            print("  ✅ payment_orders表存在")
            cursor.execute('PRAGMA table_info(payment_orders)')
            payment_cols = {col[1] for col in cursor.fetchall()}
            if 'duration' in payment_cols:
                print("  ✅ duration字段存在")
            else:
                print("  ❌ duration字段缺失")
        else:
            print("  ❌ payment_orders表不存在")
        
        # 3. 查询用户数据
        print("\n【3. 查询用户数据】")
        if username:
            query = "SELECT id, username, user_type, subscription_type, subscription_expires, efficiency_promo_used FROM users WHERE username = ?"
            cursor.execute(query, (username,))
        else:
            # 查询最近创建的效率版用户
            query = """
                SELECT id, username, user_type, subscription_type, 
                       subscription_expires, efficiency_promo_used 
                FROM users 
                WHERE subscription_type = 'efficiency' OR user_type = 'efficiency'
                ORDER BY id DESC 
                LIMIT 5
            """
            cursor.execute(query)
        
        users = cursor.fetchall()
        if not users:
            print(f"  ⚠️  未找到用户")
            if username:
                print(f"     用户名: {username}")
            return
        
        for user in users:
            user_id, uname, utype, sub_type, sub_expires, promo = user
            print(f"\n  用户: {uname} (ID: {user_id})")
            print(f"    user_type: {utype}")
            print(f"    subscription_type: {sub_type}")
            print(f"    subscription_expires: {sub_expires}")
            print(f"    efficiency_promo_used: {promo}")
            
            if sub_expires:
                expires_dt = datetime.fromtimestamp(sub_expires)
                current_time = datetime.now().timestamp()
                days_left = (sub_expires - current_time) / (24 * 3600)
                print(f"    到期时间: {expires_dt.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"    剩余天数: {days_left:.1f}天")
            else:
                print(f"    ⚠️  subscription_expires 为空!")
            
            # 4. 查询该用户的支付订单
            print(f"\n  【支付订单记录】")
            cursor.execute("""
                SELECT order_id, amount, description, duration, status, created_at
                FROM payment_orders
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT 10
            """, (user_id,))
            
            orders = cursor.fetchall()
            if orders:
                for idx, order in enumerate(orders, 1):
                    order_id, amount, desc, duration, status, created = order
                    created_dt = datetime.fromtimestamp(created).strftime('%Y-%m-%d %H:%M:%S')
                    print(f"\n    订单{idx}: {order_id[:25]}...")
                    print(f"      金额: ¥{amount/100:.2f}")
                    print(f"      描述: {desc}")
                    print(f"      时长: {duration}")
                    print(f"      状态: {status}")
                    print(f"      创建时间: {created_dt}")
            else:
                print(f"    ⚠️  没有支付订单记录")
        
        # 5. 建议
        print("\n" + "=" * 70)
        print("【诊断建议】")
        
        if 'subscription_expires' not in existing_columns:
            print("❌ 关键问题：subscription_expires字段不存在")
            print("   解决方案：运行 python fix_database_fields.py")
        elif not users:
            print("⚠️  未找到测试用户数据")
        else:
            # 检查用户数据
            for user in users:
                user_id, uname, utype, sub_type, sub_expires, promo = user
                if not sub_expires:
                    print(f"❌ 用户 {uname}: subscription_expires为空")
                    print(f"   可能原因：")
                    print(f"   1. 支付回调未正确处理")
                    print(f"   2. payment_handler.py代码未更新")
                    print(f"   3. 数据库连接权限问题")
                elif sub_type != 'efficiency' and utype != 'efficiency':
                    print(f"⚠️  用户 {uname}: subscription_type/user_type不正确")
                    print(f"   当前: subscription_type={sub_type}, user_type={utype}")
                    print(f"   应该: efficiency")
        
        conn.close()
        
    except Exception as e:
        print(f"\n❌ 诊断失败: {e}")
        import traceback
        print(traceback.format_exc())


if __name__ == "__main__":
    # 参数解析：python diagnose_renewal_issue.py [username] [db_path]
    username = None
    db_path = 'logistics.db'
    
    if len(sys.argv) > 1:
        # 如果第一个参数是.db文件，则作为数据库路径
        if sys.argv[1].endswith('.db'):
            db_path = sys.argv[1]
        else:
            username = sys.argv[1]
            # 如果有第二个参数，作为数据库路径
            if len(sys.argv) > 2:
                db_path = sys.argv[2]
    
    # 检查数据库文件是否存在
    import os
    if not os.path.exists(db_path):
        print(f"❌ 错误：数据库文件不存在: {db_path}")
        print(f"\n提示：")
        print(f"  1. 检查当前目录: ls -lh *.db")
        print(f"  2. 查找数据库: find . -name '*.db'")
        print(f"  3. 指定数据库: python {sys.argv[0]} {username or ''} /path/to/your.db")
        print(f"\n快速查找命令:")
        print(f"  bash find_database.sh")
        sys.exit(1)
    
    if username:
        print(f"诊断用户: {username}")
    else:
        print(f"诊断最近的效率版用户")
    
    print(f"使用数据库: {db_path}\n")
    
    diagnose_issue(username, db_path)

