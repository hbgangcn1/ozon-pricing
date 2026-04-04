import time
from unittest.mock import patch, MagicMock

import pytest
from fastapi import HTTPException

from security.tokens import create_access_token


def _make_api_key(token_str: str):
    mock = MagicMock()
    mock.credentials = token_str
    return mock


class TestGetCurrentUserId:
    def _call(self, token_str):
        from api.dependencies import get_current_user_id

        api_key = _make_api_key(token_str)
        return get_current_user_id.__wrapped__(api_key)

    @patch("api.dependencies.get_db_connection")
    @patch("api.dependencies.get_user_id_from_token")
    def test_jwt_token_returns_user_id(self, mock_jwt, mock_db):
        mock_jwt.return_value = 42
        ctx = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.return_value = (42,)
        ctx.__enter__ = MagicMock(return_value=(MagicMock(), cursor))
        ctx.__exit__ = MagicMock(return_value=False)
        mock_db.return_value = ctx

        from api.dependencies import get_current_user_id, _resolve_user_id

        api_key = _make_api_key("jwt-token")
        result = get_current_user_id(api_key)
        assert result == 42

    @patch("api.dependencies.get_db_connection")
    @patch("api.dependencies.get_user_id_from_token")
    def test_fallback_to_username_lookup(self, mock_jwt, mock_db):
        from security.tokens import TokenInvalidError

        mock_jwt.side_effect = TokenInvalidError("bad")

        ctx = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.return_value = (99,)
        ctx.__enter__ = MagicMock(return_value=(MagicMock(), cursor))
        ctx.__exit__ = MagicMock(return_value=False)
        mock_db.return_value = ctx

        from api.dependencies import get_current_user_id

        api_key = _make_api_key("alice")
        result = get_current_user_id(api_key)
        assert result == 99

    @patch("api.dependencies.get_db_connection")
    @patch("api.dependencies.get_user_id_from_token")
    def test_invalid_token_and_unknown_user_raises_401(self, mock_jwt, mock_db):
        from security.tokens import TokenInvalidError

        mock_jwt.side_effect = TokenInvalidError("bad")

        ctx = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.return_value = None
        ctx.__enter__ = MagicMock(return_value=(MagicMock(), cursor))
        ctx.__exit__ = MagicMock(return_value=False)
        mock_db.return_value = ctx

        from api.dependencies import get_current_user_id

        api_key = _make_api_key("nobody")
        with pytest.raises(HTTPException) as exc_info:
            get_current_user_id(api_key)
        assert exc_info.value.status_code == 401

    @patch("api.dependencies.get_db_connection")
    @patch("api.dependencies.get_user_id_from_token")
    def test_jwt_valid_but_user_not_in_db_raises_401(self, mock_jwt, mock_db):
        """JWT decodes successfully but user_id not found in DB."""
        mock_jwt.return_value = 999

        ctx = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.return_value = None
        ctx.__enter__ = MagicMock(return_value=(MagicMock(), cursor))
        ctx.__exit__ = MagicMock(return_value=False)
        mock_db.return_value = ctx

        from api.dependencies import get_current_user_id

        api_key = _make_api_key("valid-jwt-deleted-user")
        with pytest.raises(HTTPException) as exc_info:
            get_current_user_id(api_key)
        assert exc_info.value.status_code == 401
        assert "用户不存在" in exc_info.value.detail


class TestGetCurrentUser:
    def _make_db_ctx(self, cursor):
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=(MagicMock(), cursor))
        ctx.__exit__ = MagicMock(return_value=False)
        return ctx

    @patch("api.dependencies.get_db_connection")
    @patch("api.dependencies._resolve_user_id")
    def test_returns_user_dict(self, mock_resolve, mock_db):
        mock_resolve.return_value = 10

        cursor = MagicMock()
        cursor.fetchone.return_value = (10, "alice", "admin", "enterprise", 500)
        mock_db.return_value = self._make_db_ctx(cursor)

        from api.dependencies import get_current_user

        api_key = _make_api_key("jwt-token")
        result = get_current_user(api_key)
        assert result == {
            "id": 10,
            "username": "alice",
            "role": "admin",
            "user_type": "enterprise",
            "remaining_calculations": 500,
        }

    @patch("api.dependencies.get_db_connection")
    @patch("api.dependencies._resolve_user_id")
    def test_user_not_found_raises_401(self, mock_resolve, mock_db):
        mock_resolve.return_value = 999

        cursor = MagicMock()
        cursor.fetchone.return_value = None
        mock_db.return_value = self._make_db_ctx(cursor)

        from api.dependencies import get_current_user

        api_key = _make_api_key("jwt-token")
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(api_key)
        assert exc_info.value.status_code == 401
        assert "用户不存在" in exc_info.value.detail


class TestResolveUserId:
    @patch("api.dependencies.get_db_connection")
    @patch("api.dependencies.get_user_id_from_token")
    def test_jwt_success(self, mock_jwt, mock_db):
        mock_jwt.return_value = 7
        from api.dependencies import _resolve_user_id

        assert _resolve_user_id("some-jwt") == 7

    @patch("api.dependencies.get_db_connection")
    @patch("api.dependencies.get_user_id_from_token")
    def test_fallback_success(self, mock_jwt, mock_db):
        from security.tokens import TokenInvalidError

        mock_jwt.side_effect = TokenInvalidError("bad")

        ctx = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.return_value = (55,)
        ctx.__enter__ = MagicMock(return_value=(MagicMock(), cursor))
        ctx.__exit__ = MagicMock(return_value=False)
        mock_db.return_value = ctx

        from api.dependencies import _resolve_user_id

        assert _resolve_user_id("alice") == 55

    @patch("api.dependencies.get_db_connection")
    @patch("api.dependencies.get_user_id_from_token")
    def test_both_fail_raises_401(self, mock_jwt, mock_db):
        from security.tokens import TokenInvalidError

        mock_jwt.side_effect = TokenInvalidError("bad")

        ctx = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.return_value = None
        ctx.__enter__ = MagicMock(return_value=(MagicMock(), cursor))
        ctx.__exit__ = MagicMock(return_value=False)
        mock_db.return_value = ctx

        from api.dependencies import _resolve_user_id

        with pytest.raises(HTTPException) as exc_info:
            _resolve_user_id("nobody")
        assert exc_info.value.status_code == 401


class TestRequireAdmin:
    @patch("api.dependencies.get_db_connection")
    @patch("api.dependencies.get_user_id_from_token")
    def test_admin_user_returns_id(self, mock_jwt, mock_db):
        mock_jwt.return_value = 1

        ctx = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.return_value = ("admin",)
        ctx.__enter__ = MagicMock(return_value=(MagicMock(), cursor))
        ctx.__exit__ = MagicMock(return_value=False)
        mock_db.return_value = ctx

        from api.dependencies import require_admin

        api_key = _make_api_key("jwt-token")
        result = require_admin(api_key)
        assert result == 1

    @patch("api.dependencies.get_db_connection")
    @patch("api.dependencies.get_user_id_from_token")
    def test_non_admin_raises_403(self, mock_jwt, mock_db):
        mock_jwt.return_value = 2

        ctx = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.return_value = ("user",)
        ctx.__enter__ = MagicMock(return_value=(MagicMock(), cursor))
        ctx.__exit__ = MagicMock(return_value=False)
        mock_db.return_value = ctx

        from api.dependencies import require_admin

        api_key = _make_api_key("jwt-token")
        with pytest.raises(HTTPException) as exc_info:
            require_admin(api_key)
        assert exc_info.value.status_code == 403

    @patch("api.dependencies.get_db_connection")
    @patch("api.dependencies.get_user_id_from_token")
    def test_unknown_user_raises_401(self, mock_jwt, mock_db):
        from security.tokens import TokenInvalidError

        mock_jwt.side_effect = TokenInvalidError("bad")

        ctx = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.return_value = None
        ctx.__enter__ = MagicMock(return_value=(MagicMock(), cursor))
        ctx.__exit__ = MagicMock(return_value=False)
        mock_db.return_value = ctx

        from api.dependencies import require_admin

        api_key = _make_api_key("nobody")
        with pytest.raises(HTTPException) as exc_info:
            require_admin(api_key)
        assert exc_info.value.status_code == 401

    @patch("api.dependencies.get_db_connection")
    @patch("api.dependencies.get_user_id_from_token")
    def test_jwt_valid_but_user_deleted_raises_401(self, mock_jwt, mock_db):
        mock_jwt.return_value = 888

        ctx = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.return_value = None
        ctx.__enter__ = MagicMock(return_value=(MagicMock(), cursor))
        ctx.__exit__ = MagicMock(return_value=False)
        mock_db.return_value = ctx

        from api.dependencies import require_admin

        api_key = _make_api_key("jwt-for-deleted-user")
        with pytest.raises(HTTPException) as exc_info:
            require_admin(api_key)
        assert exc_info.value.status_code == 401
