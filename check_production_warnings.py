#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
生产环境警告检查工具
用于诊断和解决日志中的警告问题
"""

import os
import sys
from pathlib import Path


def check_env_variables():
    """检查环境变量"""
    print("=" * 80)
    print("1. 检查环境变量配置")
    print("-" * 80)
    
    env_vars = [
        'CALLBACK_HMAC_SECRET',  # 实际使用的环境变量名
        'WECHAT_APP_ID',
        'WECHAT_MCH_ID',
        'WECHAT_API_V3_KEY',
        'DB_TYPE',
        'POSTGRES_HOST',
        'POSTGRES_DB',
    ]
    
    for var in env_vars:
        value = os.getenv(var)
        if value:
            # 对于敏感信息，只显示前4个字符
            if 'SECRET' in var or 'KEY' in var or 'PASSWORD' in var:
                display_value = f"{value[:4]}..." if len(value) > 4 else "***"
            else:
                display_value = value
            print(f"  ✅ {var}: {display_value}")
        else:
            print(f"  ❌ {var}: 未设置")
    print()


def check_env_file():
    """检查.env文件"""
    print("=" * 80)
    print("2. 检查.env文件")
    print("-" * 80)
    
    env_file = Path(".env")
    if env_file.exists():
        print(f"  ✅ .env文件存在: {env_file.absolute()}")
        
        with open(env_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查关键配置
        checks = {
            'CALLBACK_HMAC_SECRET': 'CALLBACK_HMAC_SECRET' in content,
            'WECHAT_APP_ID': 'WECHAT_APP_ID' in content,
            'WECHAT_MCH_ID': 'WECHAT_MCH_ID' in content,
            'WECHAT_API_V3_KEY': 'WECHAT_API_V3_KEY' in content,
        }
        
        for key, found in checks.items():
            if found:
                # 检查是否有值（不是空值）
                lines = [line for line in content.split('\n') 
                        if line.strip().startswith(f'{key}=')]
                if lines:
                    value = lines[0].split('=', 1)[1].strip()
                    if value and value not in ['', 'your_secret_here', 
                                                'your_app_id_here']:
                        print(f"  ✅ {key}: 已配置")
                    else:
                        print(f"  ⚠️  {key}: 已定义但值为空或默认值")
                else:
                    print(f"  ⚠️  {key}: 已定义但格式可能不正确")
            else:
                print(f"  ❌ {key}: 未在.env中配置")
    else:
        print(f"  ❌ .env文件不存在: {env_file.absolute()}")
    print()


def check_systemd_service():
    """检查systemd服务配置"""
    print("=" * 80)
    print("3. 检查systemd服务配置")
    print("-" * 80)
    
    service_file = Path("/etc/systemd/system/streamlit-app.service")
    if service_file.exists():
        print(f"  ✅ systemd服务文件存在")
        
        with open(service_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if 'CALLBACK_HMAC_SECRET' in content:
            print("  ✅ CALLBACK_HMAC_SECRET在systemd服务中已配置")
        else:
            print("  ⚠️  CALLBACK_HMAC_SECRET未在systemd服务中配置")
            print("     建议在[Service]部分添加:")
            print("     Environment=\"CALLBACK_HMAC_SECRET=your_secret\"")
            print("     或使用EnvironmentFile指向.env文件")
    else:
        print("  ⚠️  systemd服务文件不存在或无法访问")
        print(f"     预期路径: {service_file}")
    print()


def check_code_references():
    """检查代码中的配置引用"""
    print("=" * 80)
    print("4. 检查代码中的配置引用")
    print("-" * 80)
    
    files_to_check = [
        'wechat_callback_server.py',
        'hmac_utils.py',
    ]
    
    for file_path in files_to_check:
        path = Path(file_path)
        if path.exists():
            print(f"  ✅ {file_path} 存在")
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            if 'CALLBACK_HMAC_SECRET' in content:
                print(f"     ✅ 引用了 CALLBACK_HMAC_SECRET")
            if 'get_callback_secret' in content:
                print(f"     ✅ 使用了 get_callback_secret 函数")
        else:
            print(f"  ⚠️  {file_path} 不存在")
    print()


def generate_recommendations():
    """生成建议"""
    print("=" * 80)
    print("建议操作")
    print("=" * 80)
    print()
    print("要消除 '回调密钥未配置' 警告，请执行以下操作之一：")
    print()
    print("方法1: 在.env文件中添加（推荐）")
    print("  echo 'CALLBACK_HMAC_SECRET=your_secret_here' >> .env")
    print()
    print("方法2: 在systemd服务文件中添加")
    print("  sudo nano /etc/systemd/system/streamlit-app.service")
    print("  在[Service]部分添加：")
    print("  Environment=\"CALLBACK_HMAC_SECRET=your_secret_here\"")
    print("  或使用EnvironmentFile:")
    print("  EnvironmentFile=/path/to/.env")
    print("  然后执行:")
    print("  sudo systemctl daemon-reload")
    print("  sudo systemctl restart streamlit-app.service")
    print()
    print("方法3: 在启动脚本中导出环境变量")
    print("  在启动脚本中添加：")
    print("  export CALLBACK_HMAC_SECRET=your_secret_here")
    print()
    print("生成随机密钥:")
    print("  python -c \"import secrets; print(secrets.token_urlsafe(32))\")")
    print("  或")
    print("  python -c \"import secrets; print(secrets.token_hex(32))\")")
    print()
    print("注意:")
    print("  - CALLBACK_HMAC_SECRET应该是32-64位随机字符串")
    print("  - 用于验证微信支付回调的签名")
    print("  - 如果不使用微信支付回调功能，可以忽略此警告")
    print()


def main():
    """主函数"""
    print("\n" + "=" * 80)
    print("生产环境警告检查工具")
    print("=" * 80)
    print()
    
    check_env_variables()
    check_env_file()
    check_systemd_service()
    check_code_references()
    generate_recommendations()


if __name__ == "__main__":
    main()

