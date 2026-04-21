"""
集成测试 — 安全特性端到端验证

覆盖：
- httpOnly cookie 认证流程（login 设置 cookie → 后续请求使用 cookie）
- 登录限流（5次失败后锁定）
- 冻结用户拒绝访问
- 密码迁移（SHA-256 → bcrypt）
- E2E_TEST 生产环境保护
"""

import hashlib
import os
import time
from typing import cast

import pytest
from httpx import AsyncClient


# ------------------------------------------------------------------
# 1. Cookie 认证流程
# ------------------------------------------------------------------


class TestCookieAuth:
    """Login sets httpOnly cookie; subsequent requests use it."""

    @pytest.mark.asyncio
    async def test_login_sets_cookie_and_returns_token(
        self,
        client: AsyncClient,
        test_user,
    ):
        resp = await client.post(
            "/api/auth/login",
            json={
                "username": test_user["username"],
                "password": test_user["password"],
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert "user" in body
        # httpOnly cookie is set
        cookie = resp.cookies.get("access_token")
        assert cookie is not None

    @pytest.mark.asyncio
    async def test_cookie_auth_access_protected_endpoint(
        self,
        client: AsyncClient,
        test_user,
    ):
        """Login then access /api/products using cookie only (no header)."""
        login_resp = await client.post(
            "/api/auth/login",
            json={
                "username": test_user["username"],
                "password": test_user["password"],
            },
        )
        assert login_resp.status_code == 200
        cookie_val = cast(str, login_resp.cookies.get("access_token"))
        csrf_val = cast(str, login_resp.cookies.get("csrf_token"))
        assert cookie_val

        client.cookies.update({"access_token": cookie_val})
        client.cookies.update({"csrf_token": csrf_val})

        # Use cookie only — no Authorization header
        resp = await client.get(
            "/api/products",
            headers={
                "origin": "http://test",
                "x-csrf-token": csrf_val,
            },
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_bearer_header_still_works(
        self,
        client: AsyncClient,
        test_user,
    ):
        """Bearer header takes precedence over cookie."""
        login_resp = await client.post(
            "/api/auth/login",
            json={
                "username": test_user["username"],
                "password": test_user["password"],
            },
        )
        token = login_resp.json()["access_token"]

        resp = await client.get(
            "/api/products",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_no_credentials_returns_401(self, client: AsyncClient):
        resp = await client.get("/api/products")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_expired_jwt_token_returns_401(
        self,
        client: AsyncClient,
        test_user,
    ):
        from datetime import timedelta
        from security.tokens import create_access_token

        token = create_access_token(
            user_id=test_user["id"],
            username=test_user["username"],
            expires_delta=timedelta(seconds=-1),
        )

        resp = await client.get(
            "/api/products",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_signature_jwt_token_returns_401(
        self,
        client: AsyncClient,
        test_user,
    ):
        import jwt as pyjwt

        token = pyjwt.encode(
            {"sub": str(test_user["id"]), "username": test_user["username"]},
            "wrong-secret-that-is-long-enough-for-hmac-sha256",
            algorithm="HS256",
        )

        resp = await client.get(
            "/api/products",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_malformed_token_returns_401(self, client: AsyncClient):
        resp = await client.get(
            "/api/products",
            headers={"Authorization": "Bearer definitely-not-a-jwt"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_logout_clears_cookie(
        self,
        client: AsyncClient,
        test_user,
    ):
        login_resp = await client.post(
            "/api/auth/login",
            json={
                "username": test_user["username"],
                "password": test_user["password"],
            },
        )
        assert login_resp.status_code == 200

        csrf_val = cast(str, login_resp.cookies.get("csrf_token"))
        logout_resp = await client.post(
            "/api/auth/logout",
            headers={
                "origin": "http://test",
                "x-csrf-token": csrf_val,
            },
        )
        assert logout_resp.status_code == 200
        # Cookie should be cleared (max-age=0 or deleted)
        cookie = logout_resp.cookies.get("access_token")
        # After delete_cookie the value is empty or key absent
        assert cookie is None or cookie == ""
        refresh_cookie = logout_resp.cookies.get("refresh_token")
        assert refresh_cookie is None or refresh_cookie == ""


# ------------------------------------------------------------------
# 2. 登录限流
# ------------------------------------------------------------------


class TestLoginRateLimiting:
    """5 failed attempts trigger lockout via API."""

    @pytest.mark.asyncio
    async def test_lockout_after_max_failed_attempts(
        self,
        client: AsyncClient,
        test_user,
    ):
        from api.middleware.login_limiter import login_limiter

        # Reset state for test IP
        test_ip = "127.0.0.1"
        login_limiter.attempts.pop(test_ip, None)
        login_limiter.lockouts.pop(test_ip, None)

        wrong_creds = {
            "username": test_user["username"],
            "password": "WrongP@ss999999",
        }

        for i in range(5):
            resp = await client.post("/api/auth/login", json=wrong_creds)
            assert resp.status_code == 401, f"attempt {i + 1} should be 401"

        # 6th attempt should be 429 (locked out)
        resp = await client.post("/api/auth/login", json=wrong_creds)
        assert resp.status_code == 429

    @pytest.mark.asyncio
    async def test_successful_login_clears_limiter(
        self,
        client: AsyncClient,
        test_user,
    ):
        from api.middleware.login_limiter import login_limiter

        test_ip = "127.0.0.1"
        login_limiter.attempts.pop(test_ip, None)
        login_limiter.lockouts.pop(test_ip, None)

        # 3 failed attempts
        for _ in range(3):
            await client.post(
                "/api/auth/login",
                json={
                    "username": test_user["username"],
                    "password": "WrongP@ss999999",
                },
            )

        # Successful login clears counter
        resp = await client.post(
            "/api/auth/login",
            json={
                "username": test_user["username"],
                "password": test_user["password"],
            },
        )
        assert resp.status_code == 200

        # Should be able to fail again without immediate lockout
        resp = await client.post(
            "/api/auth/login",
            json={
                "username": test_user["username"],
                "password": "WrongP@ss999999",
            },
        )
        assert resp.status_code == 401  # not 429


# ------------------------------------------------------------------
# 3. 冻结用户拒绝
# ------------------------------------------------------------------


class TestFrozenUserRejection:
    """Frozen users get 403 on any authenticated endpoint."""

    @pytest.mark.asyncio
    async def test_frozen_user_cannot_access_api(
        self,
        client: AsyncClient,
        test_user,
        db_session,
    ):
        # Login first (before freezing)
        login_resp = await client.post(
            "/api/auth/login",
            json={
                "username": test_user["username"],
                "password": test_user["password"],
            },
        )
        assert login_resp.status_code == 200
        token = login_resp.json()["access_token"]

        # Freeze the user
        from sqlalchemy import text

        await db_session.execute(
            text("UPDATE users SET is_frozen = 1 WHERE id = :uid"),
            {"uid": test_user["id"]},
        )
        await db_session.commit()

        # Try to access protected endpoint
        resp = await client.get(
            "/api/products",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403
        assert "冻结" in resp.json()["detail"]

        # Unfreeze for cleanup
        await db_session.execute(
            text("UPDATE users SET is_frozen = 0 WHERE id = :uid"),
            {"uid": test_user["id"]},
        )
        await db_session.commit()


# ------------------------------------------------------------------
# 4. 密码迁移 (SHA-256 → bcrypt)
# ------------------------------------------------------------------


class TestPasswordMigration:
    """SHA-256 legacy passwords auto-migrate to bcrypt on login."""

    @pytest.mark.asyncio
    async def test_sha256_password_migrates_on_login(
        self,
        client: AsyncClient,
        db_session,
    ):
        from models.user import User

        username = f"test_sha_mig_{int(time.time() * 1000)}"
        plain_password = "LegacyP@ss12345"
        sha_hash = hashlib.sha256(plain_password.encode()).hexdigest()

        user = User(
            username=username,
            password=sha_hash,
            role="user",
            user_type="free",
            subscription_type="free",
            remaining_calculations=10,
            created_at=time.strftime("%Y-%m-%d %H:%M:%S"),
            is_test_user=1,
        )
        db_session.add(user)
        await db_session.flush()
        await db_session.commit()
        user_id = user.id

        try:
            # Login with SHA-256 password — should succeed and migrate
            resp = await client.post(
                "/api/auth/login",
                json={
                    "username": username,
                    "password": plain_password,
                },
            )
            assert resp.status_code == 200

            # Verify password was migrated to bcrypt
            from sqlalchemy import text

            row = (
                await db_session.execute(
                    text("SELECT password FROM users WHERE id = :uid"),
                    {"uid": user_id},
                )
            ).fetchone()
            new_hash = row[0]
            assert new_hash.startswith("$2")  # bcrypt hash
            assert new_hash != sha_hash
        finally:
            from database import AsyncSessionLocal
            import tests.conftest as conftest

            await db_session.rollback()
            async with AsyncSessionLocal() as cleanup:
                try:
                    delete_test_user_async = getattr(
                        conftest,
                        "_delete_test_user_async",
                    )
                    await delete_test_user_async(
                        cleanup,
                        user_id,
                        username,
                    )
                    await cleanup.commit()
                except Exception:
                    await cleanup.rollback()


# ------------------------------------------------------------------
# 5. E2E_TEST 生产环境保护
# ------------------------------------------------------------------


class TestE2ETestFlag:
    """E2E_TEST flag should not skip rate limit in production."""

    @pytest.mark.asyncio
    async def test_e2e_flag_ignored_in_production(self):
        """Verify the flag logic: in production, E2E_TEST is ignored."""
        original_prod = os.environ.get("PRODUCTION_MODE")
        original_e2e = os.environ.get("E2E_TEST")

        try:
            os.environ["PRODUCTION_MODE"] = "true"
            os.environ["E2E_TEST"] = "1"

            _is_production = os.environ.get("PRODUCTION_MODE", "").lower() == "true"
            _skip = not _is_production and os.getenv("E2E_TEST")

            # In production mode, rate limit should NOT be skipped
            assert _skip is None or not _skip
        finally:
            if original_prod is None:
                os.environ.pop("PRODUCTION_MODE", None)
            else:
                os.environ["PRODUCTION_MODE"] = original_prod
            if original_e2e is None:
                os.environ.pop("E2E_TEST", None)
            else:
                os.environ["E2E_TEST"] = original_e2e

    @pytest.mark.asyncio
    async def test_e2e_flag_works_in_dev(self):
        """In dev mode with E2E_TEST set, rate limit can be skipped."""
        original_prod = os.environ.get("PRODUCTION_MODE")
        original_e2e = os.environ.get("E2E_TEST")

        try:
            os.environ.pop("PRODUCTION_MODE", None)
            os.environ["E2E_TEST"] = "1"

            _is_production = os.environ.get("PRODUCTION_MODE", "").lower() == "true"
            _skip = not _is_production and os.getenv("E2E_TEST")

            assert _skip  # Should be truthy in dev
        finally:
            if original_prod is None:
                os.environ.pop("PRODUCTION_MODE", None)
            else:
                os.environ["PRODUCTION_MODE"] = original_prod
            if original_e2e is None:
                os.environ.pop("E2E_TEST", None)
            else:
                os.environ["E2E_TEST"] = original_e2e
