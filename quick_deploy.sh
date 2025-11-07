#!/bin/bash
# Ubuntu生产环境快速部署脚本

set -e  # 遇到错误立即退出

echo "=========================================="
echo "物流定价系统 - Ubuntu生产环境部署"
echo "=========================================="
echo ""

# 切换到项目目录
cd /root/ozon-pricing-private

echo "【步骤1】检查Python环境"
python3 --version || { echo "❌ Python3未安装"; exit 1; }
echo "✅ Python环境正常"
echo ""

echo "【步骤2】检查/创建虚拟环境"
if [ ! -d ".venv" ]; then
    echo "创建虚拟环境..."
    python3 -m venv .venv
    echo "✅ 虚拟环境创建成功"
else
    echo "✅ 虚拟环境已存在"
fi

# 激活虚拟环境
source .venv/bin/activate
echo "✅ 虚拟环境已激活: $(which python)"
echo ""

echo "【步骤3】升级pip并安装依赖"
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
echo "✅ 依赖安装完成"
echo ""

echo "【步骤4】检查/创建.env文件"
if [ ! -f ".env" ]; then
    echo "从模板创建.env文件..."
    cp env.template .env
    echo "✅ .env文件已创建（请编辑配置）"
else
    echo "✅ .env文件已存在"
fi

# 检查必需的密钥
source .venv/bin/activate
python3 << 'PYEOF'
from dotenv import load_dotenv
import os
load_dotenv()

required_vars = {
    'SESSION_HMAC_SECRET': 'python3 -c "import secrets; print(secrets.token_urlsafe(64))"',
    'ENCRYPTION_KEY': 'python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"',
    'SESSION_SECRET': 'python3 -c "import secrets; print(secrets.token_urlsafe(32))"'
}

missing_vars = []
for var, gen_cmd in required_vars.items():
    if not os.getenv(var):
        missing_vars.append((var, gen_cmd))

if missing_vars:
    print("⚠️  以下密钥未设置:")
    for var, gen_cmd in missing_vars:
        print(f"   - {var}")
        print(f"     生成命令: {gen_cmd}")
else:
    print("✅ 所有必需密钥已设置")
PYEOF
echo ""

echo "【步骤5】检查数据库配置"
source .venv/bin/activate
python3 << 'PYEOF'
from dotenv import load_dotenv
import os
load_dotenv()

db_type = os.getenv('DB_TYPE', 'sqlite')
print(f"数据库类型: {db_type}")

if db_type == 'postgresql':
    host = os.getenv('POSTGRES_HOST')
    db = os.getenv('POSTGRES_DB')
    user = os.getenv('POSTGRES_USER')
    
    if host and db and user:
        print(f"✅ PostgreSQL配置已设置")
        print(f"   主机: {host}")
        print(f"   数据库: {db}")
        print(f"   用户: {user}")
    else:
        print("⚠️  PostgreSQL配置不完整")
        print("   请在.env文件中设置: POSTGRES_HOST, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD")
else:
    db_path = os.getenv('SQLITE_DB_PATH', 'logistics.db')
    print(f"✅ 使用SQLite数据库: {db_path}")
PYEOF
echo ""

echo "【步骤6】测试数据库连接"
source .venv/bin/activate
python3 << 'PYEOF'
try:
    from db_utils import get_db_connection
    with get_db_connection() as (conn, c):
        print("✅ 数据库连接成功")
        # 检查表是否存在
        if hasattr(c, 'execute'):
            try:
                c.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1")
                print("✅ 数据库表检查通过")
            except:
                print("⚠️  数据库可能未初始化，运行: python3 -c \"from db_utils import init_db; init_db()\"")
        else:
            # PostgreSQL
            c.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' LIMIT 1")
            print("✅ 数据库表检查通过")
except Exception as e:
    print(f"❌ 数据库连接失败: {e}")
    print("   请检查:")
    print("   1. 数据库服务是否运行")
    print("   2. .env文件中的数据库配置是否正确")
PYEOF
echo ""

echo "【步骤7】测试模块导入"
source .venv/bin/activate
python3 << 'PYEOF'
try:
    import streamlit as st
    import pandas as pd
    from db_utils import init_db
    print("✅ 核心模块导入成功")
except ImportError as e:
    print(f"❌ 模块导入失败: {e}")
    print("   请运行: pip install -r requirements.txt")
except Exception as e:
    print(f"⚠️  导入警告: {e}")
PYEOF
echo ""

echo "=========================================="
echo "✅ 基础检查完成！"
echo "=========================================="
echo ""
echo "下一步操作:"
echo "1. 如果.env文件中密钥未设置，请生成并添加:"
echo "   python3 -c \"import secrets; print('SESSION_HMAC_SECRET=' + secrets.token_urlsafe(64))\""
echo "   python3 -c \"from cryptography.fernet import Fernet; print('ENCRYPTION_KEY=' + Fernet.generate_key().decode())\""
echo "   python3 -c \"import secrets; print('SESSION_SECRET=' + secrets.token_urlsafe(32))\""
echo ""
echo "2. 如果数据库未初始化，运行:"
echo "   cd /root/ozon-pricing-private"
echo "   source .venv/bin/activate"
echo "   python3 -c \"from db_utils import init_db; init_db()\""
echo ""
echo "3. 创建管理员账户:"
echo "   python3 -c \"from db_utils import create_user; create_user('admin', '你的密码', 'admin', 'admin@example.com')\""
echo ""
echo "4. 测试启动应用:"
echo "   streamlit run app.py --server.port=8501 --server.address=127.0.0.1"
echo ""





