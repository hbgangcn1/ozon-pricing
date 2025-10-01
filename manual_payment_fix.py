#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
手动修复支付订单脚本
用于手动插入支付订单记录并触发支付成功处理
"""

import sys
import os
import time

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db_utils import get_db_connection
from payment_handler import PaymentHandler

def manual_fix_payment():
    """手动修复支付订单"""
    print("🔧 开始手动修复支付订单...")
    
    # 订单信息
    order_id = "PAY_1759325041_1d4908cc"
    user_id = 2  # 您的用户ID
    amount = 100  # 1元 = 100分
    description = "物流系统效率版订阅 - 首月优惠"
    
    try:
        with get_db_connection() as (conn, cursor):
            # 检查订单是否已存在
            cursor.execute("SELECT id FROM payment_orders WHERE order_id = ?", (order_id,))
            existing_order = cursor.fetchone()
            
            if existing_order:
                print(f"📋 订单已存在: {order_id}")
            else:
                # 插入支付订单记录
                cursor.execute("""
                    INSERT INTO payment_orders
                    (order_id, user_id, amount, description, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (order_id, user_id, amount, description, 'SUCCESS', int(time.time())))
                
                conn.commit()
                print(f"✅ 支付订单记录已创建: {order_id}")
            
            # 触发支付成功处理
            print("🔧 触发支付成功处理...")
            PaymentHandler._handle_payment_success(order_id)
            
            # 验证用户订阅状态
            cursor.execute("""
                SELECT subscription_type, subscription_expires 
                FROM users 
                WHERE id = ?
            """, (user_id,))
            
            user_info = cursor.fetchone()
            if user_info:
                subscription_type, subscription_expires = user_info
                print(f"✅ 用户订阅状态: {subscription_type}")
                print(f"✅ 订阅过期时间: {subscription_expires}")
            else:
                print("❌ 无法获取用户信息")
                
    except Exception as e:
        print(f"❌ 修复失败: {e}")
        return 1
    
    print("🎉 支付订单修复完成！")
    return 0

if __name__ == "__main__":
    sys.exit(manual_fix_payment())
