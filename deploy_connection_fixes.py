#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
部署数据库连接修复方案
"""

import sys
import os


def check_prerequisites():
    """检查前置条件"""
    print("检查前置条件...")

    # 检查Python版本
    python_version = sys.version_info[:2]
    min_python_version = (3, 7)
    current_version = python_version

    if current_version < min_python_version:  # noqa: unreachable
        print(
            f"⚠️  Python版本过低: "
            f"{sys.version}, 建议使用 Python 3.7+"
        )
    else:
        print(
            f"✅ Python版本: {sys.version.split()[0]}"
        )

    # 检查必要模块
    required_modules = ['sqlite3']
    missing_modules = []

    for module in required_modules:
        try:
            __import__(module)
            print(f"✅ 模块 {module} 已安装")
        except ImportError:
            missing_modules.append(module)
            print(f"❌ 模块 {module} 未安装")

    if missing_modules:
        print(
            f"⚠️  缺少以下模块: {', '.join(missing_modules)}"
        )
        return False

    return True


def backup_database():
    """备份数据库"""
    print("\n备份数据库...")

    db_path = 'pricing_system.db'
    if not os.path.exists(db_path):
        print(f"⚠️  数据库文件不存在: {db_path}")
        return False

    try:
        # 使用系统备份
        import shutil
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = f'{db_path}.backup_{timestamp}'
        shutil.copy2(db_path, backup_path)
        print(
            f"✅ 数据库备份成功: {backup_path}"
        )
        return True
    except Exception as e:
        print(
            f"❌ 数据库备份失败: {e}"
        )
        return False


def install_dependencies():
    """安装依赖"""
    print("\n检查依赖...")

    try:
        # 尝试导入
        from enhanced_connection_manager import (  # noqa: F401
            get_enhanced_db_connection
        )
        print("✅ 增强连接管理器已可用")
        return True
    except ImportError:
        print("⚠️  增强连接管理器不可用")
        return False


def test_connection():
    """测试连接"""
    print("\n测试数据库连接...")

    try:
        from enhanced_connection_manager import get_enhanced_db_connection

        with get_enhanced_db_connection() as (conn, cursor):
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            if result[0] == 1:
                print("✅ 数据库连接测试成功")
                return True
            else:
                print("❌ 数据库连接测试失败: 返回值异常")
                return False
    except Exception as e:
        print(
            f"❌ 数据库连接测试失败: {e}"
        )
        return False


def main():
    """主函数"""
    print("=" * 60)
    print("数据库连接修复部署脚本")
    print("=" * 60)

    # 1. 检查前置条件
    if not check_prerequisites():
        print("\n❌ 前置条件检查失败，请修复后重试")
        return False

    # 2. 备份数据库
    if not backup_database():
        print("\n❌ 数据库备份失败，部署已终止")
        return False

    # 3. 安装依赖
    if not install_dependencies():
        print(
            "\n⚠️  依赖检查失败，但继续部署"
        )

    # 4. 测试连接
    if not test_connection():
        print(
            "\n❌ 连接测试失败，部署已终止"
        )
        return False

    print("\n" + "=" * 60)
    print("✅ 数据库连接修复部署成功")
    print("=" * 60)

    # 提供使用说明
    print("\n使用说明:")
    print(
        "1. 在代码中使用 get_enhanced_db_connection() 获取连接"
    )
    print(
        "2. 定期运行 check_connection_fixes.py 检测连接泄漏"
    )
    print(
        "3. 查看 database_health_checker.py 监控数据库健康"
    )

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
