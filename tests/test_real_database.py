#!/usr/bin/env python3
"""
真实的数据库集成测试
这个测试会真正连接数据库并执行查询，确保SQL语句正确
"""

import pytest
import pandas as pd
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from db_utils import get_db
from db_adapter import adapt_sql


class TestRealDatabaseQueries:
    """真实数据库查询测试"""

    def test_database_connection(self):
        """测试数据库连接"""
        with get_db() as (conn, cursor):
            assert conn is not None
            assert cursor is not None

            # 检查表是否存在（PostgreSQL）
            cursor.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_type = 'BASE TABLE'
            """)
            tables = [row[0] for row in cursor.fetchall()]

            print(f"数据库中的表: {tables}")

            # 验证必要的表存在
            required_tables = ["users", "products", "logistics"]
            for table in required_tables:
                assert table in tables, f"缺少必要的表: {table}"

    def test_products_table_query(self):
        """测试产品表查询"""
        with get_db() as (conn, cursor):
            try:
                # 使用 adapt_sql 确保正确的占位符（PostgreSQL使用%s）
                sql = adapt_sql("SELECT * FROM products WHERE user_id = %s")
                cursor.execute(sql, (1,))
                rows = cursor.fetchall()

                # 验证查询成功
                assert isinstance(rows, list)

            except Exception as e:
                pytest.fail(f"产品表查询失败: {e}")

    def test_logistics_table_query(self):
        """测试物流表查询"""
        with get_db() as (conn, cursor):
            try:
                # 使用 adapt_sql 确保正确的占位符
                sql = adapt_sql("SELECT * FROM logistics WHERE user_id = %s")
                cursor.execute(sql, (1,))
                rows = cursor.fetchall()

                # 验证查询成功
                assert isinstance(rows, list)

            except Exception as e:
                pytest.fail(f"物流表查询失败: {e}")

    def test_logistics_rules_table_query_fails(self):
        """测试错误的表名查询应该失败"""
        with get_db() as (conn, cursor):
            with pytest.raises(Exception):
                sql = adapt_sql("SELECT * FROM logistics_rules WHERE user_id = %s")
                cursor.execute(sql, (1,))

    def test_logistics_table_query(self):
        """测试物流表查询"""
        with get_db() as (conn, cursor):
            try:
                # 使用 adapt_sql 确保正确的占位符
                sql = adapt_sql("SELECT * FROM logistics WHERE user_id = %s")
                cursor.execute(sql, (1,))
                rows = cursor.fetchall()

                # 验证查询成功
                assert isinstance(rows, list)

            except Exception as e:
                pytest.fail(f"物流表查询失败: {e}")

    def test_logistics_rules_table_query_fails(self):
        """测试错误的表名查询应该失败"""
        with get_db() as (conn, cursor):
            with pytest.raises(Exception):
                sql = adapt_sql("SELECT * FROM logistics_rules WHERE user_id = %s")
                cursor.execute(sql, (1,))

    def test_table_structure(self):
        """测试表结构"""
        with get_db() as (conn, cursor):
            # 检查logistics表结构（PostgreSQL）
            cursor.execute("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'logistics'
            """)
            columns = cursor.fetchall()

            print("logistics表结构:")
            for col in columns:
                print(f"  - {col[0]} ({col[1]})")

            # 验证必要的列存在
            column_names = [col[0] for col in columns]
            required_columns = ["id", "user_id", "name", "type"]

            for col in required_columns:
                assert col in column_names, f"logistics表缺少列: {col}"

    def test_real_data_flow(self):
        """测试真实的数据流"""
        with get_db() as (conn, cursor):
            try:
                # 使用 adapt_sql 确保正确的占位符
                sql = adapt_sql("SELECT * FROM products WHERE user_id = %s")
                cursor.execute(sql, (1,))
                products = cursor.fetchall()

                sql = adapt_sql("SELECT * FROM logistics WHERE user_id = %s")
                cursor.execute(sql, (1,))
                logistics = cursor.fetchall()

                # 验证查询成功
                assert isinstance(products, list)
                assert isinstance(logistics, list)

            except Exception as e:
                pytest.fail(f"真实数据流测试失败: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
