from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
@patch("api.routes.auth.create_refresh_token", return_value="refresh-token")
@patch("api.routes.auth.create_access_token", return_value="access-token")
@patch("api.routes.auth.deactivate_all_sessions", new_callable=AsyncMock)
@patch("api.routes.auth.insert_session", new_callable=AsyncMock)
@patch("api.routes.auth.verify_user", new_callable=AsyncMock)
@patch("api.routes.auth.secrets.token_urlsafe", return_value="login-sid")
async def test_login_kicks_other_sessions(
    mock_sid,
    mock_verify,
    mock_insert,
    mock_deactivate_all,
    mock_access_token,
    mock_refresh_token,
    client,
    test_user,
):
    mock_verify.return_value = {
        "id": test_user["id"],
        "username": test_user["username"],
        "role": "user",
        "user_type": "free",
        "subscription_type": "free",
        "remaining_calculations": 10,
    }

    response = await client.post(
        "/api/auth/login",
        json={
            "username": test_user["username"],
            "password": test_user["password"],
        },
    )

    assert response.status_code == 200
    insert_args, insert_kwargs = mock_insert.await_args
    deactivate_args, deactivate_kwargs = mock_deactivate_all.await_args
    assert insert_args[0] is deactivate_args[0]
    assert insert_kwargs["session_id"] == "login-sid"
    assert insert_kwargs["user_id"] == test_user["id"]
    assert insert_kwargs["ip_address"] == "127.0.0.1"
    assert insert_kwargs["user_agent"]
    assert insert_kwargs["now"] is not None
    assert deactivate_args[1] == test_user["id"]
    assert deactivate_kwargs == {
        "exclude_session_id": "login-sid",
        "reason": "kicked_by_new_login",
    }
    mock_access_token.assert_called_once_with(
        user_id=test_user["id"],
        username=test_user["username"],
        role="user",
        extra_claims={"sid": "login-sid"},
    )
    mock_refresh_token.assert_called_once_with(
        user_id=test_user["id"],
        sid="login-sid",
    )
    assert mock_sid.call_args_list[0].args == (32,)


@pytest.mark.asyncio
@patch("api.routes.auth.create_refresh_token", return_value="register-refresh")
@patch("api.routes.auth.create_access_token", return_value="register-access")
@patch("api.routes.auth.deactivate_all_sessions", new_callable=AsyncMock)
@patch("api.routes.auth.insert_session", new_callable=AsyncMock)
@patch("api.routes.auth.create_user", new_callable=AsyncMock)
@patch("api.routes.auth.find_by_username", new_callable=AsyncMock)
@patch("api.routes.auth.is_registration_open", new_callable=AsyncMock)
@patch("api.routes.auth.secrets.token_urlsafe", return_value="register-sid")
async def test_register_kicks_other_sessions(
    mock_sid,
    mock_open,
    mock_find,
    mock_create_user,
    mock_insert,
    mock_deactivate_all,
    mock_access_token,
    mock_refresh_token,
    client,
):
    mock_open.return_value = True
    mock_find.return_value = None
    mock_create_user.return_value = 321

    response = await client.post(
        "/api/auth/register",
        json={
            "username": "kick_register_user",
            "password": "StrongP@ss123!",
            "security_question": "q",
            "security_answer": "a",
        },
    )

    assert response.status_code == 200
    insert_args, insert_kwargs = mock_insert.await_args
    deactivate_args, deactivate_kwargs = mock_deactivate_all.await_args
    assert insert_args[0] is deactivate_args[0]
    assert insert_kwargs["session_id"] == "register-sid"
    assert insert_kwargs["user_id"] == 321
    assert insert_kwargs["ip_address"] == "127.0.0.1"
    assert insert_kwargs["user_agent"]
    assert insert_kwargs["now"] is not None
    assert deactivate_args[1] == 321
    assert deactivate_kwargs == {
        "exclude_session_id": "register-sid",
        "reason": "kicked_by_new_login",
    }
    mock_access_token.assert_called_once_with(
        user_id=321,
        username="kick_register_user",
        role="user",
        extra_claims={"sid": "register-sid"},
    )
    mock_refresh_token.assert_called_once_with(user_id=321, sid="register-sid")
    assert mock_sid.call_args_list[0].args == (32,)
