#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库初始化脚本
用于手动初始化数据库，创建所需的表
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db_utils import init_db

def main():
    """初始化数据库"""
    print("🔧 开始初始化数据库...")
    
    try:
        init_db()
        print("✅ 数据库初始化完成")
    except Exception as e:
        print(f"❌ 数据库初始化失败: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
