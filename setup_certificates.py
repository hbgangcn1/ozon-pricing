# -*- coding: utf-8 -*-
"""
证书文件处理脚本
用于安全地设置微信支付证书文件
"""

import os
import shutil
from pathlib import Path


def setup_certificates():
    """设置证书文件"""
    print("🔐 微信支付证书设置工具")
    print("=" * 50)

    # 检查源证书文件
    cert_files = {
        "apiclient_key.pem": ("C:\\Users\\hbgan\\OneDrive\\Robert\\learn\\"
                              "logistics\\cert\\apiclient_key.pem"),
        "apiclient_cert.pem": ("C:\\Users\\hbgan\\OneDrive\\Robert\\learn\\"
                               "logistics\\cert\\apiclient_cert.pem"),
        "apiclient_cert.p12": ("C:\\Users\\hbgan\\OneDrive\\Robert\\learn\\"
                               "logistics\\cert\\apiclient_cert.p12")
    }

    # 创建目标目录
    target_dir = Path("cert")
    target_dir.mkdir(exist_ok=True)

    print("📁 检查证书文件...")

    # 复制证书文件
    copied_files = []
    for name, source_path in cert_files.items():
        if os.path.exists(source_path):
            target_path = target_dir / name
            shutil.copy2(source_path, target_path)

            # 设置文件权限（Windows下权限设置可能有限）
            try:
                os.chmod(target_path, 0o600 if "key" in name else 0o644)
            except (OSError, PermissionError, AttributeError):
                pass  # Windows可能不支持chmod

            copied_files.append(str(target_path))
            print(f"✅ {name} -> {target_path}")
        else:
            print(f"❌ 未找到: {source_path}")

    if copied_files:
        print("\n🔒 证书文件设置完成！")
        print("⚠️  重要提醒：")
        print("1. 请确保 cert/ 目录不会被提交到Git")
        print("2. 在生产服务器上使用绝对路径")
        print("3. 定期备份证书文件")

        # 生成环境变量配置
        generate_env_config(copied_files)
    else:
        print("❌ 未找到任何证书文件")


def generate_env_config(cert_files):
    """生成环境变量配置"""
    _ = cert_files  # 消除未使用参数警告
    print("\n📝 生成环境变量配置...")

    env_config = f"""# 微信支付证书配置
# 请在生产服务器上设置这些环境变量

# 证书文件路径（请根据实际服务器路径调整）
WECHAT_PRIVATE_KEY_PATH={os.path.abspath('cert/apiclient_key.pem')}
WECHAT_CERT_PATH={os.path.abspath('cert/apiclient_cert.pem')}

# 其他配置
WECHAT_APP_ID=wx85196df61679da0b
WECHAT_MCH_ID=1727894157
WECHAT_API_V3_KEY=oQuF4Vk71gYZbGtuJGL3YoG5H84iCymh
WECHAT_CERT_SERIAL_NO=7DE8E0220B96CDB6E19587BAD0BA672E819EA619
PRODUCTION_MODE=true
WECHAT_SANDBOX=false
"""

    with open("cert_env_config.txt", "w", encoding="utf-8") as f:
        f.write(env_config)

    print("✅ 环境变量配置已生成: cert_env_config.txt")
    print("⚠️  请将此文件内容添加到服务器的环境变量中")


def check_gitignore():
    """检查.gitignore文件"""
    print("\n🔍 检查.gitignore配置...")

    gitignore_content = """
# 微信支付证书文件
cert/
*.pem
*.p12
cert_env_config.txt
"""

    gitignore_file = Path(".gitignore")

    if gitignore_file.exists():
        with open(gitignore_file, "r", encoding="utf-8") as f:
            content = f.read()

        if "cert/" not in content:
            with open(gitignore_file, "a", encoding="utf-8") as f:
                f.write(gitignore_content)
            print("✅ 已更新 .gitignore 文件")
        else:
            print("✅ .gitignore 已包含证书文件配置")
    else:
        with open(gitignore_file, "w", encoding="utf-8") as f:
            f.write(gitignore_content)
        print("✅ 已创建 .gitignore 文件")


if __name__ == "__main__":
    try:
        setup_certificates()
        check_gitignore()

        print("\n🎉 证书设置完成！")
        print("\n📋 下一步：")
        print("1. 检查 cert/ 目录中的证书文件")
        print("2. 在生产服务器上设置环境变量")
        print("3. 在微信商户平台配置回调地址")
        print("4. 测试支付功能")

    except Exception as e:
        print(f"❌ 设置失败: {e}")
        print("请检查证书文件路径是否正确")
