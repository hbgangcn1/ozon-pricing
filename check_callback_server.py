#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查微信支付回调服务器状态
"""

import os
import subprocess

print("=" * 70)
print("微信支付回调服务器状态检查")
print("=" * 70)

# 1. 检查端口监听
print("\n【1. 检查端口监听】")
print("查找监听的端口...")
os.system("netstat -tlnp 2>/dev/null | grep -E ':8501|:5000|:8000' || ss -tlnp | grep -E ':8501|:5000|:8000'")

# 2. 检查进程
print("\n【2. 检查Python进程】")
os.system("ps aux | grep -E 'streamlit|app.py|wechat_callback' | grep -v grep")

# 3. 检查 wechat_callback_server.py 是否存在
print("\n【3. 检查回调服务器文件】")
if os.path.exists('wechat_callback_server.py'):
    print("  ✅ wechat_callback_server.py 存在")
    # 检查是否在运行
    result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
    if 'wechat_callback_server.py' in result.stdout:
        print("  ✅ wechat_callback_server.py 正在运行")
    else:
        print("  ❌ wechat_callback_server.py 没有运行")
        print("  提示: 可能需要单独启动回调服务器")
else:
    print("  ⚠️  wechat_callback_server.py 不存在")

# 4. 检查 app.py 中的回调配置
print("\n【4. 检查 app.py 回调配置】")
if os.path.exists('app.py'):
    with open('app.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    if 'start_wechat_callback_server' in content:
        print("  ✅ 找到 start_wechat_callback_server 函数")
        if 'ENABLE_WECHAT_CALLBACK' in content:
            print("  ✅ 找到 ENABLE_WECHAT_CALLBACK 配置")
        else:
            print("  ⚠️  未找到 ENABLE_WECHAT_CALLBACK 配置")
    else:
        print("  ⚠️  未找到回调服务器启动函数")

# 5. 检查环境变量
print("\n【5. 检查环境变量】")
enable_callback = os.environ.get('ENABLE_WECHAT_CALLBACK', 'not set')
print(f"  ENABLE_WECHAT_CALLBACK: {enable_callback}")

# 6. 检查日志中的回调记录
print("\n【6. 检查最近的回调日志】")
print("查找 'wechat/notify' 或 '微信支付通知'...")
os.system("journalctl -u streamlit-app.service --since '1 hour ago' 2>/dev/null | grep -i 'wechat.*notify\|微信.*通知' | tail -5 || echo '  未找到回调日志'")

# 7. 建议
print("\n" + "=" * 70)
print("【诊断建议】")
print("\n如果回调服务器没有运行，可能原因：")
print("  1. 应用内置回调被禁用，但独立回调服务器未启动")
print("  2. 端口冲突")
print("  3. 配置错误")
print("\n解决方案：")
print("  1. 检查并启动独立回调服务器:")
print("     nohup python wechat_callback_server.py &")
print("  2. 或启用应用内置回调:")
print("     export ENABLE_WECHAT_CALLBACK=true")
print("     systemctl restart streamlit-app.service")

