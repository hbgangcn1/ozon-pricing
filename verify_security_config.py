# -*- coding: utf-8 -*-
"""
安全配置验证脚本
用于检查微信支付证书和环境变量配置是否正确
"""

import os
import sys
from pathlib import Path

# 尝试导入 python-dotenv
try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False
    load_dotenv = None  # type: ignore


def check_gitignore():
    """检查 .gitignore 是否包含必要的规则"""
    print("🔍 检查 .gitignore 配置...")

    required_patterns = [
        'cert/',
        '*.pem',
        '*.key',
        '.env',
        '.env.local',
        '.env.production'
    ]

    gitignore_path = Path('.gitignore')
    if not gitignore_path.exists():
        print("❌ .gitignore 文件不存在")
        return False

    with open(gitignore_path, 'r', encoding='utf-8') as f:
        content = f.read()

    missing = []
    for pattern in required_patterns:
        if pattern not in content:
            missing.append(pattern)

    if missing:
        print(f"⚠️  .gitignore 缺少以下规则: {', '.join(missing)}")
        return False
    else:
        print("✅ .gitignore 配置正确")
        return True


def check_env_files():
    """检查环境变量配置文件"""
    print("\n🔍 检查环境变量配置文件...")

    # 检查模板文件是否存在
    if Path('env.template').exists():
        print("✅ 配置模板文件存在: env.template")
    else:
        print("⚠️  配置模板文件不存在: env.template")

    # 检查是否有 .env 文件
    if Path('.env').exists():
        print("✅ 本地配置文件存在: .env")

        # 检查是否包含真实密钥（简单检测）
        with open('.env', 'r', encoding='utf-8') as f:
            content = f.read()

        if 'your_' in content or 'YOUR_' in content:
            print("⚠️  .env 文件可能仍包含占位符，请填写实际配置")
        else:
            print("✅ .env 文件已填写配置（请确保不提交到Git）")
    else:
        print("ℹ️  本地配置文件不存在: .env")
        print("   请复制 env.template 为 .env 并填写实际配置")


def check_env_variables():
    """检查环境变量是否已设置"""
    print("\n🔍 检查环境变量...")

    # 加载 .env 文件
    if DOTENV_AVAILABLE and load_dotenv is not None:
        load_dotenv()
        print("✅ python-dotenv 已安装")
    else:
        print("⚠️  python-dotenv 未安装")
        print("   运行: pip install python-dotenv")

    required_vars = {
        'WECHAT_APP_ID': '微信公众号 AppID',
        'WECHAT_MCH_ID': '商户号',
        'WECHAT_API_V3_KEY': 'API v3 密钥',
        'WECHAT_PRIVATE_KEY_PATH': '私钥文件路径',
        'WECHAT_CERT_SERIAL_NO': '证书序列号'
    }

    missing = []
    configured = []

    for var, desc in required_vars.items():
        value = os.getenv(var)
        if value:
            # 脱敏显示
            if 'KEY' in var or 'SERIAL' in var:
                if len(value) > 12:
                    display = f"{value[:4]}...{value[-4:]}"
                else:
                    display = "***"
            else:
                display = value

            print(f"✅ {var}: {display}")
            configured.append(var)
        else:
            print(f"❌ {var}: 未设置 ({desc})")
            missing.append(var)

    if missing:
        print(f"\n⚠️  缺少 {len(missing)} 个必需的环境变量")
        return False
    else:
        print(f"\n✅ 所有 {len(configured)} 个环境变量已配置")
        return True


def check_cert_files():
    """检查证书文件"""
    print("\n🔍 检查证书文件...")

    cert_dir = Path('cert')
    if not cert_dir.exists():
        print("⚠️  证书目录不存在: cert/")
        print("   请创建 cert/ 目录并放置证书文件")
        return False

    cert_files = {
        'apiclient_key.pem': '商户私钥',
        'apiclient_cert.pem': '商户证书'
    }

    all_exists = True
    for filename, desc in cert_files.items():
        filepath = cert_dir / filename
        if filepath.exists():
            size = filepath.stat().st_size
            print(f"✅ {filename}: 存在 ({size} bytes)")

            # 检查文件权限（仅 Linux/Mac）
            if sys.platform != 'win32':
                import stat
                mode = filepath.stat().st_mode
                perms = stat.filemode(mode)
                if 'key' in filename and mode & 0o077:
                    print(f"   ⚠️  权限过宽: {perms}")
                    print(f"   建议运行: chmod 600 {filepath}")
                else:
                    print(f"   ✅ 权限正确: {perms}")
        else:
            print(f"❌ {filename}: 不存在 ({desc})")
            all_exists = False

    return all_exists


def check_production_config():
    """检查生产环境配置"""
    print("\n🔍 检查生产环境配置...")

    try:
        from production_wechat_config import ProductionWeChatConfig

        # 临时设置环境变量以避免警告
        os.environ.setdefault('WECHAT_APP_ID', 'test')
        os.environ.setdefault('WECHAT_MCH_ID', 'test')
        os.environ.setdefault('WECHAT_API_V3_KEY', 'test')
        os.environ.setdefault('WECHAT_PRIVATE_KEY_PATH', 'test')
        os.environ.setdefault('WECHAT_CERT_SERIAL_NO', 'test')

        config = ProductionWeChatConfig()
        print("✅ 生产环境配置模块可用")

        # 验证配置使用环境变量
        if config.app_id == os.getenv('WECHAT_APP_ID'):
            print("✅ 配置正确使用环境变量")
        else:
            print("⚠️  配置可能未使用环境变量")

        return True
    except ImportError as e:
        print(f"❌ 无法导入生产环境配置: {e}")
        return False
    except Exception as e:
        print(f"⚠️  配置验证出错: {e}")
        return False


def main():
    """主函数"""
    print("=" * 60)
    print("🔐 微信支付证书安全配置验证")
    print("=" * 60)
    print()

    results = {
        'gitignore': check_gitignore(),
        'env_files': check_env_files(),
        'env_vars': check_env_variables(),
        'cert_files': check_cert_files(),
        'production_config': check_production_config()
    }

    print("\n" + "=" * 60)
    print("📊 验证结果汇总")
    print("=" * 60)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for check, result in results.items():
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{check:20s}: {status}")

    print()
    print(f"总计: {passed}/{total} 项检查通过")

    if passed == total:
        print("\n🎉 所有安全配置检查通过！")
        print("📖 详细配置指南: SECURITY_CONFIGURATION_GUIDE.md")
        return 0
    else:
        print("\n⚠️  部分配置需要修正，请参考上述提示")
        print("📖 详细配置指南: SECURITY_CONFIGURATION_GUIDE.md")
        return 1


if __name__ == "__main__":
    sys.exit(main())
