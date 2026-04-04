# -*- coding: utf-8 -*-
"""
真实的数据库集成测试
这个测试会真正连接数据库并执行查询，确保SQL语句正确
"""

import pytest
from sqlalchemy import inspect, text

from database import AsyncSessionLocal, engine


class TestRealDatabaseQueries:
    """真实数据库查询测试"""

    async def test_database_connection(self):
        """测试数据库连接"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text(
                    "SELECT table_name FROM information_schema.tables"
                    " WHERE table_schema = 'public'"
                    " AND table_type = 'BASE TABLE'"
                )
            )
            tables = [row[0] for row in result.fetchall()]
            required_tables = ["users", "products", "logistics"]
            for table in required_tables:
                assert table in tables, f"缺少必要的表: {table}"

    async def test_products_table_query(self):
        """测试产品表查询"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("SELECT * FROM products WHERE user_id = :uid"),
                {"uid": 1},
            )
            rows = result.fetchall()
            assert isinstance(rows, list)

    async def test_logistics_table_query(self):
        """测试物流表查询"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("SELECT * FROM logistics WHERE user_id = :uid"),
                {"uid": 1},
            )
            rows = result.fetchall()
            assert isinstance(rows, list)

    async def test_logistics_rules_table_query_fails(self):
        """测试错误的表名查询应该失败"""
        async with AsyncSessionLocal() as session:
            with pytest.raises(Exception):
                await session.execute(
                    text("SELECT * FROM logistics_rules WHERE user_id = :uid"),
                    {"uid": 1},
                )

    async def test_table_structure(self):
        """测试表结构"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text(
                    "SELECT column_name, data_type"
                    " FROM information_schema.columns"
                    " WHERE table_name = 'logistics'"
                )
            )
            columns = result.fetchall()
            column_names = [col[0] for col in columns]
            for col in ["id", "user_id", "name", "type"]:
                assert col in column_names, f"logistics表缺少列: {col}"

    async def test_real_data_flow(self):
        """测试真实的数据流"""
        async with AsyncSessionLocal() as session:
            products = (
                await session.execute(
                    text("SELECT * FROM products WHERE user_id = :uid"),
                    {"uid": 1},
                )
            ).fetchall()
            logistics = (
                await session.execute(
                    text("SELECT * FROM logistics WHERE user_id = :uid"),
                    {"uid": 1},
                )
            ).fetchall()
            assert isinstance(products, list)
            assert isinstance(logistics, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
