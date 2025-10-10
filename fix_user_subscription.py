#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
手动修复用户订阅时间
用于修正续费时间未正确累加的问题
"""

import sqlite3
import sys
from datetime import datetime

def fix_user_subscription(db_path, username):
    """修复用户订阅时间"""
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("=" * 70)
    print(f"修复用户订阅时间: {username}")
    print("=" * 70)
    
    # 1. 获取用户信息
    cursor.execute("""
        SELECT id, username, subscription_type, subscription_expires
        FROM users
        WHERE username = ?
    """, (username,))
    
    user = cursor.fetchone()
    if not user:
        print(f"❌ 未找到用户: {username}")
        conn.close()
        return
    
    user_id, uname, sub_type, current_expires = user
    
    print(f"\n【当前用户信息】")
    print(f"  ID: {user_id}")
    print(f"  用户名: {uname}")
    print(f"  订阅类型: {sub_type}")
    print(f"  当前到期时间戳: {current_expires}")
    
    if current_expires:
        current_dt = datetime.fromtimestamp(current_expires)
        print(f"  当前到期时间: {current_dt.strftime('%Y-%m-%d %H:%M:%S')}")
        current_time = datetime.now().timestamp()
        current_days = (current_expires - current_time) / (24 * 3600)
        print(f"  当前剩余天数: {current_days:.1f}天")
    
    # 2. 获取支付订单
    cursor.execute("""
        SELECT order_id, amount, description, duration, status, created_at
        FROM payment_orders
        WHERE user_id = ? AND status = 'PAID'
        ORDER BY created_at ASC
    """, (user_id,))
    
    orders = cursor.fetchall()
    
    print(f"\n【支付订单】共 {len(orders)} 个")
    
    if not orders:
        print("  ❌ 没有支付订单")
        conn.close()
        return
    
    # 3. 计算正确的到期时间
    print(f"\n【计算正确的到期时间】")
    
    total_days = 0
    for idx, order in enumerate(orders, 1):
        order_id, amount, desc, duration, status, created = order
        created_dt = datetime.fromtimestamp(created)
        
        # 根据duration计算天数
        if duration == "1_month" or duration == "month":
            days = 30
        elif duration == "1_year" or duration == "year":
            days = 365
        else:
            days = 30  # 默认
        
        total_days += days
        
        print(f"  订单{idx}: {order_id[:25]}...")
        print(f"    创建时间: {created_dt.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"    描述: {desc}")
        print(f"    时长: {duration} ({days}天)")
        print(f"    累计天数: {total_days}天")
    
    # 4. 计算新的到期时间
    # 从第一个订单创建时间开始计算
    first_order_time = orders[0][5]
    new_expires = first_order_time + total_days * 24 * 3600
    new_expires_dt = datetime.fromtimestamp(new_expires)
    
    print(f"\n【修复方案】")
    print(f"  基准时间: {datetime.fromtimestamp(first_order_time).strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  总天数: {total_days}天")
    print(f"  新到期时间: {new_expires_dt.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  新到期时间戳: {new_expires}")
    
    current_time = datetime.now().timestamp()
    new_days = (new_expires - current_time) / (24 * 3600)
    print(f"  新剩余天数: {new_days:.1f}天")
    
    # 5. 确认修复
    print(f"\n【确认修复】")
    response = input(f"是否更新用户 {username} 的订阅到期时间? (yes/no): ")
    
    if response.lower() != 'yes':
        print("❌ 取消修复")
        conn.close()
        return
    
    # 6. 执行更新
    cursor.execute("""
        UPDATE users
        SET subscription_expires = ?,
            subscription_type = ?,
            user_type = ?
        WHERE id = ?
    """, (new_expires, 'efficiency', 'efficiency', user_id))
    
    conn.commit()
    
    # 7. 验证更新
    cursor.execute("""
        SELECT subscription_type, subscription_expires, user_type
        FROM users
        WHERE id = ?
    """, (user_id,))
    
    verify = cursor.fetchone()
    verify_expires = verify[1]
    verify_dt = datetime.fromtimestamp(verify_expires)
    verify_days = (verify_expires - current_time) / (24 * 3600)
    
    print(f"\n【更新完成】")
    print(f"  ✅ subscription_type: {verify[0]}")
    print(f"  ✅ subscription_expires: {verify_expires}")
    print(f"  ✅ user_type: {verify[2]}")
    print(f"  ✅ 到期时间: {verify_dt.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  ✅ 剩余天数: {verify_days:.1f}天")
    
    conn.close()
    print(f"\n✅ 用户 {username} 的订阅时间已修复！")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法: python fix_user_subscription.py <database.db> <username>")
        print("示例: python fix_user_subscription.py pricing_system.db robert001")
        sys.exit(1)
    
    db_path = sys.argv[1]
    username = sys.argv[2]
    
    import os
    if not os.path.exists(db_path):
        print(f"❌ 数据库文件不存在: {db_path}")
        sys.exit(1)
    
    fix_user_subscription(db_path, username)

