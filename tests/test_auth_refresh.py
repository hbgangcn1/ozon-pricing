"""Tests for POST /auth/refresh-access endpoint (Bearer-token proactive refresh)."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("ALLOWED_ORIGINS", "http://testserver")

import pytest
from httpx import AsyncClient, ASGITransport

from api.main import app
from security.tokens import create_access_token, decode_access_token
from models.user import User


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def frozen_user(db_session):
    from db.password import hash_password

    user = User(
        username="frozen_test_user",
        password=hash_password("FrozenP@ss123456"),
        role="user",
        user_type="free",
        subscription_type="free",
        remaining_calculations=5,
        created_at="2024-01-01 00:00:00",
        is_frozen=True,
        is_test_user=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.commit()
    user_id = user.id
    yield {"id": user_id, "username": "frozen_test_user"}
    await db_session.rollback()


class TestRefreshAccessEndpoint:
    @pytest.mark.asyncio
    async def test_missing_bearer_token_returns_401(self, client):
        response = await client.post("/api/auth/refresh-access")
        assert response.status_code == 401
        assert "Bearer" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_invalid_bearer_token_format_returns_401(self, client):
        response = await client.post(
            "/api/auth/refresh-access",
            headers={"Authorization": "NotBearer sometoken"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_nonexistent_user_returns_401(self, client):
        token = create_access_token(user_id=999999, username="ghost", role="user")
        response = await client.post(
            "/api/auth/refresh-access",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401
        assert "不存在" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_frozen_user_returns_401(self, client, frozen_user):
        token = create_access_token(
            user_id=frozen_user["id"],
            username=frozen_user["username"],
            role="user",
        )
        response = await client.post(
            "/api/auth/refresh-access",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401
        assert "冻结" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_successful_refresh_returns_new_token(self, client, test_user):
        token = create_access_token(
            user_id=test_user["id"],
            username=test_user["username"],
            role="user",
        )
        response = await client.post(
            "/api/auth/refresh-access",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data.get("token_type") == "bearer"

        new_payload = decode_access_token(data["access_token"])
        assert new_payload["sub"] == str(test_user["id"])
        assert new_payload["username"] == test_user["username"]
        assert new_payload["role"] == "user"

    @pytest.mark.asyncio
    async def test_refreshed_token_is_different_from_original(self, client, test_user):
        import time
        token = create_access_token(
            user_id=test_user["id"],
            username=test_user["username"],
            role="user",
        )
        time.sleep(1.1)
        response = await client.post(
            "/api/auth/refresh-access",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["access_token"] != token

    @pytest.mark.asyncio
    async def test_invalid_token_returns_401(self, client, test_user):
        """Tampered signature must trigger TokenInvalidError → 401 (W8/W9 fix)."""
        token = create_access_token(
            user_id=test_user["id"],
            username=test_user["username"],
            role="user",
        )
        parts = token.split(".")
        assert len(parts) == 3
        tampered = f"{parts[0]}.{parts[1]}.invalidsignaturepayload"
        response = await client.post(
            "/api/auth/refresh-access",
            headers={"Authorization": f"Bearer {tampered}"},
        )
        assert response.status_code == 401
        assert "无效" in response.json()["detail"] or "过期" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_expired_token_returns_401_proactive_refresh(self, client, test_user):
        from datetime import timedelta

        token = create_access_token(
            user_id=test_user["id"],
            username=test_user["username"],
            role="user",
            expires_delta=timedelta(seconds=-1),
        )
        response = await client.post(
            "/api/auth/refresh-access",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401
        assert "过期" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_new_token_has_correct_expiry(self, client, test_user):
        from security.tokens import ACCESS_TOKEN_EXPIRE_SECONDS

        token = create_access_token(
            user_id=test_user["id"],
            username=test_user["username"],
            role="user",
        )
        response = await client.post(
            "/api/auth/refresh-access",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        import time
        time.sleep(0.1)
        data = response.json()
        new_payload = decode_access_token(data["access_token"])
        ttl = new_payload["exp"] - new_payload["iat"]
        assert ttl == ACCESS_TOKEN_EXPIRE_SECONDS

    @pytest.mark.asyncio
    async def test_admin_user_can_refresh(self, client, test_admin):
        token = create_access_token(
            user_id=test_admin["id"],
            username=test_admin["username"],
            role="admin",
        )
        response = await client.post(
            "/api/auth/refresh-access",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        new_payload = decode_access_token(data["access_token"])
        assert new_payload["role"] == "admin"

    @pytest.mark.asyncio
    async def test_inactive_session_with_sid_returns_401(
        self, client, test_user, db_session
    ):
        from uuid import uuid4
        from db.sessions_crud import insert_session
        from models.session import ActiveSession

        sid = f"refresh-inactive-{uuid4().hex}"
        await insert_session(
            db_session,
            session_id=sid,
            user_id=test_user["id"],
            ip_address="127.0.0.1",
            user_agent="pytest",
            now=1.0,
        )
        session_row = await db_session.get(ActiveSession, sid)
        session_row.is_active = False
        session_row.inactive_reason = "logout"
        await db_session.commit()

        token = create_access_token(
            user_id=test_user["id"],
            username=test_user["username"],
            role="user",
            extra_claims={"sid": sid},
        )
        response = await client.post(
            "/api/auth/refresh-access",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401
        assert "会话" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_active_session_with_sid_succeeds(
        self, client, test_user, db_session
    ):
        from uuid import uuid4
        from db.sessions_crud import insert_session

        sid = f"refresh-active-{uuid4().hex}"
        await insert_session(
            db_session,
            session_id=sid,
            user_id=test_user["id"],
            ip_address="127.0.0.1",
            user_agent="pytest",
            now=1.0,
        )
        await db_session.commit()

        token = create_access_token(
            user_id=test_user["id"],
            username=test_user["username"],
            role="user",
            extra_claims={"sid": sid},
        )
        response = await client.post(
            "/api/auth/refresh-access",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        new_payload = decode_access_token(response.json()["access_token"])
        assert new_payload["sid"] == sid

    @pytest.mark.asyncio
    async def test_missing_session_with_sid_returns_401(self, client, test_user):
        from uuid import uuid4

        token = create_access_token(
            user_id=test_user["id"],
            username=test_user["username"],
            role="user",
            extra_claims={"sid": f"refresh-missing-{uuid4().hex}"},
        )
        response = await client.post(
            "/api/auth/refresh-access",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401
        assert "会话" in response.json()["detail"]
