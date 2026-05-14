"""Route smoke tests for API endpoints."""

# pyright: reportUnusedFunction=false

import os
import sys
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("ALLOWED_ORIGINS", "http://testserver")

from fastapi.testclient import TestClient  # noqa: E402
from api.main import app  # noqa: E402
from api import dependencies  # noqa: E402
from database import get_db  # noqa: E402


@pytest.fixture(autouse=True)
def _patch_recalculate():
    with patch(
        "api.routes.logistics.recalculate_priority_groups",
        new=AsyncMock(),
    ):
        yield


MOCK_USER = {
    "id": 1,
    "username": "testuser",
    "role": "admin",
    "user_type": "enterprise",
    "remaining_calculations": 100,
}

client = TestClient(app, raise_server_exceptions=False)


# Priority 1 (correctness): function-scoped autouse override prevents cross-file
# pollution. Other test files (test_api_logistics_*) call
# `app.dependency_overrides.clear()/pop()` in their teardown, which previously
# wiped module-level overrides set here, causing 401 in subsequent tests when
# loadscope ordering interleaved them. monkeypatch.setitem auto-restores prior
# state per test. See openspec/changes/fix-preexisting-test-failures/.
@pytest.fixture(autouse=True)
def _mock_auth_dependencies(monkeypatch):
    monkeypatch.setitem(
        app.dependency_overrides,
        dependencies.get_current_user_id,
        lambda: 1,
    )
    monkeypatch.setitem(
        app.dependency_overrides,
        dependencies.require_admin,
        lambda: 1,
    )
    monkeypatch.setitem(
        app.dependency_overrides,
        dependencies.get_current_user,
        lambda: MOCK_USER,
    )


@pytest.fixture(autouse=True)
def _allow_testserver_origin(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", "http://testserver")


@pytest.fixture(autouse=True)
def _reset_username_check_limiter():
    from api.middleware.username_check_limiter import username_check_limiter
    from api.routes.auth import recover_start_limiter, recover_verify_limiter

    username_check_limiter.reset()
    recover_start_limiter.reset()
    recover_verify_limiter.reset()
    yield
    username_check_limiter.reset()
    recover_start_limiter.reset()
    recover_verify_limiter.reset()


@pytest.fixture(autouse=True)
def _preserve_username_limiter_ip_test_isolation(monkeypatch):
    from api.routes.auth import login as auth_login

    def _test_client_ip(request):
        return request.headers.get("X-Forwarded-For", "testclient").split(",")[0].strip()

    monkeypatch.setattr(auth_login, "get_username_check_client_ip", _test_client_ip)


def _logistics_row():
    return {
        "id": 1,
        "user_id": 1,
        "name": "Test",
        "type": "land",
        "min_days": 1,
        "max_days": 10,
        "price_limit_cny": 0,
        "price_min_cny": 0,
        "base_fee": 0,
        "min_weight": 0,
        "max_weight": 100000,
        "max_sum_of_sides": 0,
        "max_longest_side": 0,
        "max_second_side": 0,
        "max_third_side": 0,
        "min_second_side": 0,
        "min_length": 0,
        "max_cylinder_sum": 0,
        "min_cylinder_sum": 0,
        "max_cylinder_length": 0,
        "min_cylinder_length": 0,
        "volume_mode": "none",
        "longest_side_threshold": 0,
        "sum_of_sides_threshold": 0,
        "allow_battery": 0,
        "allow_liquid": 0,
        "battery_capacity_limit_wh": 0,
        "require_msds": 0,
        "fee_mode": "base_weight",
        "first_fee": 0,
        "first_weight_g": 0,
        "continue_fee": 0,
        "continue_unit": "g",
        "volume_coefficient": 5000,
        "delivery_method": "pickup",
        "priority_group": "D",
        "is_active": 1,
        "fulfillment_type": "rfbs",
        "destination": "RU",
        "fbp_service_level": None,
        "fbp_company": None,
        "is_smart": 0,
    }


class TestRootEndpoints:
    def test_root(self):
        r = client.get("/")
        assert r.status_code == 200
        assert "version" in r.json()

    @patch("api.main.engine")
    def test_health(self, mock_engine):
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        mock_engine.connect.return_value = mock_cm
        r = client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] in ("ok", "degraded")
        assert body["db_ok"] is True


class TestAuth:
    @patch("api.routes.auth.verify_user", new_callable=AsyncMock)
    @patch("api.routes.auth.deactivate_all_sessions", new_callable=AsyncMock)
    @patch("api.routes.auth.insert_session", new_callable=AsyncMock)
    @patch("api.routes.auth.create_refresh_token")
    @patch("api.routes.auth.create_access_token")
    def test_login_success(
        self,
        mock_access_token,
        mock_refresh_token,
        mock_insert_session,
        mock_deactivate_all,
        mock_verify,
    ):
        mock_verify.return_value = {
            "id": 1,
            "username": "u",
            "role": "user",
            "user_type": "free",
            "remaining_calculations": 10,
        }
        mock_access_token.return_value = "tok123"
        mock_refresh_token.return_value = "refresh123"
        r = client.post("/api/auth/login", json={"username": "u", "password": "p"})
        assert r.status_code == 200
        assert r.json()["access_token"] == "tok123"
        assert r.json()["user"]["has_security_question"] is False
        set_cookie = r.headers["set-cookie"]
        assert "access_token=tok123" in set_cookie
        assert "refresh_token=refresh123" in set_cookie
        assert "csrf_token=" in set_cookie
        assert "Max-Age=900" in set_cookie
        assert "Max-Age=604800" in set_cookie
        mock_insert_session.assert_awaited_once()
        mock_deactivate_all.assert_awaited_once()

    @patch("api.routes.auth.verify_user", new_callable=AsyncMock)
    @patch("api.routes.auth.deactivate_all_sessions", new_callable=AsyncMock)
    @patch("api.routes.auth.insert_session", new_callable=AsyncMock)
    @patch("api.routes.auth.create_refresh_token")
    @patch("api.routes.auth.create_access_token")
    def test_login_returns_has_security_question_true_when_security_q1_set(
        self,
        mock_access_token,
        mock_refresh_token,
        mock_insert_session,
        mock_deactivate_all,
        mock_verify,
    ):
        mock_verify.return_value = {
            "id": 2,
            "username": "u2",
            "role": "user",
            "user_type": "free",
            "remaining_calculations": 5,
            "security_q1": "您母亲的姓名是？",
        }
        mock_access_token.return_value = "tokQ"
        mock_refresh_token.return_value = "refQ"
        r = client.post("/api/auth/login", json={"username": "u2", "password": "p"})
        assert r.status_code == 200
        assert r.json()["user"]["has_security_question"] is True

    @patch("api.routes.auth.verify_user", new_callable=AsyncMock)
    @patch("api.routes.auth.login.bcrypt.checkpw")
    def test_login_bad_credentials(self, mock_checkpw, mock_verify):
        mock_verify.return_value = None
        r = client.post("/api/auth/login", json={"username": "u", "password": "wrong"})
        assert r.status_code == 401
        mock_checkpw.assert_called_once()

    @patch("api.routes.auth.get_user_by_id", new_callable=AsyncMock)
    @patch("api.routes.auth.reset_user_daily_calculations", new_callable=AsyncMock)
    @patch("api.routes.auth.verify_user", new_callable=AsyncMock)
    @patch("api.routes.auth.deactivate_all_sessions", new_callable=AsyncMock)
    @patch("api.routes.auth.insert_session", new_callable=AsyncMock)
    @patch("api.routes.auth.create_refresh_token")
    @patch("api.routes.auth.create_access_token")
    def test_login_invokes_daily_reset_and_returns_refreshed_count(
        self,
        mock_access_token,
        mock_refresh_token,
        mock_insert_session,
        mock_deactivate_all,
        mock_verify,
        mock_reset,
        mock_get_user_by_id,
    ):
        # daily-calc-reset task 3.3: login must call reset_user_daily_calculations
        # and surface the post-reset remaining_calculations in the response.
        mock_verify.return_value = {
            "id": 7,
            "username": "limited_user",
            "role": "user",
            "user_type": "free",
            "remaining_calculations": 0,
        }
        mock_reset.return_value = True
        refreshed = MagicMock()
        refreshed.remaining_calculations = 10
        refreshed.trial_used = 0
        refreshed.trial_started_at = 0
        refreshed.trial_expires_at = 0
        refreshed.trial_plan_at_start = ""
        mock_get_user_by_id.return_value = refreshed
        mock_access_token.return_value = "tokR"
        mock_refresh_token.return_value = "refR"
        r = client.post(
            "/api/auth/login",
            json={"username": "limited_user", "password": "p"},
        )
        assert r.status_code == 200
        mock_reset.assert_awaited_once()
        reset_args = mock_reset.await_args
        assert reset_args.args[1] == 7
        assert r.json()["user"]["remaining_calculations"] == 10

    @patch("api.routes.auth.verify_user", new_callable=AsyncMock)
    @patch("api.routes.auth.deactivate_all_sessions", new_callable=AsyncMock)
    @patch("api.routes.auth.insert_session", new_callable=AsyncMock)
    @patch("api.routes.auth.create_refresh_token")
    @patch("api.routes.auth.create_access_token")
    def test_logout(
        self,
        mock_access_token,
        mock_refresh_token,
        mock_insert_session,
        mock_deactivate_all,
        mock_verify,
    ):
        mock_verify.return_value = {
            "id": 1,
            "username": "u",
            "role": "user",
            "user_type": "free",
            "remaining_calculations": 10,
        }
        mock_access_token.return_value = "tok123"
        mock_refresh_token.return_value = "refresh123"
        login_resp = client.post(
            "/api/auth/login",
            json={"username": "u", "password": "p"},
        )
        csrf_token = cast(str, login_resp.cookies.get("csrf_token"))
        r = client.post(
            "/api/auth/logout",
            headers={
                "origin": "http://testserver",
                "x-csrf-token": csrf_token,
            },
        )
        assert r.status_code == 200
        assert "message" in r.json()
        set_cookie = r.headers["set-cookie"]
        assert "access_token=" in set_cookie
        assert "refresh_token=" in set_cookie
        assert "csrf_token=" in set_cookie

    def test_me(self):
        r = client.get("/api/auth/me", headers={"Authorization": "Bearer faketoken"})
        assert r.status_code == 200
        data = r.json()
        assert data["id"] == 1
        assert data["username"] == "testuser"
        assert data["has_security_question"] is False
        with patch.dict(app.dependency_overrides, {dependencies.get_current_user: lambda: {**MOCK_USER, "security_q1": "q"}}):
            assert client.get("/api/auth/me", headers={"Authorization": "Bearer faketoken"}).json()["has_security_question"] is True

    @patch("api.routes.auth.is_registration_open", new_callable=AsyncMock)
    def test_register_closed(self, mock_open):
        mock_open.return_value = False
        r = client.post(
            "/api/auth/register",
            json={
                "username": "newuser",
                "password": "StrongP@ssw0rd!",
                "security_question": "q",
                "security_answer": "a",
            },
        )
        assert r.status_code == 403

    @patch("api.routes.auth.insert_session", new_callable=AsyncMock)
    @patch("api.routes.auth.deactivate_all_sessions", new_callable=AsyncMock)
    @patch("api.routes.auth.create_refresh_token")
    @patch("api.routes.auth.create_access_token")
    @patch("api.routes.auth.create_user", new_callable=AsyncMock)
    @patch("api.routes.auth.find_by_username", new_callable=AsyncMock)
    @patch("api.routes.auth.is_registration_open", new_callable=AsyncMock)
    def test_register_success(
        self,
        mock_open,
        mock_find,
        mock_create,
        mock_access_token,
        mock_refresh_token,
        mock_deactivate_all,
        mock_insert_session,
    ):
        mock_open.return_value = True
        mock_find.return_value = None
        mock_create.return_value = 42
        mock_access_token.return_value = "newtoken"
        mock_refresh_token.return_value = "newrefresh"
        r = client.post(
            "/api/auth/register",
            json={
                "username": "validuser",
                "password": "StrongP@ss123!",
                "security_question": "q",
                "security_answer": "a",
            },
        )
        assert r.status_code == 200
        assert r.json()["access_token"] == "newtoken"
        assert r.json()["user"]["has_security_question"] is True
        set_cookie = r.headers["set-cookie"]
        assert "access_token=newtoken" in set_cookie
        assert "refresh_token=newrefresh" in set_cookie
        assert "csrf_token=" in set_cookie
        assert "Max-Age=900" in set_cookie
        assert "Max-Age=604800" in set_cookie
        mock_insert_session.assert_awaited_once()
        mock_deactivate_all.assert_awaited_once()

    @patch("api.routes.auth.find_by_username", new_callable=AsyncMock)
    @patch("api.routes.auth.is_registration_open", new_callable=AsyncMock)
    def test_register_username_conflict_uses_generic_message(
        self,
        mock_open,
        mock_find,
    ):
        mock_open.return_value = True
        mock_find.return_value = {"id": 9, "username": "validuser"}
        r = client.post(
            "/api/auth/register",
            json={
                "username": "validuser",
                "password": "StrongP@ss123!",
                "security_question": "q",
                "security_answer": "a",
            },
        )
        assert r.status_code == 400
        body = r.json()
        assert body["detail"] == "用户名或密码错误"

    @patch("api.routes.auth.update_user_password", new_callable=AsyncMock)
    @patch("api.routes.auth.get_user_by_id", new_callable=AsyncMock)
    def test_change_password_success(self, mock_get_user, mock_update):
        mock_get_user.return_value = {"id": 1}
        mock_update.return_value = True
        r = client.post(
            "/api/auth/change-password",
            json={
                "current_password": "OldP@ss123!x",
                "new_password": "NewStrongP@ss1!",
            },
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 200

    @patch("api.routes.auth.update_user_password", new_callable=AsyncMock)
    @patch("api.routes.auth.get_user_by_id", new_callable=AsyncMock)
    def test_change_password_wrong_current(self, mock_get_user, mock_update):
        mock_get_user.return_value = {"id": 1}
        mock_update.return_value = False
        r = client.post(
            "/api/auth/change-password",
            json={
                "current_password": "WrongOld@1234",
                "new_password": "NewStrongP@ss1!",
            },
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 401
        assert r.json()["detail"] == "当前密码错误"

    @patch("api.routes.auth.get_user_by_id", new_callable=AsyncMock)
    def test_change_password_missing_user_returns_401(self, mock_get_user):
        mock_get_user.return_value = None
        r = client.post(
            "/api/auth/change-password",
            json={
                "current_password": "OldP@ss123!x",
                "new_password": "NewStrongP@ss1!",
            },
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 401
        assert r.json()["detail"] == "认证已失效"

    def test_check_username_available(self):
        r = client.get("/api/auth/check-username", params={"username": "newuser"})
        assert r.status_code == 200
        assert r.json() == {"available": True}

    def test_check_username_taken(self):
        r = client.get("/api/auth/check-username", params={"username": "taken"})
        assert r.status_code == 200
        assert r.json() == {"available": True}

    def test_check_username_invalid_format(self):
        r = client.get("/api/auth/check-username", params={"username": "ab"})
        assert r.status_code == 200
        assert r.json() == {"available": True}

    def test_security_questions_endpoint_returns_preset_list(self):
        r = client.get("/api/auth/security-questions")
        assert r.status_code == 200
        body = r.json()
        assert "questions" in body
        assert isinstance(body["questions"], list)
        assert len(body["questions"]) == 5
        assert "您母亲的姓名是？" in body["questions"]

    def test_check_username_invalid_chars(self):
        r = client.get(
            "/api/auth/check-username",
            params={"username": "bad name!"},
        )
        assert r.status_code == 200
        assert r.json() == {"available": True}

    def test_check_username_rate_limit_single_ip_returns_429(self):
        headers = {"X-Forwarded-For": "203.0.113.10"}
        for _ in range(5):
            response = client.get(
                "/api/auth/check-username",
                params={"username": "newuser"},
                headers=headers,
            )
            assert response.status_code == 200

        response = client.get(
            "/api/auth/check-username",
            params={"username": "newuser"},
            headers=headers,
        )
        assert response.status_code == 429
        assert response.json()["detail"] == "请求过于频繁，请稍后再试"

    def test_check_username_rate_limit_different_ips_independent(self):
        ip1_headers = {"X-Forwarded-For": "203.0.113.11"}
        ip2_headers = {"X-Forwarded-For": "203.0.113.12"}

        for _ in range(5):
            response = client.get(
                "/api/auth/check-username",
                params={"username": "newuser"},
                headers=ip1_headers,
            )
            assert response.status_code == 200

        response = client.get(
            "/api/auth/check-username",
            params={"username": "otheruser"},
            headers=ip2_headers,
        )
        assert response.status_code == 200

        response = client.get(
            "/api/auth/check-username",
            params={"username": "newuser"},
            headers=ip1_headers,
        )
        assert response.status_code == 429

        response = client.get(
            "/api/auth/check-username",
            params={"username": "otheruser2"},
            headers=ip2_headers,
        )
        assert response.status_code == 200

    def test_check_username_rate_limit_window_resets_after_60_seconds(
        self,
    ):
        headers = {"X-Forwarded-For": "203.0.113.13"}
        fake_time = MagicMock()
        fake_time.time.side_effect = [1000.0] * 5 + [1061.0]
        with patch(
            "api.middleware.username_check_limiter.time",
            fake_time,
        ):
            for _ in range(5):
                response = client.get(
                    "/api/auth/check-username",
                    params={"username": "newuser"},
                    headers=headers,
                )
                assert response.status_code == 200

            response = client.get(
                "/api/auth/check-username",
                params={"username": "newuser"},
                headers=headers,
            )
            assert response.status_code == 200

    @patch("api.routes.auth.logger.warning")
    def test_check_username_rate_limit_logs_warning(self, mock_warning):
        headers = {"X-Forwarded-For": "203.0.113.14"}
        for _ in range(5):
            response = client.get(
                "/api/auth/check-username",
                params={"username": "newuser"},
                headers=headers,
            )
            assert response.status_code == 200

        response = client.get(
            "/api/auth/check-username",
            params={"username": "newuser"},
            headers=headers,
        )
        assert response.status_code == 429
        mock_warning.assert_called_once()
        args = mock_warning.call_args.args
        assert args[0] == "auth.check_username.rate_limited ip=%s username=%s timestamp=%s"
        assert args[1] == "203.0.113.14"
        assert args[2] == "newuser"

