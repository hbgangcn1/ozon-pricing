#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查 wechat_callback_server.py 代码
"""

import os

print("=" * 70)
print("检查 wechat_callback_server.py 代码")
print("=" * 70)

if not os.path.exists('wechat_callback_server.py'):
    print("❌ wechat_callback_server.py 不存在")
    exit(1)

with open('wechat_callback_server.py', 'r', encoding='utf-8') as f:
    content = f.read()

print("\n【1. 检查关键导入】")
checks = [
    ('from payment_handler import', 'PaymentHandler导入'),
    ('PaymentHandler', 'PaymentHandler使用'),
    ('process_wechat_notify', '支付通知处理'),
    ('_handle_payment_success', '支付成功处理'),
]

for keyword, desc in checks:
    if keyword in content:
        print(f"  ✅ {desc}")
    else:
        print(f"  ❌ {desc} - 未找到")

print("\n【2. 检查/wechat/notify路由】")
if '@app.route' in content and '/wechat/notify' in content:
    print("  ✅ 路由定义存在")
    
    # 提取路由函数
    lines = content.split('\n')
    in_notify_func = False
    notify_func_lines = []
    
    for i, line in enumerate(lines):
        if '/wechat/notify' in line:
            in_notify_func = True
            notify_func_lines = []
        
        if in_notify_func:
            notify_func_lines.append(f"{i+1:4d}: {line}")
            # 找到下一个函数定义就停止
            if line.strip().startswith('def ') and len(notify_func_lines) > 5:
                break
            if line.strip().startswith('@app.route') and len(notify_func_lines) > 5:
                break
    
    print("\n  【路由函数代码】")
    for line in notify_func_lines[:50]:  # 只显示前50行
        print(line)
else:
    print("  ❌ /wechat/notify 路由未定义")

print("\n【3. 检查是否调用了PaymentHandler】")
if 'PaymentHandler' in content and 'process_wechat_notify' in content:
    print("  ✅ 可能有调用")
elif 'payment_handler' in content:
    print("  ⚠️  使用了 payment_handler 变量，检查是否正确导入")
else:
    print("  ❌ 没有调用 PaymentHandler")

print("\n【4. 检查返回值】")
if 'return jsonify' in content:
    print("  ✅ 使用 jsonify 返回")
else:
    print("  ⚠️  可能使用其他方式返回")

