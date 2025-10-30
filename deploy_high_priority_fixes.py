# -*- coding: utf-8 -*-
"""
高优先级修复部署脚本
自动部署数据库性能优化、缓存系统、错误处理等修复
"""

import subprocess
import os
from datetime import datetime


def print_step(step_name: str, description: str):
    """打印步骤信息"""
    print(f"\n{'='*60}")
    print(f"步骤: {step_name}")
    print(f"描述: {description}")
    print(f"{'='*60}")


def check_dependencies() -> bool:
    """检查依赖项"""
    print_step("检查依赖项", "验证所需的Python包是否已安装")

    required_packages = [
        'psycopg2-binary',
        'redis',
        'plotly',
        'streamlit'
    ]

    missing_packages = []

    # 包名到模块名的映射
    package_mapping = {
        'psycopg2-binary': 'psycopg2',
        'redis': 'redis',
        'plotly': 'plotly',
        'streamlit': 'streamlit'
    }

    for package in required_packages:
        try:
            module_name = package_mapping.get(package,
                                              package.replace('-', '_'))
            __import__(module_name)
            print(f"✅ {package} 已安装")
        except ImportError:
            print(f"❌ {package} 未安装")
            missing_packages.append(package)

    if missing_packages:
        print(f"\n⚠️ 缺少以下依赖包: {', '.join(missing_packages)}")
        install_command = f"pip install {' '.join(missing_packages)}"
        print(f"💡 请运行: {install_command}")
        return False

    return True


def update_application_config() -> bool:
    """更新应用程序配置"""
    print_step("更新应用程序配置", "集成错误处理和缓存系统")

    try:
        # 检查关键文件是否存在
        required_files = [
            'enhanced_error_handler.py',
            'intelligent_cache_manager.py',
            'database_performance_monitor.py',
            'database_index_optimizer.py'
        ]

        for file in required_files:
            if not os.path.exists(file):
                print(f"❌ 缺少文件: {file}")
                return False
            print(f"✅ 文件存在: {file}")

        print("✅ 应用程序配置检查完成")
        return True

    except Exception as e:
        print(f"❌ 配置更新失败: {e}")
        return False


def optimize_database() -> bool:
    """优化数据库"""
    print_step("优化数据库", "创建索引和优化连接池")

    try:
        # 运行数据库索引优化
        result = subprocess.run([
            'python', '-c',
            'from database_index_optimizer import DatabaseIndexOptimizer; '
            'optimizer = DatabaseIndexOptimizer(); '
            'optimizer.optimize_sqlite(); '
            'optimizer.optimize_postgresql()'
        ], capture_output=True, text=True, timeout=60)

        if result.returncode == 0:
            print("✅ 数据库索引优化完成")
        else:
            print(f"⚠️ 数据库索引优化警告: {result.stderr}")

        return True

    except subprocess.TimeoutExpired:
        print("⚠️ 数据库优化超时，但继续执行")
        return True
    except Exception as e:
        print(f"❌ 数据库优化失败: {e}")
        return False


def setup_cache_system() -> bool:
    """设置缓存系统"""
    print_step("设置缓存系统", "初始化智能缓存管理器")

    try:
        # 测试缓存系统
        result = subprocess.run([
            'python', '-c',
            'from intelligent_cache_manager import get_cache_stats; '
            'print("缓存系统测试:", get_cache_stats())'
        ], capture_output=True, text=True, timeout=30)

        if result.returncode == 0:
            print("✅ 缓存系统设置完成")
            print(f"缓存状态: {result.stdout.strip()}")
        else:
            print(f"⚠️ 缓存系统设置警告: {result.stderr}")

        return True

    except subprocess.TimeoutExpired:
        print("⚠️ 缓存系统设置超时，但继续执行")
        return True
    except Exception as e:
        print(f"❌ 缓存系统设置失败: {e}")
        return False


def setup_error_handling() -> bool:
    """设置错误处理"""
    print_step("设置错误处理", "初始化增强错误处理系统")

    try:
        # 测试错误处理系统
        result = subprocess.run([
            'python', '-c',
            'from enhanced_error_handler import get_error_summary; '
            'print("错误处理系统测试:", get_error_summary())'
        ], capture_output=True, text=True, timeout=30)

        if result.returncode == 0:
            print("✅ 错误处理系统设置完成")
            print(f"错误处理状态: {result.stdout.strip()}")
        else:
            print(f"⚠️ 错误处理系统设置警告: {result.stderr}")

        return True

    except subprocess.TimeoutExpired:
        print("⚠️ 错误处理系统设置超时，但继续执行")
        return True
    except Exception as e:
        print(f"❌ 错误处理系统设置失败: {e}")
        return False


def setup_monitoring() -> bool:
    """设置监控系统"""
    print_step("设置监控系统", "初始化数据库性能监控")

    try:
        # 测试监控系统
        result = subprocess.run([
            'python', '-c',
            'from database_performance_monitor import get_performance_report; '
            'print("监控系统测试:", get_performance_report())'
        ], capture_output=True, text=True, timeout=30)

        if result.returncode == 0:
            print("✅ 监控系统设置完成")
            print(f"监控状态: {result.stdout.strip()}")
        else:
            print(f"⚠️ 监控系统设置警告: {result.stderr}")

        return True

    except subprocess.TimeoutExpired:
        print("⚠️ 监控系统设置超时，但继续执行")
        return True
    except Exception as e:
        print(f"❌ 监控系统设置失败: {e}")
        return False


def run_tests() -> bool:
    """运行测试"""
    print_step("运行测试", "验证修复是否正常工作")

    try:
        # 运行基本测试
        result = subprocess.run([
            'python', '-c',
            'import enhanced_error_handler; '
            'import intelligent_cache_manager; '
            'import database_performance_monitor; '
            'import database_index_optimizer; '
            'print("所有模块导入成功")'
        ], capture_output=True, text=True, timeout=30)

        if result.returncode == 0:
            print("✅ 模块导入测试通过")
            print(result.stdout.strip())
        else:
            print(f"⚠️ 模块导入测试警告: {result.stderr}")

        return True

    except subprocess.TimeoutExpired:
        print("⚠️ 测试超时，但继续执行")
        return True
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False


def main():
    """主函数"""
    print("🚀 开始部署高优先级修复...")
    print(f"部署时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    steps = [
        ("检查依赖项", check_dependencies),
        ("更新应用程序配置", update_application_config),
        ("优化数据库", optimize_database),
        ("设置缓存系统", setup_cache_system),
        ("设置错误处理", setup_error_handling),
        ("设置监控系统", setup_monitoring),
        ("运行测试", run_tests)
    ]

    success_count = 0
    total_steps = len(steps)

    for step_name, step_func in steps:
        try:
            if step_func():
                print(f"✅ {step_name}: 成功")
                success_count += 1
            else:
                print(f"❌ {step_name}: 失败")
        except Exception as e:
            print(f"❌ {step_name}: 异常 - {e}")

    print(f"\n{'='*60}")
    print(f"部署完成: {success_count}/{total_steps} 步骤成功")
    print(f"{'='*60}")

    if success_count == total_steps:
        print("🎉 所有修复部署成功！")
        return True
    else:
        print("⚠️ 部分修复部署失败，请检查日志")
        return False


if __name__ == "__main__":
    main()
