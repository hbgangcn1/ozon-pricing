# pyright: reportPrivateUsage=false

from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException


def _make_api_key(token_str: str):
    mock = MagicMock()
    mock.credentials = token_str
    return mock


def _make_request():
    mock = MagicMock()
    mock.cookies = {}
    return mock


def _make_user(
    user_id=1,
    username="alice",
    role="user",
    user_type="free",
    subscription_type: Optional[str] = "free",
    remaining_calculations=10,
    is_frozen=0,
):
    user = MagicMock()
    user.id = user_id
    user.username = username
    user.role = role
    user.user_type = user_type
    user.subscription_type = subscription_type
    user.remaining_calculations = remaining_calculations
    user.is_frozen = is_frozen
    return user


class TestGetUserHelper:
    @patch("api.dependencies.decode_access_token")
    async def test_valid_user_returns_user(self, mock_decode):
        mock_decode.return_value = {"sub": "1"}
        session = AsyncMock()
        session.get.return_value = _make_user(user_id=1)

        from api.dependencies import _get_user

        user = await _get_user("valid-token", session)
        assert user.id == 1

    @patch("api.dependencies.decode_access_token")
    async def test_nonexistent_user_raises_401(self, mock_decode):
        mock_decode.return_value = {"sub": "999"}
        session = AsyncMock()
        session.get.return_value = None

        from api.dependencies import _get_user

        with pytest.raises(HTTPException) as exc_info:
            await _get_user("token", session)
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "用户不存在"

    @patch("api.dependencies.decode_access_token")
    async def test_frozen_user_int1_raises_403(self, mock_decode):
        mock_decode.return_value = {"sub": "2"}
        session = AsyncMock()
        session.get.return_value = _make_user(user_id=2, is_frozen=1)

        from api.dependencies import _get_user

        with pytest.raises(HTTPException) as exc_info:
            await _get_user("token", session)
        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "账户已被冻结"

    @patch("api.dependencies.decode_access_token")
    async def test_frozen_user_bool_true_raises_403(self, mock_decode):
        mock_decode.return_value = {"sub": "2"}
        session = AsyncMock()
        session.get.return_value = _make_user(user_id=2, is_frozen=True)

        from api.dependencies import _get_user

        with pytest.raises(HTTPException) as exc_info:
            await _get_user("token", session)
        assert exc_info.value.status_code == 403

    @patch("api.dependencies.decode_access_token")
    async def test_unfrozen_user_zero_passes(self, mock_decode):
        mock_decode.return_value = {"sub": "3"}
        session = AsyncMock()
        session.get.return_value = _make_user(user_id=3, is_frozen=0)

        from api.dependencies import _get_user

        user = await _get_user("token", session)
        assert user.id == 3


class TestExtractToken:
    def test_bearer_token_preferred(self):
        from api.dependencies import _extract_token

        api_key = _make_api_key("bearer-token")
        request = MagicMock()
        request.cookies = {"access_token": "cookie-token"}
        assert _extract_token(api_key, request) == "bearer-token"

    def test_cookie_fallback(self):
        from api.dependencies import _extract_token

        request = MagicMock()
        request.method = "GET"
        request.cookies = {"access_token": "cookie-token"}
        assert _extract_token(None, request) == "cookie-token"

    def test_no_token_raises_401(self):
        from api.dependencies import _extract_token

        request = MagicMock()
        request.cookies = {}
        with pytest.raises(HTTPException) as exc_info:
            _extract_token(None, request)
        assert exc_info.value.status_code == 401

    def test_empty_credentials_uses_cookie(self):
        from api.dependencies import _extract_token

        api_key = MagicMock()
        api_key.credentials = ""
        request = MagicMock()
        request.method = "GET"
        request.cookies = {"access_token": "cookie-token"}
        assert _extract_token(api_key, request) == "cookie-token"


class TestGetCurrentUserId:
    @patch("api.dependencies._get_user", new_callable=AsyncMock)
    async def test_valid_user_returns_id(self, mock_get_user):
        mock_get_user.return_value = _make_user(user_id=42)

        from api.dependencies import get_current_user_id

        result = await get_current_user_id(
            _make_request(),
            _make_api_key("token"),
            AsyncMock(),
        )
        assert result == 42

    @patch("api.dependencies._get_user", new_callable=AsyncMock)
    async def test_nonexistent_user_raises_401(self, mock_get_user):
        mock_get_user.side_effect = HTTPException(status_code=401, detail="用户不存在")

        from api.dependencies import get_current_user_id

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_id(_make_request(), _make_api_key("token"), AsyncMock())
        assert exc_info.value.status_code == 401

    @patch("api.dependencies._get_user", new_callable=AsyncMock)
    async def test_frozen_user_raises_403(self, mock_get_user):
        mock_get_user.side_effect = HTTPException(status_code=403, detail="账户已被冻结")

        from api.dependencies import get_current_user_id

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_id(_make_request(), _make_api_key("token"), AsyncMock())
        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "账户已被冻结"


class TestGetCurrentUser:
    @patch("api.dependencies._get_user", new_callable=AsyncMock)
    async def test_valid_user_returns_dict(self, mock_get_user):
        mock_get_user.return_value = _make_user(
            user_id=10,
            username="bob",
            role="user",
            user_type="free",
            subscription_type="pro",
            remaining_calculations=5,
        )

        from api.dependencies import get_current_user

        result = await get_current_user(_make_request(), _make_api_key("token"), AsyncMock())
        assert result["id"] == 10
        assert result["username"] == "bob"
        assert result["subscription_type"] == "pro"
        assert result["remaining_calculations"] == 5

    @patch("api.dependencies._get_user", new_callable=AsyncMock)
    async def test_subscription_type_none_defaults_to_free(self, mock_get_user):
        mock_get_user.return_value = _make_user(user_id=11, subscription_type=None)

        from api.dependencies import get_current_user

        result = await get_current_user(_make_request(), _make_api_key("token"), AsyncMock())
        assert result["subscription_type"] == "free"

    @patch("api.dependencies._get_user", new_callable=AsyncMock)
    async def test_nonexistent_user_raises_401(self, mock_get_user):
        mock_get_user.side_effect = HTTPException(status_code=401, detail="用户不存在")

        from api.dependencies import get_current_user

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(_make_request(), _make_api_key("token"), AsyncMock())
        assert exc_info.value.status_code == 401

    @patch("api.dependencies._get_user", new_callable=AsyncMock)
    async def test_frozen_user_raises_403(self, mock_get_user):
        mock_get_user.side_effect = HTTPException(status_code=403, detail="账户已被冻结")

        from api.dependencies import get_current_user

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(_make_request(), _make_api_key("token"), AsyncMock())
        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "账户已被冻结"


class TestGetUserWithSubscription:
    @patch("api.dependencies._get_user", new_callable=AsyncMock)
    async def test_valid_user_returns_dict(self, mock_get_user):
        mock_get_user.return_value = _make_user(user_id=20)

        from api.dependencies import get_user_with_subscription

        result = await get_user_with_subscription(
            _make_request(),
            _make_api_key("token"),
            AsyncMock(),
        )
        assert result["id"] == 20

    @patch("api.dependencies._get_user", new_callable=AsyncMock)
    async def test_nonexistent_user_raises_401(self, mock_get_user):
        mock_get_user.side_effect = HTTPException(status_code=401, detail="用户不存在")

        from api.dependencies import get_user_with_subscription

        with pytest.raises(HTTPException) as exc_info:
            await get_user_with_subscription(
                _make_request(),
                _make_api_key("token"),
                AsyncMock(),
            )
        assert exc_info.value.status_code == 401

    @patch("api.dependencies._get_user", new_callable=AsyncMock)
    async def test_frozen_user_raises_403(self, mock_get_user):
        mock_get_user.side_effect = HTTPException(status_code=403, detail="账户已被冻结")

        from api.dependencies import get_user_with_subscription

        with pytest.raises(HTTPException) as exc_info:
            await get_user_with_subscription(
                _make_request(),
                _make_api_key("token"),
                AsyncMock(),
            )
        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "账户已被冻结"


class TestRequireAdmin:
    @patch("api.dependencies._get_user", new_callable=AsyncMock)
    async def test_admin_user_returns_id(self, mock_get_user):
        mock_get_user.return_value = _make_user(user_id=30, role="admin")

        from api.dependencies import require_admin

        result = await require_admin(_make_request(), _make_api_key("token"), AsyncMock())
        assert result == 30

    @patch("api.dependencies._get_user", new_callable=AsyncMock)
    async def test_non_admin_raises_403(self, mock_get_user):
        mock_get_user.return_value = _make_user(user_id=31, role="user")

        from api.dependencies import require_admin

        with pytest.raises(HTTPException) as exc_info:
            await require_admin(_make_request(), _make_api_key("token"), AsyncMock())
        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "需要管理员权限"

    @patch("api.dependencies._get_user", new_callable=AsyncMock)
    async def test_nonexistent_user_raises_401(self, mock_get_user):
        mock_get_user.side_effect = HTTPException(status_code=401, detail="用户不存在")

        from api.dependencies import require_admin

        with pytest.raises(HTTPException) as exc_info:
            await require_admin(_make_request(), _make_api_key("token"), AsyncMock())
        assert exc_info.value.status_code == 401

    @patch("api.dependencies._get_user", new_callable=AsyncMock)
    async def test_frozen_admin_raises_403_frozen(self, mock_get_user):
        mock_get_user.side_effect = HTTPException(status_code=403, detail="账户已被冻结")

        from api.dependencies import require_admin

        with pytest.raises(HTTPException) as exc_info:
            await require_admin(_make_request(), _make_api_key("token"), AsyncMock())
        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "账户已被冻结"
