# pyright: reportPrivateUsage=false

from typing import Optional, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException


def _make_api_key(token_str: str):
    mock = MagicMock()
    mock.credentials = token_str
    return mock


def _make_request(token_str=None):
    req = MagicMock()
    req.cookies = {"access_token": token_str} if token_str else {}
    return req


def _make_user(
    user_id=1,
    username="alice",
    role="user",
    user_type="free",
    subscription_type: Optional[str] = "free",
    remaining_calculations=10,
    is_frozen=0,
    trial_used=0,
    trial_started_at=0,
    trial_expires_at=0,
    trial_plan_at_start="",
):
    user = MagicMock()
    user.id = user_id
    user.username = username
    user.role = role
    user.user_type = user_type
    user.subscription_type = subscription_type
    user.remaining_calculations = remaining_calculations
    user.is_frozen = is_frozen
    user.trial_used = trial_used
    user.trial_started_at = trial_started_at
    user.trial_expires_at = trial_expires_at
    user.trial_plan_at_start = trial_plan_at_start
    return user


class TestGetUser:
    @patch("api.dependencies.decode_access_token")
    async def test_invalid_token_raises_401(self, mock_decode):
        from security.tokens import TokenInvalidError

        from api.dependencies import _get_user

        mock_decode.side_effect = TokenInvalidError("bad")
        with pytest.raises(HTTPException) as exc_info:
            await _get_user("bad-token", AsyncMock())
        assert exc_info.value.status_code == 401

    @patch("api.dependencies.decode_access_token")
    async def test_invalid_sub_raises_401(self, mock_decode):
        from api.dependencies import _get_user

        mock_decode.return_value = {"sub": "bad-int"}
        with pytest.raises(HTTPException) as exc_info:
            await _get_user("token", AsyncMock())
        assert exc_info.value.status_code == 401

    @patch("api.dependencies.get_session", new_callable=AsyncMock)
    @patch("api.dependencies.decode_access_token")
    async def test_missing_session_row_raises_401(self, mock_decode, mock_get_session):
        from api.dependencies import _get_user

        mock_decode.return_value = {"sub": "7", "sid": "missing-sid"}
        mock_get_session.return_value = None
        with pytest.raises(HTTPException) as exc_info:
            await _get_user("token", AsyncMock())
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == {"error": "会话已失效", "reason": None}

    @patch("api.dependencies.get_session", new_callable=AsyncMock)
    @patch("api.dependencies.decode_access_token")
    async def test_inactive_session_reason_raises_401(
        self,
        mock_decode,
        mock_get_session,
    ):
        from api.dependencies import _get_user

        inactive = MagicMock()
        inactive.is_active = False
        inactive.inactive_reason = "kicked_by_new_login"
        mock_decode.return_value = {"sub": "7", "sid": "sid-1"}
        mock_get_session.return_value = inactive
        with pytest.raises(HTTPException) as exc_info:
            await _get_user("token", AsyncMock())
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == {
            "error": "会话已失效",
            "reason": "kicked_by_new_login",
        }

    @patch("api.dependencies.get_session", new_callable=AsyncMock)
    @patch("api.dependencies.decode_access_token")
    async def test_no_sid_skips_session_lookup(self, mock_decode, mock_get_session):
        from api.dependencies import _get_user

        session = AsyncMock()
        session.get.return_value = _make_user(user_id=7)
        mock_decode.return_value = {"sub": "7"}
        user = await _get_user("token", session)
        assert user.id == 7
        mock_get_session.assert_not_awaited()

    @patch("api.dependencies.decode_access_token")
    async def test_user_not_found_raises_401(self, mock_decode):
        from api.dependencies import _get_user

        session = AsyncMock()
        session.get.return_value = None
        mock_decode.return_value = {"sub": "7"}
        with pytest.raises(HTTPException) as exc_info:
            await _get_user("token", session)
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "用户不存在"

    @patch("api.dependencies.decode_access_token")
    async def test_frozen_user_raises_403(self, mock_decode):
        from api.dependencies import _get_user

        session = AsyncMock()
        session.get.return_value = _make_user(user_id=7, is_frozen=1)
        mock_decode.return_value = {"sub": "7"}
        with pytest.raises(HTTPException) as exc_info:
            await _get_user("token", session)
        assert exc_info.value.status_code == 403


class TestGetCurrentUserId:
    @patch("api.dependencies._get_user", new_callable=AsyncMock)
    async def test_valid_user_returns_id(self, mock_get_user):
        from api.dependencies import get_current_user_id

        mock_get_user.return_value = _make_user(user_id=42)
        result = await get_current_user_id(_make_request(), _make_api_key("token"), AsyncMock())
        assert result == 42

    @patch("api.dependencies._get_user", new_callable=AsyncMock)
    async def test_failure_propagates(self, mock_get_user):
        from api.dependencies import get_current_user_id

        mock_get_user.side_effect = HTTPException(status_code=401, detail="bad")
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_id(_make_request(), _make_api_key("token"), AsyncMock())
        assert exc_info.value.status_code == 401


class TestGetCurrentUser:
    @patch("api.dependencies._get_user", new_callable=AsyncMock)
    async def test_returns_user_dict(self, mock_get_user):
        from api.dependencies import get_current_user

        mock_get_user.return_value = _make_user(
            user_id=10,
            username="alice",
            role="admin",
            user_type="enterprise",
            remaining_calculations=500,
        )
        mock_get_user.return_value.security_q1 = None
        result = await get_current_user(_make_request(), _make_api_key("jwt-token"), AsyncMock())
        assert result == {
            "id": 10,
            "username": "alice",
            "role": "admin",
            "user_type": "enterprise",
            "subscription_type": "free",
            "remaining_calculations": 500,
            "security_q1": None,
            "trial_used": 0,
            "trial_started_at": 0,
            "trial_expires_at": 0,
            "trial_plan_at_start": "",
        }


class TestGetUserWithSubscription:
    @patch("api.dependencies._get_user", new_callable=AsyncMock)
    async def test_returns_user_dict_with_subscription_type(self, mock_get_user):
        from api.dependencies import get_user_with_subscription

        mock_get_user.return_value = _make_user(
            user_id=10,
            username="alice",
            role="admin",
            user_type="permanent",
            subscription_type="enterprise",
            remaining_calculations=500,
        )
        result = await get_user_with_subscription(
            _make_request(),
            _make_api_key("jwt-token"),
            AsyncMock(),
        )
        assert result == {
            "id": 10,
            "username": "alice",
            "role": "admin",
            "user_type": "permanent",
            "subscription_type": "enterprise",
            "remaining_calculations": 500,
            "trial_used": 0,
            "trial_started_at": 0,
            "trial_expires_at": 0,
            "trial_plan_at_start": "",
        }

    @patch("api.dependencies._get_user", new_callable=AsyncMock)
    async def test_missing_subscription_type_defaults_to_free(self, mock_get_user):
        from api.dependencies import get_user_with_subscription

        mock_get_user.return_value = _make_user(
            subscription_type=cast(Optional[str], None)
        )
        result = await get_user_with_subscription(
            _make_request(),
            _make_api_key("jwt-token"),
            AsyncMock(),
        )
        assert result["subscription_type"] == "free"


class TestRequireAdmin:
    @patch("api.dependencies._get_user", new_callable=AsyncMock)
    async def test_admin_user_returns_id(self, mock_get_user):
        from api.dependencies import require_admin

        mock_get_user.return_value = _make_user(user_id=1, role="admin")
        result = await require_admin(_make_request(), _make_api_key("jwt-token"), AsyncMock())
        assert result == 1

    @patch("api.dependencies._get_user", new_callable=AsyncMock)
    async def test_non_admin_raises_403(self, mock_get_user):
        from api.dependencies import require_admin

        mock_get_user.return_value = _make_user(user_id=2, role="user")
        with pytest.raises(HTTPException) as exc_info:
            await require_admin(_make_request(), _make_api_key("jwt-token"), AsyncMock())
        assert exc_info.value.status_code == 403
