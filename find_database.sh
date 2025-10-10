#!/bin/bash
# 查找生产数据库文件

echo "========================================="
echo "查找数据库文件"
echo "========================================="

echo ""
echo "【1. 在当前目录查找】"
ls -lh *.db 2>/dev/null || echo "  未找到 .db 文件"

echo ""
echo "【2. 在项目目录查找】"
find . -name "*.db" -type f 2>/dev/null | head -10

echo ""
echo "【3. 在常见位置查找】"
find /root -name "*.db" -type f 2>/dev/null | head -10
find /var -name "logistics*.db" -type f 2>/dev/null | head -5
find /opt -name "logistics*.db" -type f 2>/dev/null | head -5

echo ""
echo "【4. 查找Streamlit进程】"
ps aux | grep streamlit | grep -v grep

echo ""
echo "【5. 查找Python应用进程】"
ps aux | grep "app.py\|ui_" | grep -v grep

echo ""
echo "【6. 检查应用配置】"
if [ -f "app.py" ]; then
    echo "app.py 中的数据库配置："
    grep -n "sqlite3.connect\|logistics.db\|pricing_system.db" app.py | head -5
fi

if [ -f "db_utils.py" ]; then
    echo ""
    echo "db_utils.py 中的数据库配置："
    grep -n "sqlite3.connect\|get_db_connection" db_utils.py | head -10
fi

