#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
手动处理已支付订单
用于修复支付成功但未处理的订单
"""

import sqlite3
import sys
import os

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def manual_process_payment(db_path, order_id):
    """手动处理支付订单"""
    
    print("=" * 70)
    print(f"手动处理支付订单: {order_id}")
    print("=" * 70)
    
    # 导入支付处理模块
    try:
        from payment_handler import PaymentHandler
        print("✅ 成功导入 PaymentHandler")
    except Exception as e:
        print(f"❌ 导入 PaymentHandler 失败: {e}")
        return
    
    # 检查订单状态
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT order_id, user_id, amount, description, duration, status
        FROM payment_orders
        WHERE order_id = ?
    """, (order_id,))
    
    order = cursor.fetchone()
    if not order:
        print(f"❌ 未找到订单: {order_id}")
        conn.close()
        return
    
    order_id, user_id, amount, desc, duration, status = order
    
    print(f"\n【订单信息】")
    print(f"  订单ID: {order_id}")
    print(f"  用户ID: {user_id}")
    print(f"  金额: ¥{amount/100:.2f}")
    print(f"  描述: {desc}")
    print(f"  时长: {duration}")
    print(f"  状态: {status}")
    
    if status != 'PAID':
        print(f"\n⚠️  订单状态不是 PAID，当前状态: {status}")
        print(f"是否仍要处理? (yes/no): ", end='')
        response = input()
        if response.lower() != 'yes':
            print("❌ 取消处理")
            conn.close()
            return
    
    conn.close()
    
    # 调用支付处理函数
    print(f"\n【开始处理支付】")
    try:
        PaymentHandler._handle_payment_success(order_id)
        print(f"\n✅ 支付处理完成")
    except Exception as e:
        print(f"\n❌ 支付处理失败: {e}")
        import traceback
        print(traceback.format_exc())
        return
    
    # 验证结果
    print(f"\n【验证处理结果】")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT subscription_type, subscription_expires, user_type
        FROM users
        WHERE id = ?
    """, (user_id,))
    
    user = cursor.fetchone()
    if user:
        sub_type, sub_expires, u_type = user
        print(f"  subscription_type: {sub_type}")
        print(f"  subscription_expires: {sub_expires}")
        print(f"  user_type: {u_type}")
        
        if sub_expires:
            from datetime import datetime
            expires_dt = datetime.fromtimestamp(sub_expires)
            current_time = datetime.now().timestamp()
            days_left = (sub_expires - current_time) / (24 * 3600)
            print(f"  到期时间: {expires_dt.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"  剩余天数: {days_left:.1f}天")
    
    conn.close()


def process_all_paid_orders(db_path):
    """处理所有已支付但可能未处理的订单"""
    
    print("=" * 70)
    print("批量处理已支付订单")
    print("=" * 70)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 查找所有PAID状态的订单
    cursor.execute("""
        SELECT order_id, user_id, amount, description, created_at
        FROM payment_orders
        WHERE status = 'PAID'
        ORDER BY created_at DESC
        LIMIT 20
    """)
    
    orders = cursor.fetchall()
    conn.close()
    
    if not orders:
        print("  未找到已支付订单")
        return
    
    print(f"\n找到 {len(orders)} 个已支付订单")
    print("\n是否处理所有订单? (yes/no): ", end='')
    response = input()
    
    if response.lower() != 'yes':
        print("❌ 取消批量处理")
        return
    
    # 导入支付处理模块
    try:
        from payment_handler import PaymentHandler
    except Exception as e:
        print(f"❌ 导入 PaymentHandler 失败: {e}")
        return
    
    # 处理每个订单
    for idx, order in enumerate(orders, 1):
        order_id = order[0]
        print(f"\n处理订单 {idx}/{len(orders)}: {order_id[:30]}...")
        
        try:
            PaymentHandler._handle_payment_success(order_id)
            print(f"  ✅ 完成")
        except Exception as e:
            print(f"  ❌ 失败: {e}")
    
    print(f"\n✅ 批量处理完成")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法:")
        print("  单个订单: python manual_process_payment.py <database.db> <order_id>")
        print("  批量处理: python manual_process_payment.py <database.db> --all")
        print("\n示例:")
        print("  python manual_process_payment.py pricing_system.db PAY_1760104313_xxx")
        print("  python manual_process_payment.py pricing_system.db --all")
        sys.exit(1)
    
    db_path = sys.argv[1]
    
    if not os.path.exists(db_path):
        print(f"❌ 数据库文件不存在: {db_path}")
        sys.exit(1)
    
    if len(sys.argv) > 2 and sys.argv[2] == '--all':
        process_all_paid_orders(db_path)
    elif len(sys.argv) > 2:
        order_id = sys.argv[2]
        manual_process_payment(db_path, order_id)
    else:
        print("❌ 请指定订单ID或使用 --all")
        sys.exit(1)

