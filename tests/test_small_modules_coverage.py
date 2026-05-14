from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException


class TestExchangeRatesNonMockPath:
    @pytest.mark.asyncio
    async def test_get_exchange_rates_awaits_async_fallback(self):
        from api.routes.exchange import get_exchange_rates

        with patch("api.routes.exchange.async_get_fallback_exchange_rate", new=AsyncMock(return_value=Decimal("0.0750"))) as mock_rub:
            with patch("api.routes.exchange.async_get_fallback_usd_rate", new=AsyncMock(return_value=Decimal("7.2000"))) as mock_usd:
                result = await get_exchange_rates()

        mock_rub.assert_awaited_once()
        mock_usd.assert_awaited_once()
        assert "RUB/CNY" in result


class TestAuthHelpersValidatePassword:
    def test_too_short(self):
        from api.routes.auth.helpers import validate_password
        assert validate_password("Short1!") is False

    def test_missing_lowercase(self):
        from api.routes.auth.helpers import validate_password
        assert validate_password("ALLUPPER123456!") is False

    def test_missing_uppercase(self):
        from api.routes.auth.helpers import validate_password
        assert validate_password("alllower123456!") is False

    def test_missing_digit(self):
        from api.routes.auth.helpers import validate_password
        assert validate_password("NoDigitsHere!!!") is False

    def test_missing_special(self):
        from api.routes.auth.helpers import validate_password
        assert validate_password("NoSpecial123456") is False

    def test_valid_password(self):
        from api.routes.auth.helpers import validate_password
        assert validate_password("ValidP@ssw0rd123") is True


class TestIdempotencyKeyHeader:
    def test_too_long_raises_400(self):
        from api.middleware.idempotency import idempotency_key_header
        with pytest.raises(HTTPException) as exc:
            idempotency_key_header("x" * 256)
        assert exc.value.status_code == 400

    def test_none_returns_none(self):
        from api.middleware.idempotency import idempotency_key_header
        assert idempotency_key_header(None) is None


class TestIdempotencyGetCachedResponse:
    @pytest.mark.asyncio
    async def test_empty_key_returns_none(self):
        from api.middleware.idempotency import get_cached_response
        result = await get_cached_response(AsyncMock(), "scope", "")
        assert result is None

    @pytest.mark.asyncio
    async def test_no_row_returns_none(self):
        from api.middleware.idempotency import get_cached_response
        mock_session = AsyncMock()
        mock_session.scalar = AsyncMock(return_value=None)
        result = await get_cached_response(mock_session, "scope", "key123")
        assert result is None


class TestAuthSecurityQuestion:
    @pytest.mark.asyncio
    async def test_already_set_returns_409(self):
        from api.routes.auth_security import set_security_question

        mock_user = {"id": 1}
        mock_session = AsyncMock()
        body = MagicMock()
        body.question = "What is your favorite color?"
        body.answer = "Blue"

        with patch("api.routes.auth_security.validate_security_questions", return_value=(True, "")):
            with patch("api.routes.auth_security.validate_security_answers", return_value=(True, "")):
                with patch("api.routes.auth_security.set_user_security_question_first_time", new=AsyncMock(return_value=False)):
                    with pytest.raises(HTTPException) as exc:
                        await set_security_question(body, mock_user, mock_session)

        assert exc.value.status_code == 409
        assert "已设置" in exc.value.detail


class TestDependenciesUnit:
    def test_parse_trusted_proxy_networks_empty_string(self):
        from api.dependencies import _parse_trusted_proxy_networks
        result = _parse_trusted_proxy_networks("")
        assert result == ()

    def test_parse_trusted_proxy_networks_empty_item(self):
        from api.dependencies import _parse_trusted_proxy_networks
        result = _parse_trusted_proxy_networks("192.168.1.0/24,,10.0.0.0/8")
        assert len(result) == 2

    def test_parse_trusted_proxy_networks_invalid_entry(self):
        from api.dependencies import _parse_trusted_proxy_networks
        result = _parse_trusted_proxy_networks("192.168.1.0/24,not-an-ip")
        assert len(result) == 1

    def test_get_request_ip_no_forwarded_for(self):
        from api.dependencies import get_request_ip

        request = MagicMock()
        request.headers = {}
        request.client.host = "192.168.1.1"
        result = get_request_ip(request)
        assert result == "192.168.1.1"

    def test_get_request_ip_all_trusted(self):
        from api.dependencies import get_request_ip

        request = MagicMock()
        request.headers = {"X-Forwarded-For": "127.0.0.1"}
        request.client.host = "127.0.0.1"
        with patch("api.dependencies._trust_forwarded_for", return_value=True):
            result = get_request_ip(request)
        assert result == "127.0.0.1"

    def test_get_request_ip_xff_empty_trusted(self):
        from api.dependencies import get_request_ip

        request = MagicMock()
        request.headers = {"X-Forwarded-For": ""}
        request.client.host = "127.0.0.1"
        with patch("api.dependencies._trust_forwarded_for", return_value=True):
            result = get_request_ip(request)
        assert result == "127.0.0.1"

    def test_get_request_ip_malformed_xff(self):
        from api.dependencies import get_request_ip

        request = MagicMock()
        request.headers = {"X-Forwarded-For": "not-an-ip"}
        request.client.host = "127.0.0.1"
        with patch("api.dependencies._trust_forwarded_for", return_value=True):
            result = get_request_ip(request)
        assert result == "127.0.0.1"

    def test_get_request_ip_invalid_client_host(self):
        from api.dependencies import get_request_ip

        request = MagicMock()
        request.headers = {}
        request.client.host = "not-an-ip"
        result = get_request_ip(request)
        assert result == "not-an-ip"

    @patch("api.dependencies.os.environ.get", return_value="")
    def test_get_allowed_origins_empty(self, mock_env):
        from api.dependencies import _get_allowed_origins
        result = _get_allowed_origins()
        assert result == set()

    @patch("api.dependencies.os.environ.get", return_value="http://a.com, http://b.com")
    def test_get_allowed_origins_multiple(self, mock_env):
        from api.dependencies import _get_allowed_origins
        result = _get_allowed_origins()
        assert result == {"http://a.com", "http://b.com"}

    def test_check_csrf_origin_no_allowed_origins(self):
        from api.dependencies import _check_csrf_origin

        request = MagicMock()
        request.method = "POST"
        with patch("api.dependencies._get_allowed_origins", return_value=set()):
            with pytest.raises(HTTPException) as exc:
                _check_csrf_origin(request)
            assert exc.value.status_code == 403

    def test_check_csrf_origin_from_referer(self):
        from api.dependencies import _check_csrf_origin

        request = MagicMock()
        request.method = "POST"
        request.headers = {"referer": "http://test.com/page"}
        with patch("api.dependencies._get_allowed_origins", return_value={"http://test.com"}):
            _check_csrf_origin(request)

    def test_check_csrf_origin_invalid(self):
        from api.dependencies import _check_csrf_origin

        request = MagicMock()
        request.method = "POST"
        request.headers = {"origin": "http://evil.com"}
        with patch("api.dependencies._get_allowed_origins", return_value={"http://test.com"}):
            with pytest.raises(HTTPException) as exc:
                _check_csrf_origin(request)
            assert exc.value.status_code == 403

    def test_check_csrf_double_submit_missing_cookie(self):
        from api.dependencies import _check_csrf_double_submit

        request = MagicMock()
        request.method = "POST"
        request.cookies = {}
        request.headers = {}
        with pytest.raises(HTTPException) as exc:
            _check_csrf_double_submit(request)
        assert exc.value.status_code == 403

    def test_check_csrf_double_submit_mismatch(self):
        from api.dependencies import _check_csrf_double_submit

        request = MagicMock()
        request.method = "POST"
        request.cookies = {"csrf_token": "abc"}
        request.headers = {"x-csrf-token": "xyz"}
        with pytest.raises(HTTPException) as exc:
            _check_csrf_double_submit(request)
        assert exc.value.status_code == 403

    def test_check_csrf_double_submit_get_request(self):
        from api.dependencies import _check_csrf_double_submit

        request = MagicMock()
        request.method = "GET"
        _check_csrf_double_submit(request)

    def test_check_csrf_origin_get_request(self):
        from api.dependencies import _check_csrf_origin

        request = MagicMock()
        request.method = "GET"
        _check_csrf_origin(request)
