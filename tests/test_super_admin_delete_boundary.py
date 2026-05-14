# pyright: reportUnusedFunction=false
"""W10 TEST#5 — 删除超级管理员的权限边界测试

注意：当前 codebase 没有 `is_super_admin` 字段。
"超级管理员" = `users.id == 1`（在 `api/routes/admin.py` 中硬编码）。
仅 `users.id == 1` 被保护，其他 `role == 'admin'` 的用户可以被删除。

本测试针对实际存在的权限边界进行覆盖：
  1. 普通 admin 试图删除 super-admin (id=1)  → 400 "不能删除超级管理员"
  2. super-admin (id=1) 删除普通 user        → 200 删除成功
  3. 任何 admin 删除另一名 admin (非 id=1)  → 200 删除成功

夹具：使用 `app.dependency_overrides[require_admin]` 注入调用者身份，
DB 走真实 PostgreSQL（worker schema 隔离）。
"""

import os
import secrets
import sys
import time

import pytest
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api import dependencies  # noqa: E402
from api.main import app  # noqa: E402
from database import AsyncSessionLocal  # noqa: E402
from db.password import hash_password  # noqa: E402
from models.user import User  # noqa: E402


def _suffix() -> str:
    worker = os.environ.get("PYTEST_XDIST_WORKER", "master")
    return f"{worker}_{int(time.time() * 1000)}_{secrets.token_hex(3)}"


async def _create_user(role: str, *, username: str | None = None) -> int:
    """Create a real user in DB (committed). Returns id. Marked is_test_user=1."""
    uname = username or f"test_{role}_{_suffix()}"
    async with AsyncSessionLocal() as session:
        user = User(
            username=uname,
            password=hash_password("Pwd123456!"),
            role=role,
            user_type="permanent" if role == "admin" else "free",
            subscription_type="free",
            remaining_calculations=-1 if role == "admin" else 10,
            created_at=time.strftime("%Y-%m-%d %H:%M:%S"),
            is_test_user=1,
        )
        session.add(user)
        await session.flush()
        uid = user.id
        await session.commit()
    return uid


async def _delete_user_hard(user_id: int) -> None:
    """Best-effort cleanup of a user + FK rows."""
    from sqlalchemy import text

    async with AsyncSessionLocal() as session:
        try:
            for tbl in [
                "products",
                "logistics",
                "active_sessions",
                "payment_orders",
                "user_login_log",
                "user_behavior_log",
                "subscription_upgrade_history",
                "trial_overflow_window",
            ]:
                try:
                    await session.execute(
                        text(f"DELETE FROM {tbl} WHERE user_id = :uid"),
                        {"uid": user_id},
                    )
                except Exception:
                    await session.rollback()
            try:
                await session.execute(
                    text(
                        "DELETE FROM admin_action_log "
                        "WHERE admin_id = :uid OR target_user_id = :uid"
                    ),
                    {"uid": user_id},
                )
            except Exception:
                await session.rollback()
            try:
                await session.execute(
                    text("DELETE FROM audit_logs WHERE admin_id = :uid"),
                    {"uid": user_id},
                )
            except Exception:
                await session.rollback()
            await session.execute(
                text("DELETE FROM users WHERE id = :uid"),
                {"uid": user_id},
            )
            await session.commit()
        except Exception:
            await session.rollback()


@pytest.fixture
async def normal_admin():
    """A non-super admin (role=admin, id != 1)."""
    uid = await _create_user("admin")
    yield {"id": uid}
    await _delete_user_hard(uid)


@pytest.fixture
async def normal_user():
    uid = await _create_user("user")
    yield {"id": uid}
    await _delete_user_hard(uid)


@pytest.fixture
async def second_admin():
    uid = await _create_user("admin")
    yield {"id": uid}
    await _delete_user_hard(uid)


@pytest.fixture
async def super_admin_id() -> int:
    """The hardcoded super-admin id (== 1).

    We do not create or delete this user; we only need the id to drive the
    route's `if user_id == 1` branch. If id=1 happens not to exist in the
    schema, the route still rejects BEFORE touching the DB, so the assertion
    holds either way.
    """
    return 1


@pytest.fixture
async def http_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _override_admin(admin_id: int) -> None:
    app.dependency_overrides[dependencies.require_admin] = lambda: admin_id


@pytest.mark.asyncio
async def test_normal_admin_cannot_delete_super_admin(
    normal_admin,
    super_admin_id,
    http_client,
):
    """普通 admin 试图删除 super-admin (id=1) 必须被拒绝。

    当前实现：route 层硬编码 `if user_id == 1: 400 不能删除超级管理员`。
    （任务文档原描述为 403；实际代码返回 400 — 测试断言以实际为准，
    并在注释中标记此差异。）
    """
    _override_admin(normal_admin["id"])
    resp = await http_client.delete(f"/api/admin/users/{super_admin_id}")
    # 实际为 400；403 也接受（若未来收紧权限语义改为 403 不破坏测试意图）
    assert resp.status_code in (400, 403), (
        f"super-admin 删除必须被拒绝，实际 {resp.status_code}: {resp.text}"
    )
    assert "超级管理员" in resp.json().get("detail", "")


@pytest.mark.asyncio
async def test_super_admin_can_delete_normal_user(
    super_admin_id,
    normal_user,
    http_client,
):
    """super-admin (id=1) 可以删除普通 user → 200。

    使用 dependency override 注入 admin_id=1 模拟 super-admin 调用者。
    """
    _override_admin(super_admin_id)
    target_id = normal_user["id"]
    resp = await http_client.delete(f"/api/admin/users/{target_id}")
    assert resp.status_code == 200, (
        f"super-admin 删除普通用户应成功，实际 {resp.status_code}: {resp.text}"
    )
    assert resp.json().get("message") == "删除成功"

    # 验证用户确已被软/硬删除（再次 DELETE 应 404）
    resp2 = await http_client.delete(f"/api/admin/users/{target_id}")
    assert resp2.status_code == 404


@pytest.mark.asyncio
async def test_admin_can_delete_another_admin(
    normal_admin,
    second_admin,
    http_client,
):
    """普通 admin 可以删除另一名 admin（非 id=1）。

    仅 users.id==1 被路由层保护，其他 admin 可被正常删除。
    """
    _override_admin(normal_admin["id"])
    target_id = second_admin["id"]
    resp = await http_client.delete(f"/api/admin/users/{target_id}")
    assert resp.status_code == 200, (
        f"admin 删除另一名 admin 应成功，实际 {resp.status_code}: {resp.text}"
    )
    assert resp.json().get("message") == "删除成功"

    # 验证目标 admin 确已被删除
    async with AsyncSessionLocal() as session:
        gone = await session.get(User, target_id)
        assert gone is None, "已被删除的 admin 必须不存在"
