from datetime import timedelta
import time
from typing import cast

import pytest

from db.sessions_crud import deactivate_session, get_session, insert_session
from security.tokens import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
)


def _csrf_headers(token: str | None = None) -> dict[str, str]:
    headers = {"origin": "http://test"}
    if token is not None:
        headers["x-csrf-token"] = token
    return headers


@pytest.fixture(autouse=True)
def allow_test_origin(monkeypatch):
    monkeypatch.setattr("api.dependencies._ALLOWED_ORIGINS", {"http://test"})


class TestAuthRefresh:
    @pytest.mark.asyncio
    async def test_refresh_missing_cookie_returns_401(
        self,
        client,
    ):
        client.cookies.set("csrf_token", "csrf-1")
        resp = await client.post(
            "/api/auth/refresh",
            headers=_csrf_headers("csrf-1"),
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_missing_csrf_returns_403(
        self,
        client,
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

        resp = await client.post(
            "/api/auth/refresh",
            headers={"origin": "http://test"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_refresh_access_token_rejected(
        self,
        client,
        test_user,
    ):
        access_token = create_access_token(
            user_id=test_user["id"],
            username=test_user["username"],
        )
        client.cookies.set("csrf_token", "csrf-2")
        client.cookies.set("refresh_token", access_token)

        resp = await client.post(
            "/api/auth/refresh",
            headers=_csrf_headers("csrf-2"),
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_expired_token_rejected(
        self,
        client,
        test_user,
    ):
        expired_refresh = create_refresh_token(
            user_id=test_user["id"],
            sid="expired-sid",
            expires_delta=timedelta(seconds=-1),
        )
        client.cookies.set("csrf_token", "csrf-3")
        client.cookies.set("refresh_token", expired_refresh)

        resp = await client.post(
            "/api/auth/refresh",
            headers=_csrf_headers("csrf-3"),
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_unknown_sid_rejected(
        self,
        client,
        test_user,
    ):
        refresh_token = create_refresh_token(
            user_id=test_user["id"],
            sid="missing-sid",
        )
        client.cookies.set("csrf_token", "csrf-4")
        client.cookies.set("refresh_token", refresh_token)

        resp = await client.post(
            "/api/auth/refresh",
            headers=_csrf_headers("csrf-4"),
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_inactive_sid_rejected(
        self,
        client,
        test_user,
        db_session,
    ):
        sid = f"inactive-sid-{int(time.time() * 1000)}"
        await insert_session(
            db_session,
            session_id=sid,
            user_id=test_user["id"],
            ip_address="127.0.0.1",
            user_agent="pytest",
            now=1.0,
        )
        await deactivate_session(db_session, sid)
        await db_session.commit()

        refresh_token = create_refresh_token(user_id=test_user["id"], sid=sid)
        client.cookies.set("csrf_token", "csrf-5")
        client.cookies.set("refresh_token", refresh_token)

        resp = await client.post(
            "/api/auth/refresh",
            headers=_csrf_headers("csrf-5"),
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_happy_path_reuses_sid(
        self,
        client,
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

        original_payload = decode_refresh_token(cast(str, client.cookies.get("refresh_token")))
        original_sid = original_payload["sid"]
        csrf_token = cast(str, client.cookies.get("csrf_token"))

        resp = await client.post(
            "/api/auth/refresh",
            headers=_csrf_headers(csrf_token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["token_type"] == "bearer"
        assert body["access_token"]

        new_payload = decode_refresh_token(cast(str, client.cookies.get("refresh_token")))
        assert new_payload["sid"] == original_sid
        assert client.cookies.get("csrf_token")

    @pytest.mark.asyncio
    async def test_refresh_can_repeat_with_same_sid(
        self,
        client,
        test_user,
        db_session,
    ):
        login_resp = await client.post(
            "/api/auth/login",
            json={
                "username": test_user["username"],
                "password": test_user["password"],
            },
        )
        assert login_resp.status_code == 200

        original_sid = decode_refresh_token(
            cast(str, client.cookies.get("refresh_token"))
        )["sid"]
        first_csrf = cast(str, client.cookies.get("csrf_token"))
        first_resp = await client.post(
            "/api/auth/refresh",
            headers=_csrf_headers(first_csrf),
        )
        assert first_resp.status_code == 200

        second_csrf = cast(str, client.cookies.get("csrf_token"))
        second_resp = await client.post(
            "/api/auth/refresh",
            headers=_csrf_headers(second_csrf),
        )
        assert second_resp.status_code == 200
        assert decode_refresh_token(
            cast(str, client.cookies.get("refresh_token"))
        )["sid"] == original_sid

        session_row = await get_session(db_session, original_sid)
        assert session_row is not None
        assert session_row.is_active is True
