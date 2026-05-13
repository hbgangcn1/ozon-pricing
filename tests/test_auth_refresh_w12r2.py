from datetime import timedelta

import jwt as pyjwt
import pytest
from httpx import ASGITransport, AsyncClient

from api.main import app
from db.sessions_crud import insert_session
from security.tokens import (
    ALGORITHM,
    AUDIENCE,
    ISSUER,
    SECRET_KEY,
    TOKEN_TYPE_ACCESS,
    TokenInvalidError,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
)


JWT_SECRET = str(SECRET_KEY)


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


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


class TestRefreshAccessW12R2:
    @pytest.mark.asyncio
    async def test_refresh_with_access_token_returns_401(self, client, test_user):
        access = create_access_token(
            user_id=test_user["id"],
            username=test_user["username"],
            role="user",
        )
        _set_refresh_cookie(client, access)

        response = await client.post(
            "/api/auth/refresh-access",
            headers={"Authorization": f"Bearer {access}"},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_with_valid_refresh_cookie_rotates_tokens(
        self,
        client,
        test_user,
        db_session,
    ):
        sid = "w12r2-valid-refresh"
        await _insert_active_session(db_session, test_user["id"], sid)
        refresh = create_refresh_token(user_id=test_user["id"], sid=sid)
        old_jti = decode_refresh_token(refresh)["jti"]
        _set_refresh_cookie(client, refresh)

        response = await client.post("/api/auth/refresh-access")

        assert response.status_code == 200
        access_token = response.json()["access_token"]
        access_payload = decode_access_token(access_token)
        assert access_payload["sub"] == str(test_user["id"])
        assert access_payload["sid"] == sid
        assert response.cookies.get("access_token") == access_token

        new_refresh = response.cookies.get("refresh_token")
        assert new_refresh and new_refresh != refresh
        new_refresh_payload = decode_refresh_token(new_refresh)
        assert new_refresh_payload["sub"] == str(test_user["id"])
        assert new_refresh_payload["sid"] == sid
        assert new_refresh_payload["jti"] != old_jti
        with pytest.raises(TokenInvalidError):
            decode_refresh_token(refresh)

    @pytest.mark.asyncio
    async def test_refresh_with_expired_refresh_returns_401(
        self,
        client,
        test_user,
        db_session,
    ):
        sid = "w12r2-expired-refresh"
        await _insert_active_session(db_session, test_user["id"], sid)
        expired = create_refresh_token(
            user_id=test_user["id"],
            sid=sid,
            expires_delta=timedelta(seconds=-1),
        )
        _set_refresh_cookie(client, expired)

        response = await client.post("/api/auth/refresh-access")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_with_wrong_token_type_returns_401(self, client):
        token = pyjwt.encode(
            {
                "sub": "1",
                "sid": "wrong-type-sid",
                "type": TOKEN_TYPE_ACCESS,
                "iat": 1,
                "exp": 9999999999,
                "iss": ISSUER,
                "aud": AUDIENCE,
            },
            JWT_SECRET,
            algorithm=ALGORITHM,
        )
        _set_refresh_cookie(client, token)

        response = await client.post("/api/auth/refresh-access")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_auth_cookies_secure_true_in_production_env(
        self,
        monkeypatch,
        client,
        test_user,
        db_session,
    ):
        monkeypatch.setenv("ENVIRONMENT", "production")
        sid = "w12r2-prod-cookie"
        await _insert_active_session(db_session, test_user["id"], sid)
        _set_refresh_cookie(client, create_refresh_token(user_id=test_user["id"], sid=sid))

        response = await client.post("/api/auth/refresh-access")

        assert response.status_code == 200
        assert all(
            "Secure" in header
            for header in response.headers.get_list("set-cookie")
            if header.startswith(("access_token=", "refresh_token=", "csrf_token="))
        )

    @pytest.mark.asyncio
    async def test_auth_cookies_secure_false_in_dev_over_http(
        self,
        monkeypatch,
        client,
        test_user,
        db_session,
    ):
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.setenv("ENV", "development")
        sid = "w12r2-dev-cookie"
        await _insert_active_session(db_session, test_user["id"], sid)
        _set_refresh_cookie(client, create_refresh_token(user_id=test_user["id"], sid=sid))

        response = await client.post("/api/auth/refresh-access")

        assert response.status_code == 200
        assert all(
            "Secure" not in header
            for header in response.headers.get_list("set-cookie")
            if header.startswith(("access_token=", "refresh_token=", "csrf_token="))
        )
