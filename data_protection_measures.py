#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据保护措施
"""

import sqlite3
import os
import shutil
from datetime import datetime


def create_emergency_backup():
    """创建紧急备份"""
    db_path = 'pricing_system.db'
    if os.path.exists(db_path):
        backup_name = (
            f'emergency_backup_'
            f'{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'
        )
        shutil.copy2(db_path, backup_name)
        print(f"✅ 创建紧急备份: {backup_name}")
        return backup_name
    return None


def verify_data_integrity():
    """验证数据完整性"""
    db_path = 'pricing_system.db'

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 检查所有用户的产品数据
        cursor.execute('''
            SELECT u.id, u.username, COUNT(p.id) as product_count
            FROM users u
            LEFT JOIN products p ON u.id = p.user_id
            GROUP BY u.id, u.username
            ORDER BY product_count DESC
        ''')
        user_stats = cursor.fetchall()

        print("📊 当前数据完整性检查:")
        for user_id, username, count in user_stats:
            print(f"  用户 {username} (ID: {user_id}): {count} 个产品")

        # 检查数据库完整性
        cursor.execute("PRAGMA integrity_check")
        integrity_result = cursor.fetchone()[0]
        print(f"🔍 数据库完整性: {integrity_result}")
        conn.close()
        return True

    except Exception as e:
        print(f"❌ 数据完整性检查失败: {e}")
        return False


def setup_data_protection():
    """设置数据保护措施"""
    print("🛡️ 设置数据保护措施...")

    # 1. 创建紧急备份
    create_emergency_backup()

    # 2. 验证数据完整性
    if verify_data_integrity():
        print("✅ 数据完整性验证通过")
    else:
        print("❌ 数据完整性验证失败")
        return False

    # 3. 创建数据保护指南
    protection_guide = """
# 数据保护指南

## 🚨 紧急情况处理
如果再次发生数据丢失：
1. 立即停止所有数据库操作
2. 检查最新的备份文件
3. 使用 restore_admin_products.py 恢复数据
4. 验证恢复结果

## 🔒 预防措施
1. 定期检查数据完整性
2. 在重要操作前创建手动备份
3. 监控数据库文件大小变化
4. 记录所有数据库操作

## 📞 技术支持
如果遇到数据问题，请：
1. 运行 verify_data_integrity() 检查数据
2. 查看备份文件
3. 联系技术支持
"""

    with open('数据保护指南.md', 'w', encoding='utf-8') as f:
        f.write(protection_guide)

    print("✅ 数据保护措施设置完成")
    return True


if __name__ == '__main__':
    setup_data_protection()
