#!/usr/bin/env python3
"""
用户迁移脚本 - 将现有用户迁移到新的订阅系统
"""

import sqlite3
from datetime import datetime, timedelta
import os


def migrate_existing_users():
    """迁移现有用户到新的订阅系统"""

    # 连接到数据库
    db_path = os.path.join(os.path.dirname(__file__), "pricing_system.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    print("🔄 开始迁移现有用户...")

    # 获取所有用户
    c.execute("SELECT id, username, user_type, role FROM users")
    users = c.fetchall()

    for user in users:
        user_id = user['id']
        username = user['username']
        old_user_type = user['user_type']
        role = user['role']

        print(f"\n处理用户: {username}")
        print(f"  - 旧类型: {old_user_type}")
        print(f"  - 角色: {role}")

        # 根据角色和旧类型确定新类型
        if role == 'admin':
            new_user_type = 'enterprise'
            subscription_end = None  # 企业版永久
            logistics_limit = -1  # 无限
            remaining_calculations = -1  # 无限
        elif old_user_type == 'permanent':
            new_user_type = 'gratitude'  # 感谢版（永久）
            subscription_end = None
            logistics_limit = -1
            remaining_calculations = -1
        elif old_user_type == 'monthly':
            new_user_type = 'efficiency'  # 降级到效率版
            subscription_end = (
                datetime.now() + timedelta(days=30)
            ).isoformat()
            logistics_limit = 3
            remaining_calculations = -1
        else:
            new_user_type = 'free'  # 默认为免费版
            subscription_end = None
            logistics_limit = 1
            remaining_calculations = 10

        # 更新用户信息
        c.execute("""
            UPDATE users SET
                user_type = ?,
                subscription_start = ?,
                subscription_end = ?,
                remaining_calculations = ?,
                logistics_templates_limit = ?,
                is_auto_renew = ?,
                trial_used = ?
            WHERE id = ?
        """, (
            new_user_type,
            datetime.now().isoformat(),
            subscription_end,
            remaining_calculations,
            logistics_limit,
            True if new_user_type not in ['free', 'gratitude'] else False,
            False,
            user_id
        ))

        print(f"  - 新类型: {new_user_type}")
        print(f"  - 物流模板限制: {logistics_limit}")
        print(f"  - 计算次数: {remaining_calculations}")

    conn.commit()
    conn.close()
    print("\n✅ 用户迁移完成")


if __name__ == "__main__":
    migrate_existing_users()
