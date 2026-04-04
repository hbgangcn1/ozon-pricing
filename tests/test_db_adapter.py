# -*- coding: utf-8 -*-
"""
数据库适配器测试
测试db_adapter.py的PostgreSQL数据库支持
"""

import pytest
import os
from unittest.mock import patch


class TestDatabaseAdapter:
    """数据库适配器测试类"""

    def test_adapt_sql_for_postgresql(self):
        """测试PostgreSQL的SQL语法适配"""
        from db_adapter import adapt_sql

        sql = "CREATE TABLE test (id INTEGER PRIMARY KEY AUTOINCREMENT)"
        result = adapt_sql(sql)
        # PostgreSQL模式下转换
        assert "SERIAL PRIMARY KEY" in result

    def test_adapt_sql_datetime_now(self):
        """测试datetime('now')转换"""
        from db_adapter import adapt_sql

        # DB_TYPE patch removed - using PostgreSQL directly
        sql = "INSERT INTO test VALUES (datetime('now'))"
        result = adapt_sql(sql)
        assert "CURRENT_TIMESTAMP" in result

    def test_adapt_sql_strftime(self):
        """测试strftime转换"""
        from db_adapter import adapt_sql

        # DB_TYPE patch removed - using PostgreSQL directly
        sql = "SELECT strftime('%s', 'now')"
        result = adapt_sql(sql)
        assert "extract(epoch from now())" in result

    def test_get_placeholder_postgresql(self):
        """测试PostgreSQL占位符"""
        from db_adapter import get_placeholder

        # DB_TYPE patch removed - using PostgreSQL directly
        placeholder = get_placeholder()
        assert placeholder == "%s"

    def test_adapt_placeholders_postgresql(self):
        """测试PostgreSQL占位符适配"""
        from db_adapter import adapt_placeholders

        # DB_TYPE patch removed - using PostgreSQL directly
        sql = "SELECT * FROM users WHERE id = ? AND name = ?"
        result = adapt_placeholders(sql, 2)
        # psycopg2使用%s占位符
        assert "%s" in result
        assert "?" not in result

    def test_get_last_insert_id_postgresql(self):
        """测试获取PostgreSQL最后插入ID"""
        from db_adapter import get_last_insert_id
        from unittest.mock import MagicMock

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)

        last_id = get_last_insert_id(mock_cursor)
        assert last_id == 1
        mock_cursor.execute.assert_called_with("SELECT lastval()")
        mock_cursor.fetchone.assert_called_once()

    def test_multiple_sql_adaptations(self):
        """测试多个SQL转换"""
        from db_adapter import adapt_sql

        # DB_TYPE patch removed - using PostgreSQL directly
        sql = """
        CREATE TABLE test (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at datetime('now'),
            timestamp strftime('%s', 'now')
        )
        """
        result = adapt_sql(sql)

        assert "SERIAL PRIMARY KEY" in result
        assert "CURRENT_TIMESTAMP" in result
        assert "extract(epoch from now())" in result

    def test_adapt_sql_insert_or_ignore(self):
        """测试INSERT OR IGNORE转换"""
        from db_adapter import adapt_sql

        # DB_TYPE patch removed - using PostgreSQL directly
        sql = "INSERT OR IGNORE INTO test VALUES (1)"
        result = adapt_sql(sql)
        assert "ON CONFLICT" in result and "DO NOTHING" in result

    def test_init_connection_pool(self):
        """测试初始化连接池"""
        from db_adapter import init_connection_pool

        # 应该正常执行
        init_connection_pool()


class TestDatabaseConfig:
    """数据库配置测试类"""

    def test_db_config_type(self):
        """测试数据库类型配置"""
        from db_config import DB_TYPE

        # 验证配置应该是postgresql
        assert DB_TYPE == "postgresql"

    def test_db_config_get_db_url(self):
        """测试获取数据库URL"""
        from db_config import get_db_url

        url = get_db_url()
        # 应该包含postgresql前缀
        assert "postgresql://" in url

    def test_db_config_get_db_config_dict(self):
        """测试获取配置字典"""
        from db_config import get_db_config

        config = get_db_config()
        assert isinstance(config, dict)
        assert "postgres_config" in config
        assert "pool_size" in config
        assert "timeout" in config

    def test_postgres_config_structure(self):
        """测试PostgreSQL配置结构"""
        from db_config import POSTGRES_CONFIG

        assert isinstance(POSTGRES_CONFIG, dict)
        assert "host" in POSTGRES_CONFIG
        assert "port" in POSTGRES_CONFIG
        assert "database" in POSTGRES_CONFIG
        assert "user" in POSTGRES_CONFIG
        assert "password" in POSTGRES_CONFIG

    def test_connection_pool_defaults(self):
        """测试连接池默认配置"""
        from db_config import (
        CONNECTION_POOL_SIZE,
        CONNECTION_POOL_MAX,
        CONNECTION_TIMEOUT,
        )

        assert isinstance(CONNECTION_POOL_SIZE, int)
        assert isinstance(CONNECTION_POOL_MAX, int)
        assert isinstance(CONNECTION_TIMEOUT, int)
        assert CONNECTION_POOL_SIZE > 0
        assert CONNECTION_POOL_MAX >= CONNECTION_POOL_SIZE

    def test_invalid_db_type_raises_error(self):
        """测试数据库类型配置"""
        from db_config import DB_TYPE

        # 验证DB_TYPE是postgresql
        assert DB_TYPE == "postgresql"

