#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库结构修复脚本
用于手动添加缺失的数据库字段
"""

import sys
import os

from db_utils import get_db_connection

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def fix_database_schema():
    """修复数据库结构"""
    print("🔧 开始修复数据库结构...")

    try:
        with get_db_connection() as (conn, cursor):
            # 检查users表结构
            cursor.execute("PRAGMA table_info(users)")
            columns = [col[1] for col in cursor.fetchall()]
            print(f"📋 当前users表字段: {columns}")

            # 需要添加的字段
            required_fields = {
                "subscription_type": "TEXT DEFAULT 'free'",
                "subscription_expires": "INTEGER",
                "user_type": "TEXT DEFAULT 'permanent'",
                "expiry_date": "TEXT",
                "remaining_calculations": "INTEGER DEFAULT -1",
                "first_login_date": "TEXT",
                "test_days_remaining": "INTEGER DEFAULT 0"
            }

            # 添加缺失的字段
            for field, definition in required_fields.items():
                if field not in columns:
                    try:
                        cursor.execute(
                            f"ALTER TABLE users ADD COLUMN {field} "
                            f"{definition}"
                        )
                        print(f"✅ 添加字段: {field}")
                    except Exception as e:
                        print(f"⚠️ 添加字段 {field} 失败: {e}")
                else:
                    print(f"📋 字段已存在: {field}")

            conn.commit()

            # 验证修复结果
            cursor.execute("PRAGMA table_info(users)")
            updated_columns = [col[1] for col in cursor.fetchall()]
            print(f"✅ 修复后users表字段: {updated_columns}")

    except Exception as e:
        print(f"❌ 修复失败: {e}")
        return 1

    print("🎉 数据库结构修复完成！")
    return 0


if __name__ == "__main__":
    sys.exit(fix_database_schema())
