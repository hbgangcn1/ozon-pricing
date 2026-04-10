# -*- coding: utf-8 -*-
"""
管理员功能综合测试
覆盖管理员认证、用户管理、订阅管理、冻结/解冻、删除等功能
"""

import secrets
import sys
import os
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import AsyncSessionLocal
from db.users import create_user
from db.admin import (
    authenticate_admin,
    get_all_users,
    get_user_detail,
    update_user_subscription_admin,
    freeze_user,
    unfreeze_user,
    delete_user_admin,
)
from models.user import User


def _suffix():
    return f"{int(time.time() * 1000)}_{secrets.token_hex(4)}"


class TestAdminAuthentication:
    """测试管理员认证"""

    async def test_authenticate_admin_success(self, clean_db):
        """测试管理员认证成功
        clean_db 参数是 pytest fixture，会自动清理测试数据
        """
        sfx = _suffix()
        username = f"admin_user_{sfx}"
        password = "Admin123!@#Test"
        email = f"admin_{sfx}@test.com"

        async with AsyncSessionLocal() as session:
            user_id = await create_user(
                session,
                username,
                password,
                role="admin",
                email=email,
                is_test_user=True,
            )
            await session.commit()

            if user_id is None:
                pytest.fail(f"Failed to create admin user: {username}")

            result = await authenticate_admin(session, username, password)

        assert result is not None
        assert result["role"] == "admin"
        assert result["username"] == username

    async def test_authenticate_admin_wrong_password(self, clean_db):
        """测试管理员认证 - 密码错误
        clean_db 参数是 pytest fixture，会自动清理测试数据
        """
        sfx = _suffix()
        username = f"admin_wrong_{sfx}"
        password = "Admin123!@#Test"
        email = f"admin_wrong_{sfx}@test.com"

        async with AsyncSessionLocal() as session:
            user_id = await create_user(
                session,
                username,
                password,
                role="admin",
                email=email,
                is_test_user=True,
            )
            await session.commit()

            if user_id is None:
                pytest.fail(f"Failed to create admin user: {username}")

            result = await authenticate_admin(session, username, "WrongPassword123!@#")

        assert result is None

    async def test_authenticate_admin_user_not_found(self, clean_db):
        """测试管理员认证 - 用户不存在
        clean_db 参数是 pytest fixture，会自动清理测试数据
        """
        async with AsyncSessionLocal() as session:
            result = await authenticate_admin(session, "nonexistent", "password")
        assert result is None

    async def test_authenticate_admin_not_admin_role(self, clean_db):
        """测试管理员认证 - 非管理员角色
        clean_db 参数是 pytest fixture，会自动清理测试数据
        """
        sfx = _suffix()
        username = f"regular_{sfx}"
        password = "User123!@#Test"
        email = f"regular_{sfx}@test.com"

        async with AsyncSessionLocal() as session:
            user_id = await create_user(
                session,
                username,
                password,
                role="user",
                email=email,
                is_test_user=True,
            )
            await session.commit()

            if user_id is None:
                pytest.fail(f"Failed to create regular user: {username}")

            result = await authenticate_admin(session, username, password)

        assert result is None


class TestGetAllUsers:
    """测试获取所有用户列表"""

    async def test_get_all_users_basic(self, clean_db):
        """测试基本用户列表查询
        clean_db 参数是 pytest fixture，会自动清理测试数据
        """
        sfx = _suffix()

        async with AsyncSessionLocal() as session:
            for i in range(5):
                await create_user(
                    session,
                    f"user_{sfx}_{i}",
                    "Password123!@#",
                    role="user",
                    email=f"user_{sfx}_{i}@test.com",
                    is_test_user=True,
                )
            await session.commit()

            result = await get_all_users(session, page=1, per_page=10)

        assert "users" in result
        assert "total_count" in result
        assert "total_pages" in result
        assert "current_page" in result
        assert len(result["users"]) >= 5

    async def test_get_all_users_with_search(self, clean_db):
        """测试带搜索的用户列表查询
        clean_db 参数是 pytest fixture，会自动清理测试数据
        """
        sfx = _suffix()

        async with AsyncSessionLocal() as session:
            u1 = await create_user(
                session,
                f"john_doe_{sfx}",
                "Password123!@#",
                role="user",
                email=f"john_{sfx}@test.com",
                is_test_user=True,
            )
            u2 = await create_user(
                session,
                f"jane_doe_{sfx}",
                "Password123!@#",
                role="user",
                email=f"jane_{sfx}@test.com",
                is_test_user=True,
            )
            u3 = await create_user(
                session,
                f"bob_smith_{sfx}",
                "Password123!@#",
                role="user",
                email=f"bob_{sfx}@test.com",
                is_test_user=True,
            )
            await session.commit()

            if u1 is None or u2 is None or u3 is None:
                pytest.fail(f"Failed to create test users: u1={u1}, u2={u2}, u3={u3}")

            result = await get_all_users(session, page=1, per_page=10, search="john")

        assert result.get("total_count", result.get("total", 0)) >= 1
        assert any(
            "john" in user["username"].lower() or "john" in user["email"].lower()
            for user in result["users"]
        )

    async def test_get_all_users_with_user_type_filter(self, clean_db):
        """测试按用户类型过滤
        clean_db 参数是 pytest fixture，会自动清理测试数据
        """
        sfx = _suffix()
        username = f"free_user_{sfx}"

        async with AsyncSessionLocal() as session:
            user_id = await create_user(
                session,
                username,
                "Password123!@#",
                role="user",
                email=f"free_{sfx}@test.com",
                is_test_user=True,
            )
            await session.commit()

            if user_id is None:
                pytest.fail(f"Failed to create user: {username}")

            user = await session.get(User, user_id)
            user.user_type = "free"
            await session.commit()

            result = await get_all_users(
                session, page=1, per_page=10, user_type_filter="free"
            )

        assert all(u["user_type"] == "free" for u in result["users"])

    async def test_get_all_users_with_status_filter_expired(self, clean_db):
        """测试按过期状态过滤
        clean_db 参数是 pytest fixture，会自动清理测试数据
        """
        sfx = _suffix()
        username = f"expired_user_{sfx}"
        email = f"expired_{sfx}@test.com"
        expired_time = int(time.time()) - 86400

        async with AsyncSessionLocal() as session:
            user_id = await create_user(
                session,
                username,
                "Password123!@#",
                role="user",
                email=email,
                is_test_user=True,
            )
            await session.commit()

            if user_id is None:
                pytest.fail(f"Failed to create expired user: {username}")

            user = await session.get(User, user_id)
            user.subscription_expires = expired_time
            await session.commit()

            result = await get_all_users(
                session,
                page=1,
                per_page=10,
                search=username,
                status_filter="expired",
            )

        assert any(u["username"] == username for u in result["users"])

    async def test_get_all_users_pagination(self, clean_db):
        """测试分页功能
        clean_db 参数是 pytest fixture，会自动清理测试数据
        """
        sfx = _suffix()

        async with AsyncSessionLocal() as session:
            created_user_ids = []
            for i in range(25):
                uid = await create_user(
                    session,
                    f"user_{sfx}_{i}",
                    "Password123!@#",
                    role="user",
                    email=f"user_{sfx}_{i}@test.com",
                    is_test_user=True,
                )
                if uid is not None:
                    created_user_ids.append(uid)
            await session.commit()

            created_count = len(created_user_ids)
            if created_count < 10:
                pytest.fail(f"Only created {created_count} users, need at least 10")

            search_keyword = f"user_{sfx}"
            result1 = await get_all_users(
                session, page=1, per_page=10, search=search_keyword
            )
            created_in_p1 = [u for u in result1["users"] if u["id"] in created_user_ids]

            if len(created_in_p1) < min(10, created_count):
                pytest.fail(
                    f"Expected >= {min(10, created_count)} created users in page 1, "
                    f"got {len(created_in_p1)}. Total: {len(result1['users'])}"
                )

            assert result1["current_page"] == 1

            result2 = await get_all_users(
                session, page=2, per_page=10, search=search_keyword
            )
            created_in_p2 = [u for u in result2["users"] if u["id"] in created_user_ids]

            if created_count > 10:
                expected_min = min(10, created_count - 10)
                if len(created_in_p2) < expected_min:
                    pytest.fail(
                        f"Expected >= {expected_min} created users in page 2, "
                        f"got {len(created_in_p2)}."
                    )

            assert result2["current_page"] == 2


class TestGetUserDetail:
    """测试获取用户详细信息"""

    async def test_get_user_detail_success(self, clean_db):
        """测试成功获取用户详情
        clean_db 参数是 pytest fixture，会自动清理测试数据
        """
        sfx = _suffix()
        username = f"test_user_{sfx}"
        email = f"test_{sfx}@test.com"

        async with AsyncSessionLocal() as session:
            user_id = await create_user(
                session,
                username,
                "Password123!@#",
                role="user",
                email=email,
                is_test_user=True,
            )
            await session.commit()

            if user_id is None:
                pytest.fail(f"create_user returned None for {username}")

            detail = await get_user_detail(session, user_id)

        assert detail is not None
        assert detail["id"] == user_id
        assert detail["username"] == username
        assert detail["email"] == email

    async def test_get_user_detail_not_found(self, clean_db):
        """测试用户不存在
        clean_db 参数是 pytest fixture，会自动清理测试数据
        """
        async with AsyncSessionLocal() as session:
            detail = await get_user_detail(session, 99999)
        assert detail is None


class TestUpdateUserSubscriptionAdmin:
    """测试管理员更新用户订阅"""

    async def test_update_user_subscription_admin_success(self, clean_db):
        """测试成功更新订阅
        clean_db 参数是 pytest fixture，会自动清理测试数据
        """
        sfx = _suffix()
        sfx2 = _suffix()

        async with AsyncSessionLocal() as session:
            admin_id = await create_user(
                session,
                f"admin_update_{sfx}",
                "Admin123!@#Test",
                role="admin",
                email=f"admin_update_{sfx}@test.com",
                is_test_user=True,
            )
            await session.commit()

            if admin_id is None:
                pytest.fail(f"Failed to create admin user: admin_update_{sfx}")

            user_id = await create_user(
                session,
                f"test_user_{sfx2}",
                "Password123!@#",
                role="user",
                email=f"test_{sfx2}@test.com",
                is_test_user=True,
            )
            await session.commit()

            if user_id is None:
                pytest.fail(f"create_user returned None for test_user_{sfx2}")

            updates = {"user_type": "efficiency", "remaining_calculations": 1000}
            result = await update_user_subscription_admin(
                session, user_id, updates, admin_id
            )
            await session.commit()

            assert result is not None

            user = await session.get(User, user_id)
            assert user.user_type == "efficiency"
            assert user.remaining_calculations == 1000

    async def test_update_user_subscription_admin_empty_updates(self, clean_db):
        """测试空更新
        clean_db 参数是 pytest fixture，会自动清理测试数据
        """
        sfx = _suffix()
        sfx2 = _suffix()

        async with AsyncSessionLocal() as session:
            admin_id = await create_user(
                session,
                f"admin_empty_{sfx}",
                "Admin123!@#Test",
                role="admin",
                email=f"admin_empty_{sfx}@test.com",
                is_test_user=True,
            )
            await session.commit()

            if admin_id is None:
                pytest.fail(f"Failed to create admin user: admin_empty_{sfx}")

            user_id = await create_user(
                session,
                f"test_user_{sfx2}",
                "Password123!@#",
                role="user",
                email=f"test_{sfx2}@test.com",
                is_test_user=True,
            )
            await session.commit()

            if user_id is None:
                pytest.fail(f"create_user returned None for test_user_{sfx2}")

            result = await update_user_subscription_admin(
                session, user_id, {}, admin_id
            )

        assert result is False


class TestFreezeUnfreezeUser:
    """测试用户冻结/解冻"""

    async def test_freeze_user_success(self, clean_db):
        """测试成功冻结用户
        clean_db 参数是 pytest fixture，会自动清理测试数据
        """
        sfx = _suffix()
        sfx2 = _suffix()

        async with AsyncSessionLocal() as session:
            admin_id = await create_user(
                session,
                f"admin_freeze_{sfx}",
                "Admin123!@#Test",
                role="admin",
                email=f"admin_freeze_{sfx}@test.com",
                is_test_user=True,
            )
            await session.commit()

            if admin_id is None:
                pytest.fail(f"Failed to create admin user: admin_freeze_{sfx}")

            user_id = await create_user(
                session,
                f"test_user_{sfx2}",
                "Password123!@#",
                role="user",
                email=f"test_{sfx2}@test.com",
                is_test_user=True,
            )
            await session.commit()

            if user_id is None:
                pytest.fail(f"create_user returned None for test_user_{sfx2}")

            result = await freeze_user(session, user_id, admin_id)
            await session.commit()

            assert result is not None

            user = await session.get(User, user_id)
            assert user.is_frozen == 1

    async def test_unfreeze_user_success(self, clean_db):
        """测试成功解冻用户
        clean_db 参数是 pytest fixture，会自动清理测试数据
        """
        sfx = _suffix()
        sfx2 = _suffix()

        async with AsyncSessionLocal() as session:
            admin_id = await create_user(
                session,
                f"admin_unfreeze_{sfx}",
                "Admin123!@#Test",
                role="admin",
                email=f"admin_unfreeze_{sfx}@test.com",
                is_test_user=True,
            )
            await session.commit()

            if admin_id is None:
                pytest.fail(f"Failed to create admin user: admin_unfreeze_{sfx}")

            user_id = await create_user(
                session,
                f"test_user_{sfx2}",
                "Password123!@#",
                role="user",
                email=f"test_{sfx2}@test.com",
                is_test_user=True,
            )
            await session.commit()

            if user_id is None:
                pytest.fail(f"create_user returned None for test_user_{sfx2}")

            await freeze_user(session, user_id, admin_id)
            await session.commit()

            result = await unfreeze_user(session, user_id, admin_id)
            await session.commit()

            assert result is not None

            user = await session.get(User, user_id)
            assert user.is_frozen == 0


class TestDeleteUserAdmin:
    """测试管理员删除用户"""

    async def test_delete_user_admin_success(self, clean_db):
        """测试成功删除用户
        clean_db 参数是 pytest fixture，会自动清理测试数据
        """
        sfx = _suffix()
        sfx2 = _suffix()

        async with AsyncSessionLocal() as session:
            admin_id = await create_user(
                session,
                f"admin_delete_{sfx}",
                "Admin123!@#Test",
                role="admin",
                email=f"admin_delete_{sfx}@test.com",
                is_test_user=True,
            )
            await session.commit()

            if admin_id is None:
                pytest.fail(f"Failed to create admin user: admin_delete_{sfx}")

            user_id = await create_user(
                session,
                f"test_user_{sfx2}",
                "Password123!@#",
                role="user",
                email=f"test_{sfx2}@test.com",
                is_test_user=True,
            )
            await session.commit()

            if user_id is None:
                pytest.fail(f"create_user returned None for test_user_{sfx2}")

            result = await delete_user_admin(session, user_id, admin_id)
            await session.commit()

            assert result is not None

            user = await session.get(User, user_id)
            assert user is None

    async def test_delete_user_admin_protect_admin(self, clean_db):
        """测试保护管理员账号
        clean_db 参数是 pytest fixture，会自动清理测试数据
        """
        sfx = _suffix()

        async with AsyncSessionLocal() as session:
            admin_id = await create_user(
                session,
                f"admin_protect_{sfx}",
                "Admin123!@#Test",
                role="admin",
                email=f"admin_protect_{sfx}@test.com",
                is_test_user=True,
            )
            await session.commit()

            if admin_id is None:
                pytest.fail(f"Failed to create admin user: admin_protect_{sfx}")

            result = await delete_user_admin(session, admin_id, admin_id)

        assert result is False
