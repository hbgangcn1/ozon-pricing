"""Coverage tests for security/tokens.py edge cases."""
import os
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
import jwt

import security.tokens as _tmod
from security.tokens import (
    _get_jwt_secret,
    ALGORITHM,
    ISSUER,
    TOKEN_TYPE_REFRESH,
    TokenExpiredError,
    TokenInvalidError,
    decode_password_reset_token,
    decode_refresh_token,
    revoke_refresh_token_jti,
)


@pytest.fixture(autouse=True)
def _reset_secret_cache():
    orig = _tmod._secret_key_cache
    _tmod._secret_key_cache = os.environ.get("JWT_SECRET_KEY")
    yield
    _tmod._secret_key_cache = orig


class TestGetJwtSecret:
    def test_missing_secret_raises(self):
        with patch.dict(os.environ, {"JWT_SECRET_KEY": ""}, clear=True):
            _tmod._secret_key_cache = None
            with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
                _get_jwt_secret()

    def test_short_secret_raises(self):
        with patch.dict(os.environ, {"JWT_SECRET_KEY": "short"}, clear=True):
            _tmod._secret_key_cache = None
            with pytest.raises(RuntimeError, match="too short"):
                _get_jwt_secret()


class TestDecodePasswordResetToken:
    def test_refresh_token_type_rejected(self):
        secret = os.environ["JWT_SECRET_KEY"]
        now = datetime.now(timezone.utc)
        payload = {
            "sub": "1",
            "sid": "sid",
            "jti": "abc",
            "type": TOKEN_TYPE_REFRESH,
            "token_type": TOKEN_TYPE_REFRESH,
            "iat": now,
            "exp": now + timedelta(days=7),
        }
        token = jwt.encode(payload, secret, algorithm=ALGORITHM)
        with pytest.raises(TokenInvalidError, match="Refresh token"):
            decode_password_reset_token(token)

    def test_non_password_reset_purpose_rejected(self):
        secret = os.environ["JWT_SECRET_KEY"]
        now_ts = int(time.time())
        payload = {
            "sub": "1",
            "iat": now_ts,
            "exp": now_ts + 86400,
        }
        token = jwt.encode(payload, secret, algorithm=ALGORITHM)
        with pytest.raises(TokenInvalidError, match="不是 password reset"):
            decode_password_reset_token(token)


class TestDecodeRefreshToken:
    def test_missing_sub_rejected(self):
        secret = os.environ["JWT_SECRET_KEY"]
        now = datetime.now(timezone.utc)
        payload = {
            "sid": "sid123",
            "jti": "abc",
            "type": TOKEN_TYPE_REFRESH,
            "token_type": TOKEN_TYPE_REFRESH,
            "iss": ISSUER,
            "aud": "cbprice-web",
            "iat": now,
            "exp": now + timedelta(days=7),
        }
        token = jwt.encode(payload, secret, algorithm=ALGORITHM)
        with pytest.raises(TokenInvalidError, match="sub"):
            decode_refresh_token(token)


class TestRevokeRefreshTokenJti:
    def test_none_jti_ignored(self):
        revoke_refresh_token_jti(None)

    def test_empty_string_ignored(self):
        revoke_refresh_token_jti("")

    def test_non_string_ignored(self):
        revoke_refresh_token_jti(123)
