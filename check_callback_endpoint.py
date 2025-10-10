#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试微信支付回调端点
"""

import requests
import json

print("=" * 70)
print("测试微信支付回调端点")
print("=" * 70)

# 测试本地回调服务器
print("\n【1. 测试本地回调服务器 (8081端口)】")
try:
    response = requests.post(
        'http://localhost:8081/wechat/notify',
        json={"test": "data"},
        headers={'Content-Type': 'application/json'},
        timeout=5
    )
    print(f"  状态码: {response.status_code}")
    print(f"  响应: {response.text[:200]}")
    if response.status_code == 200:
        print("  ✅ 本地回调服务器正常响应")
    else:
        print("  ⚠️  响应状态码异常")
except Exception as e:
    print(f"  ❌ 请求失败: {e}")

# 测试外网回调URL
print("\n【2. 测试外网回调URL】")
try:
    response = requests.post(
        'https://www.cbprice.cn/wechat/notify',
        json={"test": "data"},
        headers={'Content-Type': 'application/json'},
        timeout=10
    )
    print(f"  状态码: {response.status_code}")
    print(f"  响应: {response.text[:200]}")
    if response.status_code == 200:
        print("  ✅ 外网回调URL正常响应")
    elif response.status_code == 502 or response.status_code == 504:
        print("  ❌ Nginx转发配置可能有问题")
    else:
        print("  ⚠️  响应状态码异常")
except Exception as e:
    print(f"  ❌ 请求失败: {e}")

# 检查回调服务器健康状态
print("\n【3. 检查回调服务器进程】")
import subprocess
result = subprocess.run(
    ['ps', 'aux'], 
    capture_output=True, 
    text=True
)
gunicorn_lines = [
    line for line in result.stdout.split('\n') 
    if 'gunicorn' in line and 'wechat' in line
]
if gunicorn_lines:
    print(f"  ✅ 找到 {len(gunicorn_lines)} 个gunicorn进程")
    for line in gunicorn_lines[:3]:
        print(f"    {line[:100]}")
else:
    print("  ❌ 未找到gunicorn回调服务器进程")

# 检查端口监听
print("\n【4. 检查端口监听】")
result = subprocess.run(
    ['ss', '-tlnp'], 
    capture_output=True, 
    text=True
)
port_8081 = [
    line for line in result.stdout.split('\n')
    if ':8081' in line
]
if port_8081:
    print("  ✅ 8081端口正在监听")
    for line in port_8081:
        print(f"    {line}")
else:
    print("  ❌ 8081端口未监听")
    print("  提示: 回调服务器可能没有启动")

print("\n" + "=" * 70)
print("【诊断建议】")
if port_8081 and gunicorn_lines:
    print("回调服务器正在运行，但可能存在以下问题：")
    print("  1. Nginx转发配置错误")
    print("  2. 微信商户后台回调URL配置错误")
    print("  3. 防火墙阻止了微信服务器的请求")
    print("  4. 回调处理代码有bug")
else:
    print("回调服务器未正常运行，请检查：")
    print("  1. gunicorn服务是否启动")
    print("  2. wechat_callback_server.py是否有语法错误")

