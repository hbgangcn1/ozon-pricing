"""Tests for POST /api/auth/refresh-access refresh-cookie contract."""

from datetime import timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from api.main import app
from db.sessions_crud import insert_session
from models.session import ActiveSession
from models.user import User
from security.tokens import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
)


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
    yield {"id": user.id, "username": "frozen_test_user"}
    await db_session.rollback()


async def _insert_active_session(db_session, user_id: int, sid: str) -> None:
    await insert_session(
        db_session,
        session_id=sid,
        user_id=user_id,
        ip_address="127.0.0.1",
        user_agent="pytest",
        now=1.0,
    )
    await db_session.commit()


def _set_refresh_cookie(client: AsyncClient, token: str) -> None:
    client.cookies.set("refresh_token", token, path="/")


class TestRefreshAccessEndpoint:
    @pytest.mark.asyncio
    async def test_missing_refresh_cookie_returns_401(self, client):
        response = await client.post("/api/auth/refresh-access")

        assert response.status_code == 401
        assert "刷新令牌" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_bearer_access_token_without_cookie_returns_401(self, client, test_user):
        token = create_access_token(
            user_id=test_user["id"],
            username=test_user["username"],
            role="user",
        )

        response = await client.post(
            "/api/auth/refresh-access",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_access_token_in_refresh_cookie_returns_401(self, client, test_user):
        token = create_access_token(
            user_id=test_user["id"],
            username=test_user["username"],
            role="user",
        )
        _set_refresh_cookie(client, token)

        response = await client.post("/api/auth/refresh-access")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_nonexistent_user_returns_401(self, client, db_session):
        sid = "refresh-nonexistent-user"
        await _insert_active_session(db_session, 999999, sid)
        _set_refresh_cookie(client, create_refresh_token(user_id=999999, sid=sid))

        response = await client.post("/api/auth/refresh-access")

        assert response.status_code == 401
        assert "不存在" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_frozen_user_returns_401(self, client, frozen_user, db_session):
        sid = "refresh-frozen-user"
        await _insert_active_session(db_session, frozen_user["id"], sid)
        _set_refresh_cookie(client, create_refresh_token(user_id=frozen_user["id"], sid=sid))

        response = await client.post("/api/auth/refresh-access")

        assert response.status_code == 401
        assert "冻结" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_successful_refresh_returns_new_token(self, client, test_user, db_session):
        sid = "refresh-successful"
        await _insert_active_session(db_session, test_user["id"], sid)
        _set_refresh_cookie(client, create_refresh_token(user_id=test_user["id"], sid=sid))

        response = await client.post("/api/auth/refresh-access")

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data.get("token_type") == "bearer"

        new_payload = decode_access_token(data["access_token"])
        assert new_payload["sub"] == str(test_user["id"])
        assert new_payload["username"] == test_user["username"]
        assert new_payload["role"] == "user"
        assert new_payload["sid"] == sid
        assert response.cookies.get("refresh_token") is not None

    @pytest.mark.asyncio
    async def test_expired_refresh_cookie_returns_401(self, client, test_user, db_session):
        sid = "refresh-expired"
        await _insert_active_session(db_session, test_user["id"], sid)
        token = create_refresh_token(
            user_id=test_user["id"],
            sid=sid,
            expires_delta=timedelta(seconds=-1),
        )
        _set_refresh_cookie(client, token)

        response = await client.post("/api/auth/refresh-access")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_admin_user_can_refresh(self, client, test_admin, db_session):
        sid = "refresh-admin"
        await _insert_active_session(db_session, test_admin["id"], sid)
        _set_refresh_cookie(client, create_refresh_token(user_id=test_admin["id"], sid=sid))

        response = await client.post("/api/auth/refresh-access")

        assert response.status_code == 200
        new_payload = decode_access_token(response.json()["access_token"])
        assert new_payload["role"] == "admin"

    @pytest.mark.asyncio
    async def test_inactive_session_with_sid_returns_401(
        self,
        client,
        test_user,
        db_session,
    ):
        sid = "refresh-inactive"
        await _insert_active_session(db_session, test_user["id"], sid)
        session_row = await db_session.get(ActiveSession, sid)
        session_row.is_active = False
        session_row.inactive_reason = "logout"
        await db_session.commit()
        _set_refresh_cookie(client, create_refresh_token(user_id=test_user["id"], sid=sid))

        response = await client.post("/api/auth/refresh-access")

        assert response.status_code == 401
        assert "会话" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_missing_session_with_sid_returns_401(self, client, test_user):
        token = create_refresh_token(user_id=test_user["id"], sid="refresh-missing")
        _set_refresh_cookie(client, token)

        response = await client.post("/api/auth/refresh-access")

        assert response.status_code == 401
        assert "会话" in response.json()["detail"]
