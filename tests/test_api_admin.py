from api.dependencies import require_admin
from api.main import app
from db.password import hash_password
from models.user import User


def _admin_override(admin_id):
    app.dependency_overrides[require_admin] = lambda: admin_id


def _clear_overrides():
    app.dependency_overrides.clear()


async def test_reset_other_admin_password_blocked(client, test_admin, db_session):
    admin_id = test_admin["id"]
    other_admin = User(
        username=f"test_other_admin_{admin_id}",
        password=hash_password("AdminP@ss123456"),
        role="admin",
        user_type="permanent",
        subscription_type="free",
        remaining_calculations=-1,
        created_at="2026-01-01 00:00:00",
        is_test_user=1,
    )
    db_session.add(other_admin)
    await db_session.flush()
    await db_session.commit()

    _admin_override(admin_id)
    try:
        resp = await client.post(f"/api/admin/users/{other_admin.id}/reset-password")
        assert resp.status_code == 403
        assert resp.json()["detail"] == "禁止重置其他管理员密码"
    finally:
        _clear_overrides()
