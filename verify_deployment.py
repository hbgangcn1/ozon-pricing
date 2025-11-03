#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生产环境部署验证脚本
用于检查部署是否完整和正确
"""

import os
import sys
from pathlib import Path


def check_python_version():
    """检查 Python 版本"""
    print("=" * 60)
    print("1. 检查 Python 版本...")
    version = sys.version_info
    if version.major == 3 and version.minor >= 8:
        print(f"  ✅ Python {version.major}.{version.minor}.{version.micro} - 版本符合要求")
        return True
    else:
        print(f"  ❌ Python {version.major}.{version.minor}.{version.micro} - 需要 Python 3.8+")
        return False


def check_required_modules():
    """检查必需的 Python 模块"""
    print("\n2. 检查必需的 Python 模块...")
    required_modules = [
        'streamlit',
        'pandas',
        'bcrypt',
        'requests',
        'sqlite3',
        'dotenv',
    ]
    
    missing = []
    for module in required_modules:
        try:
            __import__(module)
            print(f"  ✅ {module}")
        except ImportError:
            print(f"  ❌ {module} - 未安装")
            missing.append(module)
    
    # 检查 PostgreSQL 驱动（可选）
    try:
        import psycopg2
        print(f"  ✅ psycopg2 (PostgreSQL驱动)")
    except ImportError:
        print(f"  ⚠️  psycopg2 - 未安装（如果使用 PostgreSQL 需要安装）")
    
    # 检查 Redis（可选）
    try:
        import redis
        print(f"  ✅ redis (缓存驱动)")
    except ImportError:
        print(f"  ⚠️  redis - 未安装（可选，用于缓存加速）")
    
    return len(missing) == 0


def check_env_file():
    """检查 .env 文件"""
    print("\n3. 检查环境变量文件...")
    
    env_file = Path('.env')
    if not env_file.exists():
        print("  ❌ .env 文件不存在")
        print("  📝 请复制 env.template 为 .env 并填写配置")
        return False
    
    print("  ✅ .env 文件存在")
    
    # 读取并检查关键环境变量
    from dotenv import load_dotenv
    load_dotenv()
    
    critical_vars = {
        'SESSION_HMAC_SECRET': '会话HMAC密钥（必须设置！）',
        'ENCRYPTION_KEY': '数据加密密钥（必须设置！）',
        'DB_TYPE': '数据库类型',
    }
    
    missing_vars = []
    for var, desc in critical_vars.items():
        value = os.getenv(var)
        if value:
            if var in ['SESSION_HMAC_SECRET', 'ENCRYPTION_KEY']:
                # 只显示是否设置，不显示值
                print(f"  ✅ {var} - 已设置 ({desc})")
            else:
                print(f"  ✅ {var} = {value}")
        else:
            print(f"  ❌ {var} - 未设置 ({desc})")
            missing_vars.append(var)
    
    # 检查数据库配置
    db_type = os.getenv('DB_TYPE', 'sqlite')
    if db_type == 'postgresql':
        postgres_vars = ['POSTGRES_HOST', 'POSTGRES_PORT', 'POSTGRES_DB', 
                        'POSTGRES_USER', 'POSTGRES_PASSWORD']
        for var in postgres_vars:
            value = os.getenv(var)
            if value:
                if 'PASSWORD' in var:
                    print(f"  ✅ {var} - 已设置")
                else:
                    print(f"  ✅ {var} = {value}")
            else:
                print(f"  ❌ {var} - 未设置")
                missing_vars.append(var)
    
    return len(missing_vars) == 0


def check_database_connection():
    """检查数据库连接"""
    print("\n4. 检查数据库连接...")
    
    try:
        from dotenv import load_dotenv
        load_dotenv()
        from db_utils import get_db_connection
        
        with get_db_connection() as (conn, c):
            # 测试查询
            c.execute("SELECT 1")
            result = c.fetchone()
            if result:
                print("  ✅ 数据库连接成功")
                
                # 检查关键表是否存在
                if hasattr(conn, 'execute'):
                    # SQLite
                    tables = c.execute("""
                        SELECT name FROM sqlite_master 
                        WHERE type='table' AND name IN ('users', 'products', 'logistics')
                    """).fetchall()
                else:
                    # PostgreSQL
                    c.execute("""
                        SELECT table_name FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name IN ('users', 'products', 'logistics')
                    """)
                    tables = c.fetchall()
                
                if len(tables) >= 3:
                    print("  ✅ 关键数据表已创建")
                    return True
                else:
                    print("  ⚠️  数据表可能未完全创建，请运行 init_db()")
                    return False
            else:
                print("  ❌ 数据库查询失败")
                return False
    except Exception as e:
        print(f"  ❌ 数据库连接失败: {e}")
        print("  📝 请检查：")
        print("     1. 数据库服务是否运行")
        print("     2. .env 中的数据库配置是否正确")
        print("     3. 数据库用户权限是否正确")
        return False


def check_session_security():
    """检查会话安全配置"""
    print("\n5. 检查会话安全配置...")
    
    try:
        from session_security import SessionSecurity
        
        # 尝试生成会话ID（这会检查 SESSION_HMAC_SECRET）
        try:
            session_id = SessionSecurity.generate_session_id(1)
            if session_id:
                print("  ✅ 会话ID生成成功（SESSION_HMAC_SECRET 配置正确）")
                return True
            else:
                print("  ❌ 会话ID生成失败")
                return False
        except ValueError as e:
            if "SESSION_HMAC_SECRET" in str(e):
                print("  ❌ SESSION_HMAC_SECRET 环境变量未设置")
                print("  📝 请在 .env 文件中设置 SESSION_HMAC_SECRET")
                return False
            else:
                raise
    except Exception as e:
        print(f"  ❌ 会话安全检查失败: {e}")
        return False


def check_certificates():
    """检查证书文件（如果使用微信支付）"""
    print("\n6. 检查证书文件...")
    
    from dotenv import load_dotenv
    load_dotenv()
    
    cert_dir = os.getenv('WECHAT_CERT_DIR', 'cert')
    private_key_path = os.getenv('WECHAT_PRIVATE_KEY_PATH', 
                                 os.path.join(cert_dir, 'apiclient_key.pem'))
    
    if not os.path.exists(private_key_path):
        print(f"  ⚠️  证书文件不存在: {private_key_path}")
        print("  📝 如果使用微信支付功能，需要上传证书文件")
        return True  # 不使用支付时不强制要求
    
    print(f"  ✅ 证书文件存在: {private_key_path}")
    
    # 检查文件权限
    import stat
    file_stat = os.stat(private_key_path)
    mode = file_stat.st_mode
    if mode & stat.S_IRGRP or mode & stat.S_IWGRP or mode & stat.S_IROTH or mode & stat.S_IWOTH:
        print(f"  ⚠️  证书文件权限可能不安全（建议 600）")
    else:
        print(f"  ✅ 证书文件权限正确")
    
    return True


def check_directory_permissions():
    """检查目录权限"""
    print("\n7. 检查目录权限...")
    
    env_file = Path('.env')
    if env_file.exists():
        import stat
        mode = env_file.stat().st_mode
        # 检查是否只有所有者可读写
        if mode & (stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH | stat.S_IWOTH):
            print("  ⚠️  .env 文件权限可能不安全（建议 600）")
            print("  📝 运行: chmod 600 .env")
        else:
            print("  ✅ .env 文件权限正确")
    
    backup_dir = Path('backups')
    if backup_dir.exists():
        print(f"  ✅ backups 目录存在")
    else:
        print(f"  ⚠️  backups 目录不存在（自动备份需要此目录）")
    
    logs_dir = Path('logs')
    if logs_dir.exists():
        print(f"  ✅ logs 目录存在")
    else:
        print(f"  ⚠️  logs 目录不存在（日志将写入当前目录）")
    
    return True


def check_backup_configuration():
    """检查备份配置"""
    print("\n8. 检查备份配置...")
    
    try:
        from auto_backup import get_backup_info
        backup_info = get_backup_info()
        
        if backup_info and backup_info.get('backup_count', 0) > 0:
            print(f"  ✅ 备份功能正常（已有 {backup_info.get('backup_count')} 个备份）")
        else:
            print("  ⚠️  尚未创建备份，建议立即创建备份")
        
        return True
    except Exception as e:
        print(f"  ⚠️  备份模块检查失败: {e}")
        return True  # 不影响整体验证


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("生产环境部署验证")
    print("=" * 60)
    
    results = []
    
    results.append(("Python版本", check_python_version()))
    results.append(("Python模块", check_required_modules()))
    results.append(("环境变量", check_env_file()))
    results.append(("数据库连接", check_database_connection()))
    results.append(("会话安全", check_session_security()))
    results.append(("证书文件", check_certificates()))
    results.append(("目录权限", check_directory_permissions()))
    results.append(("备份配置", check_backup_configuration()))
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("验证结果汇总")
    print("=" * 60)
    
    critical_checks = ['Python版本', 'Python模块', '环境变量', '数据库连接', '会话安全']
    passed = 0
    failed = 0
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        critical = "【关键】" if name in critical_checks else ""
        print(f"{critical}{name}: {status}")
        
        if result:
            passed += 1
        else:
            failed += 1
            if name in critical_checks:
                print(f"    ⚠️  此项必须修复才能正常运行！")
    
    print("\n" + "=" * 60)
    print(f"总计: {passed} 项通过, {failed} 项失败")
    
    if failed == 0:
        print("✅ 所有检查通过！部署配置正确。")
        return 0
    else:
        critical_failed = [name for name, result in results 
                          if not result and name in critical_checks]
        if critical_failed:
            print(f"❌ 关键检查项失败: {', '.join(critical_failed)}")
            print("⚠️  请修复这些问题后再启动应用！")
            return 1
        else:
            print("⚠️  有非关键项未通过，但可以运行")
            print("建议修复这些问题以获得更好的体验")
            return 0


if __name__ == '__main__':
    sys.exit(main())

