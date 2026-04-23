"""守护 E2E_DISABLE_NEW_LOGIN_SESSION_KICK gate 行为。

确保：
  1. 默认（无 env / 单 env）仍调用 deactivate_all_sessions（生产安全）。
  2. 仅当 E2E_TEST=1 且 E2E_DISABLE_NEW_LOGIN_SESSION_KICK=1 同时设置时才跳过。
  3. 任一 env 缺失或非 '1' 都不生效。

这是 R-W14-C0-line25-arch（Oracle 窄化 A）的 regression guard，
防止未来误删 if 语句或松绑 env 条件。
"""
from unittest.mock import AsyncMock, patch

import pytest


def _build_login_mocks():
    return {
        "verify": {
            "id": 1,
            "username": "u",
            "role": "user",
            "user_type": "free",
            "subscription_type": "free",
            "remaining_calculations": 10,
        },
    }


@pytest.mark.asyncio
@patch("api.routes.auth.create_refresh_token", return_value="r")
@patch("api.routes.auth.create_access_token", return_value="a")
@patch("api.routes.auth.deactivate_all_sessions", new_callable=AsyncMock)
@patch("api.routes.auth.insert_session", new_callable=AsyncMock)
@patch("api.routes.auth.verify_user", new_callable=AsyncMock)
@patch("api.routes.auth.secrets.token_urlsafe", return_value="sid-default")
async def test_default_env_kicks(
    _sid, mock_verify, _ins, mock_deactivate, _at, _rt, client, test_user, monkeypatch
):
    monkeypatch.delenv("E2E_TEST", raising=False)
    monkeypatch.delenv("E2E_DISABLE_NEW_LOGIN_SESSION_KICK", raising=False)
    mock_verify.return_value = {**_build_login_mocks()["verify"], "id": test_user["id"]}
    resp = await client.post(
        "/api/auth/login",
        json={"username": test_user["username"], "password": test_user["password"]},
    )
    assert resp.status_code == 200
    mock_deactivate.assert_awaited_once()


@pytest.mark.asyncio
@patch("api.routes.auth.create_refresh_token", return_value="r")
@patch("api.routes.auth.create_access_token", return_value="a")
@patch("api.routes.auth.deactivate_all_sessions", new_callable=AsyncMock)
@patch("api.routes.auth.insert_session", new_callable=AsyncMock)
@patch("api.routes.auth.verify_user", new_callable=AsyncMock)
@patch("api.routes.auth.secrets.token_urlsafe", return_value="sid-only-e2e")
async def test_only_e2e_test_env_still_kicks(
    _sid, mock_verify, _ins, mock_deactivate, _at, _rt, client, test_user, monkeypatch
):
    monkeypatch.setenv("E2E_TEST", "1")
    monkeypatch.delenv("E2E_DISABLE_NEW_LOGIN_SESSION_KICK", raising=False)
    mock_verify.return_value = {**_build_login_mocks()["verify"], "id": test_user["id"]}
    resp = await client.post(
        "/api/auth/login",
        json={"username": test_user["username"], "password": test_user["password"]},
    )
    assert resp.status_code == 200
    mock_deactivate.assert_awaited_once()


@pytest.mark.asyncio
@patch("api.routes.auth.create_refresh_token", return_value="r")
@patch("api.routes.auth.create_access_token", return_value="a")
@patch("api.routes.auth.deactivate_all_sessions", new_callable=AsyncMock)
@patch("api.routes.auth.insert_session", new_callable=AsyncMock)
@patch("api.routes.auth.verify_user", new_callable=AsyncMock)
@patch("api.routes.auth.secrets.token_urlsafe", return_value="sid-only-disable")
async def test_only_disable_env_still_kicks(
    _sid, mock_verify, _ins, mock_deactivate, _at, _rt, client, test_user, monkeypatch
):
    monkeypatch.delenv("E2E_TEST", raising=False)
    monkeypatch.setenv("E2E_DISABLE_NEW_LOGIN_SESSION_KICK", "1")
    mock_verify.return_value = {**_build_login_mocks()["verify"], "id": test_user["id"]}
    resp = await client.post(
        "/api/auth/login",
        json={"username": test_user["username"], "password": test_user["password"]},
    )
    assert resp.status_code == 200
    mock_deactivate.assert_awaited_once()


@pytest.mark.asyncio
@patch("api.routes.auth.create_refresh_token", return_value="r")
@patch("api.routes.auth.create_access_token", return_value="a")
@patch("api.routes.auth.deactivate_all_sessions", new_callable=AsyncMock)
@patch("api.routes.auth.insert_session", new_callable=AsyncMock)
@patch("api.routes.auth.verify_user", new_callable=AsyncMock)
@patch("api.routes.auth.secrets.token_urlsafe", return_value="sid-both")
async def test_both_envs_skip_kick(
    _sid, mock_verify, _ins, mock_deactivate, _at, _rt, client, test_user, monkeypatch
):
    monkeypatch.setenv("E2E_TEST", "1")
    monkeypatch.setenv("E2E_DISABLE_NEW_LOGIN_SESSION_KICK", "1")
    mock_verify.return_value = {**_build_login_mocks()["verify"], "id": test_user["id"]}
    resp = await client.post(
        "/api/auth/login",
        json={"username": test_user["username"], "password": test_user["password"]},
    )
    assert resp.status_code == 200
    mock_deactivate.assert_not_awaited()


@pytest.mark.asyncio
@patch("api.routes.auth.create_refresh_token", return_value="r")
@patch("api.routes.auth.create_access_token", return_value="a")
@patch("api.routes.auth.deactivate_all_sessions", new_callable=AsyncMock)
@patch("api.routes.auth.insert_session", new_callable=AsyncMock)
@patch("api.routes.auth.verify_user", new_callable=AsyncMock)
@patch("api.routes.auth.secrets.token_urlsafe", return_value="sid-non1")
async def test_non_one_value_does_not_disable(
    _sid, mock_verify, _ins, mock_deactivate, _at, _rt, client, test_user, monkeypatch
):
    monkeypatch.setenv("E2E_TEST", "true")
    monkeypatch.setenv("E2E_DISABLE_NEW_LOGIN_SESSION_KICK", "yes")
    mock_verify.return_value = {**_build_login_mocks()["verify"], "id": test_user["id"]}
    resp = await client.post(
        "/api/auth/login",
        json={"username": test_user["username"], "password": test_user["password"]},
    )
    assert resp.status_code == 200
    mock_deactivate.assert_awaited_once()
