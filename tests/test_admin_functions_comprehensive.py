# -*- coding: utf-8 -*-
"""
管理员功能综合测试
覆盖管理员认证、用户管理、订阅管理、冻结/解冻、删除等功能
"""

import pytest
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db_utils import (
    get_db_connection,
    create_user,
)
from db_utils import create_user, get_user_detail
from db_utils import (
    get_all_users,
    get_user_detail,
    update_user_subscription_admin,
    freeze_user,
    unfreeze_user,
    delete_user_admin,
    authenticate_admin,
)


class TestAdminAuthentication:
    """测试管理员认证"""

    def test_authenticate_admin_success(self, clean_db):  # noqa: ARG002
        """测试管理员认证成功
        clean_db 参数是 pytest fixture，会自动清理测试数据
        """
        _ = clean_db  # 明确表示 fixture 参数未显式使用
        import time
        import secrets

        # 使用时间戳+随机数确保唯一性
        unique_suffix = f"{int(time.time() * 1000)}_{secrets.token_hex(4)}"
        password = "Admin123!@#Test"
        username = f"admin_user_{unique_suffix}"
        unique_email = f"admin_{unique_suffix}@test.com"

        # 使用create_user创建测试用户
        user = create_user(
            username, password, role="admin", email=unique_email, is_test_user=True
        )

        if user is None:
            pytest.fail(f"Failed to create admin user: {username}")

        # 测试认证
        result = authenticate_admin(username, password)

        assert result is not None
        assert result["role"] == "admin"
        assert result["username"] == username

    def test_authenticate_admin_wrong_password(self, clean_db):  # noqa: ARG002
        """测试管理员认证 - 密码错误
        clean_db 参数是 pytest fixture，会自动清理测试数据
        """
        _ = clean_db  # 明确表示 fixture 参数未显式使用
        import time
        import secrets

        # 使用时间戳+随机数确保唯一性
        unique_suffix = f"{int(time.time() * 1000)}_{secrets.token_hex(4)}"
        password = "Admin123!@#Test"
        username = f"admin_wrong_{unique_suffix}"
        unique_email = f"admin_wrong_{unique_suffix}@test.com"

        user = create_user(
            username, password, role="admin", email=unique_email, is_test_user=True
        )

        if user is None:
            pytest.fail(f"Failed to create admin user: {username}")

        # 测试错误密码
        result = authenticate_admin(username, "WrongPassword123!@#")

        assert result is None

    def test_authenticate_admin_user_not_found(self, clean_db):  # noqa: ARG002
        """测试管理员认证 - 用户不存在
        clean_db 参数是 pytest fixture，会自动清理测试数据
        """
        _ = clean_db  # 明确表示 fixture 参数未显式使用
        result = authenticate_admin("nonexistent", "password")
        assert result is None

    def test_authenticate_admin_not_admin_role(self, clean_db):  # noqa: ARG002
        """测试管理员认证 - 非管理员角色
        clean_db 参数是 pytest fixture，会自动清理测试数据
        """
        _ = clean_db  # 明确表示 fixture 参数未显式使用
        import time
        import secrets

        # 使用时间戳+随机数确保唯一性
        unique_suffix = f"{int(time.time() * 1000)}_{secrets.token_hex(4)}"
        password = "User123!@#Test"
        username = f"regular_{unique_suffix}"
        unique_email = f"regular_{unique_suffix}@test.com"

        user = create_user(
            username, password, role="user", email=unique_email, is_test_user=True
        )

        if user is None:
            pytest.fail(f"Failed to create regular user: {username}")

        # 测试非管理员用户
        result = authenticate_admin(username, password)
        assert result is None


class TestGetAllUsers:
    """测试获取所有用户列表"""

    def test_get_all_users_basic(self, clean_db):  # noqa: ARG002
        """测试基本用户列表查询
        clean_db 参数是 pytest fixture，会自动清理测试数据
        """
        _ = clean_db  # 明确表示 fixture 参数未显式使用
        # 批量创建测试用户以加速测试
        import secrets
        from datetime import datetime
        from db_utils import (
            init_db,
            hash_password,
            get_db_connection,
            _is_postgresql_connection,  # pyright: ignore[reportPrivateUsage]
            _safe_adapt_sql,  # pyright: ignore[reportPrivateUsage]
        )

        unique_suffix = f"{int(time.time() * 1000)}_{secrets.token_hex(4)}"

        # 使用批量插入优化性能
        init_db()
        hashed_password = hash_password("Password123!@#")
        users_to_insert = []
        for i in range(5):
            username = f"user_{unique_suffix}_{i}"
            email = f"user_{unique_suffix}_{i}@test.com"
            users_to_insert.append(
                (
                    username,
                    hashed_password,
                    "user",
                    email,
                    "free",
                    -1,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    1,
                )
            )

        with get_db_connection() as (conn, c):
            is_pg = _is_postgresql_connection(conn)

            if is_pg:
                insert_sql_raw = """
                    INSERT INTO users (username, password, role, email,
                    user_type, remaining_calculations, created_at, is_test_user)
                    VALUES (%s, %s, %s, %s, %s, %s, to_timestamp(%s), %s)
                    RETURNING id
                """
            else:
                insert_sql_raw = """
                    INSERT INTO users (username, password, role, email,
                    user_type, remaining_calculations, created_at, is_test_user)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """
            insert_sql = _safe_adapt_sql(insert_sql_raw, conn)

            for user_data in users_to_insert:
                if is_pg:
                    user_data_pg = list(user_data)
                    user_data_pg[6] = datetime.strptime(
                        user_data_pg[6], "%Y-%m-%d %H:%M:%S"
                    ).timestamp()
                    c.execute(insert_sql, tuple(user_data_pg))
                else:
                    c.execute(insert_sql, user_data)
            conn.commit()

        result = get_all_users(page=1, per_page=10)

        assert "users" in result
        assert "total_count" in result
        assert "total_pages" in result
        assert "current_page" in result
        assert len(result["users"]) >= 5

    def test_get_all_users_with_search(self, clean_db):  # noqa: ARG002
        """测试带搜索的用户列表查询
        clean_db 参数是 pytest fixture，会自动清理测试数据
        """
        from unittest.mock import patch

        _ = clean_db  # 明确表示 fixture 参数未显式使用
        import time
        import secrets

        # 使用时间戳+随机数确保唯一性
        unique_suffix = f"{int(time.time() * 1000)}_{secrets.token_hex(4)}"
        # Mock hash_password 以加速测试（此测试不涉及密码验证）
        with patch("db_utils.hash_password", lambda pwd: f"$2b$04$fast{pwd}"):
            # 创建测试用户（使用唯一用户名）
            user1 = create_user(
                f"john_doe_{unique_suffix}",
                "Password123!@#",
                role="user",
                email=f"john_{unique_suffix}@test.com",
                is_test_user=True,
            )
            user2 = create_user(
                f"jane_doe_{unique_suffix}",
                "Password123!@#",
                role="user",
                email=f"jane_{unique_suffix}@test.com",
                is_test_user=True,
            )
            user3 = create_user(
                f"bob_smith_{unique_suffix}",
                "Password123!@#",
                role="user",
                email=f"bob_{unique_suffix}@test.com",
                is_test_user=True,
            )

        if user1 is None or user2 is None or user3 is None:
            pytest.fail(
                f"Failed to create test users: user1={user1}, user2={user2}, user3={user3}"
            )

        # 搜索 "john"
        result = get_all_users(page=1, per_page=10, search="john")

        # 应该找到至少一个包含"john"的用户
        assert result.get("total_count", result.get("total", 0)) >= 1
        assert any(
            "john" in user["username"].lower() or "john" in user["email"].lower()
            for user in result["users"]
        )

    def test_get_all_users_with_user_type_filter(self, clean_db):  # noqa: ARG002
        """测试按用户类型过滤
        clean_db 参数是 pytest fixture，会自动清理测试数据
        """
        _ = clean_db  # 明确表示 fixture 参数未显式使用
        # 创建不同类型的用户
        import secrets

        unique_suffix = f"{int(time.time() * 1000)}_{secrets.token_hex(4)}"
        create_user(
            f"free_user_{unique_suffix}",
            "Password123!@#",
            role="user",
            email=f"free_{unique_suffix}@test.com",
            is_test_user=True,
        )

        with get_db_connection() as (conn, c):
            from db_adapter import adapt_sql

            sql = adapt_sql("UPDATE users SET user_type = 'free' WHERE username = ?")
            c.execute(sql, (f"free_user_{unique_suffix}",))
            conn.commit()

        result = get_all_users(page=1, per_page=10, user_type_filter="free")

        assert all(user["user_type"] == "free" for user in result["users"])

    def test_get_all_users_with_status_filter_expired(self, clean_db):  # noqa: ARG002
        """测试按过期状态过滤
        clean_db 参数是 pytest fixture，会自动清理测试数据
        """
        _ = clean_db  # 明确表示 fixture 参数未显式使用
        import time
        import secrets

        # 使用时间戳+随机数确保唯一性
        unique_suffix = f"{int(time.time() * 1000)}_{secrets.token_hex(4)}"
        username = f"expired_user_{unique_suffix}"
        email = f"expired_{unique_suffix}@test.com"

        # 创建过期用户
        user = create_user(
            username, "Password123!@#", role="user", email=email, is_test_user=True
        )

        if user is None:
            pytest.fail(f"Failed to create expired user: {username}")

        expired_time = int(time.time()) - 86400  # 1天前
        with get_db_connection() as (conn, c):
            from db_adapter import adapt_sql

            sql = adapt_sql(
                """
                UPDATE users 
                SET subscription_expires = ?
                WHERE username = ?
                """
            )
            c.execute(sql, (expired_time, username))
            conn.commit()

        result = get_all_users(page=1, per_page=10, status_filter="expired")

        # 应该找到过期用户
        assert any(user["username"] == username for user in result["users"])

    def test_get_all_users_pagination(self, clean_db, monkeypatch):  # noqa: ARG002
        """测试分页功能
        clean_db 参数是 pytest fixture，会自动清理测试数据
        """
        _ = clean_db  # 明确表示 fixture 参数未显式使用
        import time
        import secrets
        import importlib

        # 防止加载 session_security_enhanced 模块，避免 Redis 锁超时
        original_import = importlib.import_module

        def mock_import_module(module_name, package=None):
            if module_name == "session_security_enhanced" or (
                package and module_name.endswith(".session_security_enhanced")
            ):
                raise ImportError("Mocked import error to prevent Redis lock timeout")
            return original_import(module_name, package)

        monkeypatch.setattr(importlib, "import_module", mock_import_module)

        # 使用时间戳+随机数确保唯一性
        unique_suffix = f"{int(time.time() * 1000)}_{secrets.token_hex(4)}"
        # 批量创建用户以提高性能（使用批量插入而不是循环调用create_user）
        # create_user每次都会调用init_db()和多次数据库查询，批量插入会快很多
        created_user_ids = []
        password_hash = None  # 缓存密码哈希，避免重复计算

        # 预先计算密码哈希（bcrypt较慢，只计算一次）
        from db_utils import hash_password

        password_hash = hash_password("Password123!@#")

        # 批量插入用户
        with get_db_connection() as (conn, c):
            from db_utils import (
                _safe_adapt_sql,  # pyright: ignore[reportPrivateUsage]
                _is_postgresql_connection,  # pyright: ignore[reportPrivateUsage]
            )
            from datetime import datetime

            created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            is_pg = _is_postgresql_connection(conn)

            # 准备批量插入数据
            users_to_insert = []
            for i in range(25):
                username = f"user_{unique_suffix}_{i}"
                email = f"user_{unique_suffix}_{i}@test.com"
                users_to_insert.append(
                    (
                        username,
                        password_hash,
                        "user",
                        email,
                        "test",
                        "test",
                        -1,
                        created_at,
                        1,  # is_test_user=1
                    )
                )

            # 批量插入（根据数据库类型选择不同的SQL）
            if is_pg:
                sql_raw = (
                    "INSERT INTO users (username, password, role, email, "
                    "user_type, subscription_type, remaining_calculations, "
                    "created_at, is_test_user) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, to_timestamp(?), ?) "
                    "RETURNING id"
                )
                sql = _safe_adapt_sql(sql_raw, conn)
                created_at_ts = int(datetime.now().timestamp())
                # PostgreSQL批量插入
                for user_data in users_to_insert:
                    user_data_list = list(user_data)
                    user_data_list[7] = created_at_ts  # 替换created_at为时间戳
                    c.execute(sql, user_data_list)
                    user_id = c.fetchone()[0]
                    created_user_ids.append(user_id)
            else:
                sql_raw = (
                    "INSERT INTO users (username, password, role, email, "
                    "user_type, subscription_type, remaining_calculations, "
                    "created_at, is_test_user) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
                )
                sql = _safe_adapt_sql(sql_raw, conn)
                for user_data in users_to_insert:
                    c.execute(sql, user_data)
                    created_user_ids.append(c.lastrowid)

            conn.commit()

        created_count = len(created_user_ids)
        if created_count < 10:
            pytest.fail(f"Only created {created_count} users, need at least 10")

        # 清除get_all_users的缓存（通过重新导入或直接调用）
        # 不需要等待，create_user已经提交事务

        # 清除get_all_users的缓存（通过重新导入或直接调用）
        try:
            import streamlit as st

            if hasattr(st, "cache_data"):
                # 尝试清除缓存
                if hasattr(st.cache_data, "clear"):
                    st.cache_data.clear()
        except (ImportError, AttributeError, RuntimeError):
            # 清除缓存失败，忽略继续执行测试
            pass

        # 使用唯一后缀作为搜索关键字，避免被其他测试创建的用户干扰
        search_keyword = f"user_{unique_suffix}"

        # 重试机制：最多重试3次
        max_retries = 3
        for attempt in range(max_retries):
            # 第一页
            result1 = get_all_users(page=1, per_page=10, search=search_keyword)
            # 第一页应该至少有10个用户（如果创建了足够的用户）
            # 注意：result1['users']可能包含其他用户（如admin），所以只检查我们创建的用户
            created_users_in_page1 = [
                u for u in result1["users"] if u["id"] in created_user_ids
            ]

            if len(created_users_in_page1) >= min(10, created_count):
                # 成功，继续测试第二页
                assert result1["current_page"] == 1

                # 第二页
                result2 = get_all_users(page=2, per_page=10, search=search_keyword)
                created_users_in_page2 = [
                    u for u in result2["users"] if u["id"] in created_user_ids
                ]
                if created_count > 10:
                    expected_min = min(10, created_count - 10)
                    if len(created_users_in_page2) >= expected_min:
                        assert result2["current_page"] == 2
                        return  # 测试通过
                    elif attempt < max_retries - 1:
                        # 重试（减少等待时间）
                        time.sleep(0.1)
                        continue
                    else:
                        pytest.fail(
                            f"Expected at least {expected_min} created users in page 2, "
                            f"but got {len(created_users_in_page2)}. "
                            f"Total users in page 2: {len(result2['users'])}. "
                            f"Created user IDs: {created_user_ids[:20]}"
                        )
                else:
                    assert result2["current_page"] == 2
                    return  # 测试通过
            elif attempt < max_retries - 1:
                # 重试（减少等待时间）
                time.sleep(0.1)
                continue
            else:
                # 最后一次尝试失败
                pytest.fail(
                    f"Expected at least {min(10, created_count)} created users in page 1, "
                    f"but got {len(created_users_in_page1)}. "
                    f"Total users in page 1: {len(result1['users'])}. "
                    f"Created user IDs: {created_user_ids[:20]}. "
                    f"Users in page 1: {[u['id'] for u in result1['users']]}"
                )


class TestGetUserDetail:
    """测试获取用户详细信息"""

    def test_get_user_detail_success(self, clean_db):  # noqa: ARG002
        """测试成功获取用户详情
        clean_db 参数是 pytest fixture，会自动清理测试数据
        """
        _ = clean_db  # 明确表示 fixture 参数未显式使用
        import time
        import secrets

        unique_suffix = f"{int(time.time() * 1000)}_{secrets.token_hex(4)}"
        username = f"test_user_{unique_suffix}"
        user_id = create_user(
            username,
            "Password123!@#",
            role="user",
            email=f"test_{unique_suffix}@test.com",
            is_test_user=True,
        )

        if user_id is None:
            pytest.fail(f"create_user returned None for {username}")

        detail = get_user_detail(user_id)

        assert detail is not None
        assert detail["id"] == user_id
        assert detail["username"] == username
        assert detail["email"] == f"test_{unique_suffix}@test.com"

    def test_get_user_detail_not_found(self, clean_db):  # noqa: ARG002
        """测试用户不存在
        clean_db 参数是 pytest fixture，会自动清理测试数据
        """
        _ = clean_db  # 明确表示 fixture 参数未显式使用
        detail = get_user_detail(99999)
        assert detail is None


class TestUpdateUserSubscriptionAdmin:
    """测试管理员更新用户订阅"""

    def test_update_user_subscription_admin_success(self, clean_db):  # noqa: ARG002
        """测试成功更新订阅
        clean_db 参数是 pytest fixture，会自动清理测试数据
        """
        _ = clean_db  # 明确表示 fixture 参数未显式使用
        # 创建管理员和用户（使用唯一邮箱）
        import time

        admin_email = f"admin_update_{int(time.time())}@test.com"
        admin_username = f"admin_update_{int(time.time())}"

        admin_id = create_user(
            admin_username,
            "Admin123!@#Test",
            role="admin",
            email=admin_email,
            is_test_user=True,
        )

        if admin_id is None:
            pytest.fail(f"Failed to create admin user: {admin_username}")

        import secrets

        unique_suffix = f"{int(time.time() * 1000)}_{secrets.token_hex(4)}"
        user_id = create_user(
            f"test_user_{unique_suffix}",
            "Password123!@#",
            role="user",
            email=f"test_{unique_suffix}@test.com",
            is_test_user=True,
        )

        if user_id is None:
            pytest.fail(f"create_user returned None for test_user_{unique_suffix}")

        # 更新订阅
        updates = {
            "user_type": "efficiency",
            "remaining_calculations": 1000,
        }

        result = update_user_subscription_admin(user_id, updates, admin_id)

        assert result is not None

        # 验证更新
        with get_db_connection() as (_, c):
            from db_adapter import adapt_sql

            sql = adapt_sql(
                "SELECT user_type, remaining_calculations FROM users WHERE id = ?"
            )
            c.execute(sql, (user_id,))
            row = c.fetchone()
            assert row[0] == "efficiency"
            assert row[1] == 1000

    def test_update_user_subscription_admin_empty_updates(self, clean_db):  # noqa: ARG002
        """测试空更新
        clean_db 参数是 pytest fixture，会自动清理测试数据
        """
        _ = clean_db  # 明确表示 fixture 参数未显式使用
        import time
        import secrets

        unique_suffix = f"{int(time.time() * 1000)}_{secrets.token_hex(4)}"
        admin_email = f"admin_empty_{unique_suffix}@test.com"
        admin_username = f"admin_empty_{unique_suffix}"

        admin_id = create_user(
            admin_username,
            "Admin123!@#Test",
            role="admin",
            email=admin_email,
            is_test_user=True,
        )

        if admin_id is None:
            pytest.fail(f"Failed to create admin user: {admin_username}")

        import secrets

        unique_suffix2 = f"{int(time.time() * 1000)}_{secrets.token_hex(4)}"
        user_id = create_user(
            f"test_user_{unique_suffix2}",
            "Password123!@#",
            role="user",
            email=f"test_{unique_suffix2}@test.com",
            is_test_user=True,
        )

        if user_id is None:
            pytest.fail(f"create_user returned None for test_user_{unique_suffix2}")

        result = update_user_subscription_admin(user_id, {}, admin_id)

        assert result is False


class TestFreezeUnfreezeUser:
    """测试用户冻结/解冻"""

    def test_freeze_user_success(self, clean_db):  # noqa: ARG002
        """测试成功冻结用户
        clean_db 参数是 pytest fixture，会自动清理测试数据
        """
        _ = clean_db  # 明确表示 fixture 参数未显式使用
        import time
        import secrets

        unique_suffix = f"{int(time.time() * 1000)}_{secrets.token_hex(4)}"
        admin_email = f"admin_freeze_{unique_suffix}@test.com"
        admin_username = f"admin_freeze_{unique_suffix}"

        admin_id = create_user(
            admin_username,
            "Admin123!@#Test",
            role="admin",
            email=admin_email,
            is_test_user=True,
        )

        if admin_id is None:
            pytest.fail(f"Failed to create admin user: {admin_username}")

        import secrets

        unique_suffix2 = f"{int(time.time() * 1000)}_{secrets.token_hex(4)}"
        user_id = create_user(
            f"test_user_{unique_suffix2}",
            "Password123!@#",
            role="user",
            email=f"test_{unique_suffix2}@test.com",
            is_test_user=True,
        )

        if user_id is None:
            pytest.fail(f"create_user returned None for test_user_{unique_suffix2}")

        # 冻结用户
        result = freeze_user(user_id, admin_id)

        assert result is not None

        # 验证用户已冻结
        with get_db_connection() as (conn, c):
            from db_adapter import adapt_sql

            # 检测数据库类型
            try:
                import psycopg2

                is_pg = isinstance(conn, psycopg2.extensions.connection)
            except (ImportError, AttributeError):
                is_pg = False

            sql = adapt_sql("SELECT is_frozen FROM users WHERE id = ?")
            c.execute(sql, (user_id,))
            row = c.fetchone()
            # PostgreSQL返回True/False，SQLite返回1/0
            if is_pg:
                assert row[0] is True
            else:
                assert row[0] == 1

    def test_unfreeze_user_success(self, clean_db):  # noqa: ARG002
        """测试成功解冻用户
        clean_db 参数是 pytest fixture，会自动清理测试数据
        """
        _ = clean_db  # 明确表示 fixture 参数未显式使用
        import time
        import secrets

        unique_suffix = f"{int(time.time() * 1000)}_{secrets.token_hex(4)}"
        admin_email = f"admin_unfreeze_{unique_suffix}@test.com"
        admin_username = f"admin_unfreeze_{unique_suffix}"

        admin_id = create_user(
            admin_username,
            "Admin123!@#Test",
            role="admin",
            email=admin_email,
            is_test_user=True,
        )

        if admin_id is None:
            pytest.fail(f"Failed to create admin user: {admin_username}")

        import secrets

        unique_suffix2 = f"{int(time.time() * 1000)}_{secrets.token_hex(4)}"
        user_id = create_user(
            f"test_user_{unique_suffix2}",
            "Password123!@#",
            role="user",
            email=f"test_{unique_suffix2}@test.com",
            is_test_user=True,
        )

        if user_id is None:
            pytest.fail(f"create_user returned None for test_user_{unique_suffix2}")

        # 先冻结
        freeze_user(user_id, admin_id)

        # 再解冻
        result = unfreeze_user(user_id, admin_id)

        assert result is not None

        # 验证用户已解冻
        with get_db_connection() as (conn, c):
            from db_adapter import adapt_sql

            # 检测数据库类型
            try:
                import psycopg2

                is_pg = isinstance(conn, psycopg2.extensions.connection)
            except (ImportError, AttributeError):
                is_pg = False

            sql = adapt_sql("SELECT is_frozen FROM users WHERE id = ?")
            c.execute(sql, (user_id,))
            row = c.fetchone()
            # PostgreSQL返回True/False，SQLite返回1/0
            if is_pg:
                assert row[0] is False
            else:
                assert row[0] == 0


class TestDeleteUserAdmin:
    """测试管理员删除用户"""

    def test_delete_user_admin_success(self, clean_db):  # noqa: ARG002
        """测试成功删除用户
        clean_db 参数是 pytest fixture，会自动清理测试数据
        """
        _ = clean_db  # 明确表示 fixture 参数未显式使用
        import time
        import secrets

        unique_suffix = f"{int(time.time() * 1000)}_{secrets.token_hex(4)}"
        admin_email = f"admin_delete_{unique_suffix}@test.com"
        admin_username = f"admin_delete_{unique_suffix}"

        admin_id = create_user(
            admin_username,
            "Admin123!@#Test",
            role="admin",
            email=admin_email,
            is_test_user=True,
        )

        if admin_id is None:
            pytest.fail(f"Failed to create admin user: {admin_username}")

        import secrets

        unique_suffix2 = f"{int(time.time() * 1000)}_{secrets.token_hex(4)}"
        user_id = create_user(
            f"test_user_{unique_suffix2}",
            "Password123!@#",
            role="user",
            email=f"test_{unique_suffix2}@test.com",
            is_test_user=True,
        )

        if user_id is None:
            pytest.fail(f"create_user returned None for test_user_{unique_suffix2}")

        # 删除用户
        result = delete_user_admin(user_id, admin_id)

        assert result is not None

        # 验证用户已删除
        with get_db_connection() as (_, c):
            from db_adapter import adapt_sql

            sql = adapt_sql("SELECT COUNT(*) FROM users WHERE id = ?")
            c.execute(sql, (user_id,))
            count = c.fetchone()[0]
            assert count == 0

    def test_delete_user_admin_protect_admin(self, clean_db):  # noqa: ARG002
        """测试保护管理员账号
        clean_db 参数是 pytest fixture，会自动清理测试数据
        """
        _ = clean_db  # 明确表示 fixture 参数未显式使用
        import time
        import secrets

        unique_suffix = f"{int(time.time() * 1000)}_{secrets.token_hex(4)}"
        admin_email = f"admin_protect_{unique_suffix}@test.com"
        admin_username = f"admin_protect_{unique_suffix}"

        admin_id = create_user(
            admin_username,
            "Admin123!@#Test",
            role="admin",
            email=admin_email,
            is_test_user=True,
        )

        if admin_id is None:
            pytest.fail(f"Failed to create admin user: {admin_username}")

        # 尝试删除管理员
        result = delete_user_admin(admin_id, admin_id)

        assert result is False
