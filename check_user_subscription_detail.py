#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查用户订阅详情和升级历史
"""

import sqlite3
import time
from datetime import datetime


def check_user_subscription(username='robert001'):
    """检查指定用户的订阅详情"""
    db_path = 'logistics.db'
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 获取用户基本信息
        cursor.execute("""
            SELECT id, username, subscription_type, user_type,
                   subscription_expires, billing_cycle,
                   last_paid_amount, subscription_start,
                   efficiency_promo_used
            FROM users
            WHERE username = ?
        """, (username,))
        
        user = cursor.fetchone()
        if not user:
            print(f"❌ 未找到用户: {username}")
            return
        
        (user_id, username, sub_type, user_type, expires, cycle,
         last_paid, sub_start, promo_used) = user
        
        print(f"\n{'='*60}")
        print(f"👤 用户信息: {username} (ID: {user_id})")
        print(f"{'='*60}")
        print(f"订阅类型 (subscription_type): {sub_type}")
        print(f"用户类型 (user_type): {user_type}")
        print(f"计费周期 (billing_cycle): {cycle}")
        print(f"上次支付金额 (last_paid_amount): ¥{last_paid or 0:.2f}")
        print(f"首月优惠已用 (efficiency_promo_used): {promo_used}")
        
        # 到期时间
        if expires:
            expires_dt = datetime.fromtimestamp(expires)
            current_time = time.time()
            remaining_seconds = expires - current_time
            remaining_days = remaining_seconds / (24 * 3600)
            
            print(f"\n⏰ 订阅时间:")
            if sub_start:
                start_dt = datetime.fromtimestamp(sub_start)
                print(f"  开始时间: {start_dt.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"  到期时间: {expires_dt.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"  剩余天数: {remaining_days:.1f} 天")
        else:
            print(f"\n⏰ 到期时间: 无（免费版或未设置）")
        
        # 查询升级历史
        cursor.execute("""
            SELECT from_plan, to_plan, from_cycle, to_cycle,
                   upgrade_time, remaining_value, difference_paid,
                   target_price, payment_order_id
            FROM subscription_upgrade_history
            WHERE user_id = ?
            ORDER BY upgrade_time DESC
            LIMIT 10
        """, (user_id,))
        
        history = cursor.fetchall()
        if history:
            print(f"\n📜 最近升级历史:")
            print(f"{'='*60}")
            for record in history:
                (from_plan, to_plan, from_cycle, to_cycle,
                 upgrade_time, remain_val, diff_paid,
                 target_price, order_id) = record
                
                upgrade_dt = datetime.fromtimestamp(upgrade_time)
                print(f"\n升级时间: {upgrade_dt.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"  {from_plan}({from_cycle}) → {to_plan}({to_cycle})")
                print(f"  目标价格: ¥{target_price:.2f}")
                print(f"  剩余价值: ¥{remain_val:.2f}")
                print(f"  实付差价: ¥{diff_paid:.2f}")
                print(f"  订单ID: {order_id}")
        else:
            print(f"\n📜 无升级历史记录")
        
        # 查询最近的支付订单
        cursor.execute("""
            SELECT order_id, amount, description, duration,
                   created_at, status, is_upgrade,
                   upgrade_from_plan, upgrade_to_plan
            FROM payment_orders
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT 5
        """, (user_id,))
        
        orders = cursor.fetchall()
        if orders:
            print(f"\n💳 最近支付订单:")
            print(f"{'='*60}")
            for order in orders:
                (order_id, amount, desc, duration, created,
                 status, is_upgrade, from_plan, to_plan) = order
                
                created_dt = datetime.fromtimestamp(created)
                print(f"\n订单ID: {order_id}")
                print(f"  时间: {created_dt.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"  金额: ¥{amount / 100:.2f}")
                print(f"  描述: {desc}")
                print(f"  时长: {duration}")
                print(f"  状态: {status}")
                if is_upgrade:
                    print(f"  升级: {from_plan} → {to_plan}")
        else:
            print(f"\n💳 无支付订单记录")
        
        conn.close()
        print(f"\n{'='*60}\n")
        
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import sys
    username = sys.argv[1] if len(sys.argv) > 1 else 'robert001'
    check_user_subscription(username)

