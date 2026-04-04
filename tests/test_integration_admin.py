import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.dependencies import require_admin

client = TestClient(app)


def _admin_override(admin_id):
    app.dependency_overrides[require_admin] = lambda: admin_id


def _clear_overrides():
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET /api/admin/users — list with pagination
# ---------------------------------------------------------------------------


class TestAdminListUsers:
    def test_list_users_pagination(self, test_admin):
        admin_id = test_admin["id"]
        _admin_override(admin_id)
        try:
            resp = client.get("/api/admin/users?page=1&page_size=20")
            assert resp.status_code == 200
            data = resp.json()
            assert "users" in data
            assert "total" in data
            assert "page" in data
            assert "page_size" in data
            assert data["page"] == 1
            assert data["page_size"] == 20
            assert isinstance(data["users"], list)
            assert data["total"] >= 0
        finally:
            _clear_overrides()

    def test_list_users_default_params(self, test_admin):
        admin_id = test_admin["id"]
        _admin_override(admin_id)
        try:
            resp = client.get("/api/admin/users")
            assert resp.status_code == 200
            data = resp.json()
            assert "users" in data
        finally:
            _clear_overrides()

    def test_list_users_contains_created_user(self, test_admin, test_user):
        admin_id = test_admin["id"]
        _admin_override(admin_id)
        try:
            resp = client.get(f"/api/admin/users?keyword={test_user['username']}")
            assert resp.status_code == 200
            data = resp.json()
            usernames = [u["username"] for u in data["users"]]
            assert test_user["username"] in usernames
        finally:
            _clear_overrides()


# ---------------------------------------------------------------------------
# GET /api/admin/users?keyword= — search users
# ---------------------------------------------------------------------------


class TestAdminSearchUsers:
    def test_search_by_keyword(self, test_admin, test_user):
        admin_id = test_admin["id"]
        _admin_override(admin_id)
        try:
            keyword = test_user["username"][:10]
            resp = client.get(f"/api/admin/users?keyword={keyword}")
            assert resp.status_code == 200
            data = resp.json()
            assert "users" in data
            assert "total" in data
            for u in data["users"]:
                assert keyword.lower() in u["username"].lower()
        finally:
            _clear_overrides()

    def test_search_no_results(self, test_admin):
        admin_id = test_admin["id"]
        _admin_override(admin_id)
        try:
            resp = client.get("/api/admin/users?keyword=zzz_nonexistent_xyz_9999")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 0
            assert data["users"] == []
        finally:
            _clear_overrides()


# ---------------------------------------------------------------------------
# POST /api/admin/users — create user
# ---------------------------------------------------------------------------


class TestAdminCreateUser:
    def test_create_user_success(self, test_admin):
        import time

        admin_id = test_admin["id"]
        _admin_override(admin_id)
        created_id = None
        try:
            username = f"int_test_user_{int(time.time() * 1000)}"
            payload = {
                "username": username,
                "password": "TestPass@123",
                "role": "user",
                "user_type": "free",
            }
            resp = client.post("/api/admin/users", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["username"] == username
            assert data["role"] == "user"
            assert data["user_type"] == "free"
            assert "id" in data
            created_id = data["id"]
        finally:
            _clear_overrides()
            if created_id:
                _admin_override(admin_id)
                client.delete(f"/api/admin/users/{created_id}")
                _clear_overrides()

    def test_create_user_response_fields(self, test_admin):
        import time

        admin_id = test_admin["id"]
        _admin_override(admin_id)
        created_id = None
        try:
            username = f"int_test_fields_{int(time.time() * 1000)}"
            payload = {
                "username": username,
                "password": "TestPass@123",
                "role": "admin",
                "user_type": "permanent",
            }
            resp = client.post("/api/admin/users", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["role"] == "admin"
            assert data["user_type"] == "permanent"
            created_id = data["id"]
        finally:
            _clear_overrides()
            if created_id:
                _admin_override(admin_id)
                client.delete(f"/api/admin/users/{created_id}")
                _clear_overrides()


# ---------------------------------------------------------------------------
# PUT /api/admin/users/{user_id} — update user
# ---------------------------------------------------------------------------


class TestAdminUpdateUser:
    def test_update_user_role(self, test_admin, test_user):
        admin_id = test_admin["id"]
        user_id = test_user["id"]
        _admin_override(admin_id)
        try:
            resp = client.put(
                f"/api/admin/users/{user_id}",
                json={"role": "admin", "user_type": "permanent"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["role"] == "admin"
            assert data["user_type"] == "permanent"
        finally:
            _clear_overrides()

    def test_update_user_not_found(self, test_admin):
        admin_id = test_admin["id"]
        _admin_override(admin_id)
        try:
            resp = client.put(
                "/api/admin/users/999999999",
                json={"role": "user"},
            )
            assert resp.status_code == 404
        finally:
            _clear_overrides()

    def test_update_user_partial(self, test_admin, test_user):
        admin_id = test_admin["id"]
        user_id = test_user["id"]
        _admin_override(admin_id)
        try:
            resp = client.put(
                f"/api/admin/users/{user_id}",
                json={"user_type": "monthly"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["user_type"] == "monthly"
        finally:
            _clear_overrides()


# ---------------------------------------------------------------------------
# POST /api/admin/users/{user_id}/reset-password
# ---------------------------------------------------------------------------


class TestAdminResetPassword:
    def test_reset_password_success(self, test_admin, test_user):
        admin_id = test_admin["id"]
        user_id = test_user["id"]
        _admin_override(admin_id)
        try:
            resp = client.post(f"/api/admin/users/{user_id}/reset-password")
            assert resp.status_code == 200
            data = resp.json()
            assert "message" in data
            assert "密码已重置为: " in data["message"]
            reset_password = data["message"].replace("密码已重置为: ", "")
            assert len(reset_password) >= 12
            assert reset_password != "123456"
        finally:
            _clear_overrides()

    def test_reset_password_not_found(self, test_admin):
        admin_id = test_admin["id"]
        _admin_override(admin_id)
        try:
            resp = client.post("/api/admin/users/999999999/reset-password")
            assert resp.status_code == 404
        finally:
            _clear_overrides()


# ---------------------------------------------------------------------------
# DELETE /api/admin/users/{user_id}
# ---------------------------------------------------------------------------


class TestAdminDeleteUser:
    def test_delete_nonexistent_user(self, test_admin):
        admin_id = test_admin["id"]
        _admin_override(admin_id)
        try:
            resp = client.delete("/api/admin/users/999999999")
            assert resp.status_code == 404
        finally:
            _clear_overrides()

    def test_delete_super_admin_blocked(self, test_admin):
        admin_id = test_admin["id"]
        _admin_override(admin_id)
        try:
            resp = client.delete("/api/admin/users/1")
            assert resp.status_code == 400
        finally:
            _clear_overrides()

    def test_delete_user_success(self, test_admin):
        import time

        admin_id = test_admin["id"]
        _admin_override(admin_id)
        created_id = None
        try:
            username = f"int_del_user_{int(time.time() * 1000)}"
            payload = {
                "username": username,
                "password": "TestPass@123",
                "role": "user",
                "user_type": "free",
            }
            create_resp = client.post("/api/admin/users", json=payload)
            assert create_resp.status_code == 201
            created_id = create_resp.json()["id"]

            del_resp = client.delete(f"/api/admin/users/{created_id}")
            assert del_resp.status_code == 200
            data = del_resp.json()
            assert "message" in data
            created_id = None

            get_resp = client.get(f"/api/admin/users?keyword={username}")
            assert get_resp.json()["total"] == 0
        finally:
            _clear_overrides()
            if created_id:
                _admin_override(admin_id)
                client.delete(f"/api/admin/users/{created_id}")
                _clear_overrides()
