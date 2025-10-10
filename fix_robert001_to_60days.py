#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""修正robert001为60天"""

import sqlite3
from datetime import datetime

conn = sqlite3.connect('pricing_system.db')
cursor = conn.cursor()

# 首次购买时间: 2025-10-10 22:07:55 (时间戳 1760105275)
# 正确到期时间应该是: 首次购买 + 60天
first_purchase_timestamp = 1760105275
correct_expires = first_purchase_timestamp + 60 * 24 * 3600  # 1765289275

print("=" * 70)
print("修正 robert001 订阅时间为 60天")
print("=" * 70)

# 更新
cursor.execute('''
    UPDATE users 
    SET subscription_expires = ?,
        user_type = ?,
        subscription_type = ?
    WHERE username = ?
''', (correct_expires, 'efficiency', 'efficiency', 'robert001'))

conn.commit()
print("\n✅ 数据库已更新")

# 验证
cursor.execute('''
    SELECT subscription_expires, user_type, subscription_type
    FROM users WHERE username = ?
''', ('robert001',))

result = cursor.fetchone()
expires_dt = datetime.fromtimestamp(result[0])
current_time = datetime.now().timestamp()
days_left = (result[0] - current_time) / (24 * 3600)

print("\n【验证结果】")
print(f"  用户: robert001")
print(f"  subscription_type: {result[2]}")
print(f"  subscription_expires: {result[0]}")
print(f"  user_type: {result[1]}")
print(f"  到期时间: {expires_dt.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"  剩余天数: {days_left:.1f}天")

if abs(days_left - 60) < 1:
    print("\n✅ 修复成功！剩余天数正确为60天")
else:
    print(f"\n⚠️  剩余天数不是60天，是{days_left:.1f}天")

conn.close()

