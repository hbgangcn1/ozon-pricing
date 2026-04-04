from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException


def _make_api_key(token_str: str):
    mock = MagicMock()
    mock.credentials = token_str
    return mock


def _make_user(
    user_id=1,
    username="alice",
    role="user",
    user_type="free",
    remaining_calculations=10,
    is_frozen=0,
):
    user = MagicMock()
    user.id = user_id
    user.username = username
    user.role = role
    user.user_type = user_type
    user.remaining_calculations = remaining_calculations
    user.is_frozen = is_frozen
    return user


class TestResolveUserId:
    @patch("api.dependencies.get_user_id_from_token")
    def test_jwt_success(self, mock_jwt):
        mock_jwt.return_value = 7
        from api.dependencies import _resolve_user_id

        assert _resolve_user_id("some-jwt") == 7

    @patch("api.dependencies.get_user_id_from_token")
    def test_jwt_failure_raises_401(self, mock_jwt):
        from security.tokens import TokenInvalidError

        mock_jwt.side_effect = TokenInvalidError("bad")

        from api.dependencies import _resolve_user_id

        with pytest.raises(HTTPException) as exc_info:
            _resolve_user_id("bad-token")
        assert exc_info.value.status_code == 401

    @patch("api.dependencies.get_user_id_from_token")
    def test_expired_token_raises_401(self, mock_jwt):
        from security.tokens import TokenExpiredError

        mock_jwt.side_effect = TokenExpiredError("expired")

        from api.dependencies import _resolve_user_id

        with pytest.raises(HTTPException) as exc_info:
            _resolve_user_id("expired-token")
        assert exc_info.value.status_code == 401


class TestGetCurrentUserId:
    @patch("api.dependencies._resolve_user_id")
    async def test_valid_user_returns_id(self, mock_resolve):
        mock_resolve.return_value = 42
        session = AsyncMock()
        session.get.return_value = _make_user(user_id=42)
        api_key = _make_api_key("token")

        from api.dependencies import get_current_user_id

        result = await get_current_user_id(api_key, session)
        assert result == 42
        session.get.assert_awaited_once()

    @patch("api.dependencies._resolve_user_id")
    async def test_user_not_found_raises_401(self, mock_resolve):
        mock_resolve.return_value = 999
        session = AsyncMock()
        session.get.return_value = None
        api_key = _make_api_key("token")

        from api.dependencies import get_current_user_id

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_id(api_key, session)
        assert exc_info.value.status_code == 401
        assert "用户不存在" in exc_info.value.detail

    @patch("api.dependencies._resolve_user_id")
    async def test_frozen_user_raises_403(self, mock_resolve):
        mock_resolve.return_value = 42
        session = AsyncMock()
        session.get.return_value = _make_user(user_id=42, is_frozen=1)
        api_key = _make_api_key("token")

        from api.dependencies import get_current_user_id

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_id(api_key, session)
        assert exc_info.value.status_code == 403

    @patch("api.dependencies._resolve_user_id")
    async def test_jwt_failure_propagates_401(self, mock_resolve):
        mock_resolve.side_effect = HTTPException(
            status_code=401, detail="无效的认证凭证"
        )
        session = AsyncMock()
        api_key = _make_api_key("bad-token")

        from api.dependencies import get_current_user_id

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_id(api_key, session)
        assert exc_info.value.status_code == 401


class TestGetCurrentUser:
    @patch("api.dependencies._resolve_user_id")
    async def test_returns_user_dict(self, mock_resolve):
        mock_resolve.return_value = 10
        session = AsyncMock()
        session.get.return_value = _make_user(
            user_id=10,
            username="alice",
            role="admin",
            user_type="enterprise",
            remaining_calculations=500,
        )
        api_key = _make_api_key("jwt-token")

        from api.dependencies import get_current_user

        result = await get_current_user(api_key, session)
        assert result == {
            "id": 10,
            "username": "alice",
            "role": "admin",
            "user_type": "enterprise",
            "remaining_calculations": 500,
        }

    @patch("api.dependencies._resolve_user_id")
    async def test_user_not_found_raises_401(self, mock_resolve):
        mock_resolve.return_value = 999
        session = AsyncMock()
        session.get.return_value = None
        api_key = _make_api_key("jwt-token")

        from api.dependencies import get_current_user

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(api_key, session)
        assert exc_info.value.status_code == 401
        assert "用户不存在" in exc_info.value.detail

    @patch("api.dependencies._resolve_user_id")
    async def test_jwt_failure_propagates_401(self, mock_resolve):
        mock_resolve.side_effect = HTTPException(
            status_code=401, detail="无效的认证凭证"
        )
        session = AsyncMock()
        api_key = _make_api_key("bad-token")

        from api.dependencies import get_current_user

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(api_key, session)
        assert exc_info.value.status_code == 401


class TestRequireAdmin:
    @patch("api.dependencies._resolve_user_id")
    async def test_admin_user_returns_id(self, mock_resolve):
        mock_resolve.return_value = 1
        session = AsyncMock()
        session.get.return_value = _make_user(user_id=1, role="admin")
        api_key = _make_api_key("jwt-token")

        from api.dependencies import require_admin

        result = await require_admin(api_key, session)
        assert result == 1

    @patch("api.dependencies._resolve_user_id")
    async def test_non_admin_raises_403(self, mock_resolve):
        mock_resolve.return_value = 2
        session = AsyncMock()
        session.get.return_value = _make_user(user_id=2, role="user")
        api_key = _make_api_key("jwt-token")

        from api.dependencies import require_admin

        with pytest.raises(HTTPException) as exc_info:
            await require_admin(api_key, session)
        assert exc_info.value.status_code == 403

    @patch("api.dependencies._resolve_user_id")
    async def test_user_not_found_raises_401(self, mock_resolve):
        mock_resolve.return_value = 999
        session = AsyncMock()
        session.get.return_value = None
        api_key = _make_api_key("jwt-token")

        from api.dependencies import require_admin

        with pytest.raises(HTTPException) as exc_info:
            await require_admin(api_key, session)
        assert exc_info.value.status_code == 401

    @patch("api.dependencies._resolve_user_id")
    async def test_jwt_failure_propagates_401(self, mock_resolve):
        mock_resolve.side_effect = HTTPException(
            status_code=401, detail="无效的认证凭证"
        )
        session = AsyncMock()
        api_key = _make_api_key("bad-token")

        from api.dependencies import require_admin

        with pytest.raises(HTTPException) as exc_info:
            await require_admin(api_key, session)
        assert exc_info.value.status_code == 401

    @patch("api.dependencies._resolve_user_id")
    async def test_jwt_valid_but_user_deleted_raises_401(self, mock_resolve):
        mock_resolve.return_value = 888
        session = AsyncMock()
        session.get.return_value = None
        api_key = _make_api_key("jwt-for-deleted-user")

        from api.dependencies import require_admin

        with pytest.raises(HTTPException) as exc_info:
            await require_admin(api_key, session)
        assert exc_info.value.status_code == 401
