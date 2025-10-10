#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查生产代码版本和关键代码是否存在
"""

import os
import sys

def check_code_version():
    """检查代码版本"""
    
    print("=" * 70)
    print("代码版本检查")
    print("=" * 70)
    
    # 1. 检查git版本
    print("\n【1. Git版本】")
    os.system("git log -1 --oneline")
    
    # 2. 检查payment_handler.py中的关键代码
    print("\n【2. payment_handler.py 关键代码检查】")
    
    if not os.path.exists('payment_handler.py'):
        print("  ❌ payment_handler.py 文件不存在")
        return
    
    with open('payment_handler.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查关键字
    checks = [
        ('续费模式', '续费逻辑标记'),
        ('原到期时间', '显示原到期时间'),
        ('新到期时间', '显示新到期时间'),
        ('subscription_type, subscription_expires, user_type', '查询三个字段'),
        ('subscription_type = ?,\n                            subscription_expires = ?,\n                            user_type = ?', '更新三个字段'),
    ]
    
    for keyword, desc in checks:
        if keyword in content:
            print(f"  ✅ {desc}")
        else:
            print(f"  ❌ {desc} - 未找到")
    
    # 3. 检查_handle_payment_success函数
    print("\n【3. _handle_payment_success 函数检查】")
    
    if '_handle_payment_success' in content:
        print("  ✅ 函数存在")
        
        # 提取函数内容
        start_idx = content.find('def _handle_payment_success')
        if start_idx != -1:
            # 找到函数结束（下一个同级函数或文件结束）
            end_idx = content.find('\ndef ', start_idx + 10)
            if end_idx == -1:
                end_idx = len(content)
            
            func_content = content[start_idx:end_idx]
            
            # 检查关键逻辑
            if 'current_expires and current_expires > current_time' in func_content:
                print("  ✅ 续费判断逻辑存在")
            else:
                print("  ❌ 续费判断逻辑缺失")
            
            if 'new_expires = current_expires + days * 24 * 3600' in func_content:
                print("  ✅ 时间累加逻辑存在")
            else:
                print("  ❌ 时间累加逻辑缺失")
            
            if 'user_type = ?' in func_content:
                print("  ✅ user_type更新存在")
            else:
                print("  ❌ user_type更新缺失")
    else:
        print("  ❌ 函数不存在")
    
    # 4. 检查文件最后修改时间
    print("\n【4. 文件修改时间】")
    stat = os.stat('payment_handler.py')
    import time
    mod_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stat.st_mtime))
    print(f"  payment_handler.py: {mod_time}")
    
    # 5. 显示函数行号
    print("\n【5. 关键代码位置】")
    lines = content.split('\n')
    for idx, line in enumerate(lines, 1):
        if 'def _handle_payment_success' in line:
            print(f"  _handle_payment_success 函数: 第 {idx} 行")
        if '续费模式：' in line and 'print' in line:
            print(f"  续费模式日志: 第 {idx} 行")


if __name__ == "__main__":
    check_code_version()

