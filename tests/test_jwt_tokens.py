import time
from datetime import timedelta

import pytest

from security.tokens import (
    create_access_token,
    decode_access_token,
    get_user_id_from_token,
    TokenExpiredError,
    TokenInvalidError,
    SECRET_KEY,
    ALGORITHM,
)


class TestCreateAccessToken:
    def test_returns_string(self):
        token = create_access_token(user_id=1, username="alice")
        assert isinstance(token, str)
        assert len(token) > 0

    def test_payload_contains_required_fields(self):
        token = create_access_token(user_id=42, username="bob", role="admin")
        payload = decode_access_token(token)
        assert payload["sub"] == "42"
        assert payload["username"] == "bob"
        assert payload["role"] == "admin"
        assert "iat" in payload
        assert "exp" in payload

    def test_default_role_is_user(self):
        token = create_access_token(user_id=1, username="alice")
        payload = decode_access_token(token)
        assert payload["role"] == "user"

    def test_custom_expires_delta(self):
        token = create_access_token(
            user_id=1,
            username="alice",
            expires_delta=timedelta(seconds=1),
        )
        payload = decode_access_token(token)
        assert payload["exp"] - payload["iat"] == 1

    def test_sub_is_string(self):
        token = create_access_token(user_id=999, username="x")
        payload = decode_access_token(token)
        assert isinstance(payload["sub"], str)


class TestDecodeAccessToken:
    def test_valid_token(self):
        token = create_access_token(user_id=1, username="alice")
        payload = decode_access_token(token)
        assert payload["sub"] == "1"
        assert payload["username"] == "alice"

    def test_expired_token_raises(self):
        token = create_access_token(
            user_id=1,
            username="alice",
            expires_delta=timedelta(seconds=-1),
        )
        with pytest.raises(TokenExpiredError):
            decode_access_token(token)

    def test_tampered_token_raises(self):
        token = create_access_token(user_id=1, username="alice")
        tampered = token[:-4] + "XXXX"
        with pytest.raises(TokenInvalidError):
            decode_access_token(tampered)

    def test_garbage_string_raises(self):
        with pytest.raises(TokenInvalidError):
            decode_access_token("not.a.jwt")

    def test_empty_string_raises(self):
        with pytest.raises(TokenInvalidError):
            decode_access_token("")

    def test_wrong_secret_raises(self):
        import jwt as pyjwt

        payload = {"sub": "1", "username": "alice"}
        wrong_key = "wrong-secret-that-is-long-enough-for-hmac-sha256"
        token = pyjwt.encode(payload, wrong_key, algorithm=ALGORITHM)
        with pytest.raises(TokenInvalidError):
            decode_access_token(token)


class TestGetUserIdFromToken:
    def test_returns_int_user_id(self):
        token = create_access_token(user_id=42, username="bob")
        assert get_user_id_from_token(token) == 42

    def test_expired_raises(self):
        token = create_access_token(
            user_id=1,
            username="alice",
            expires_delta=timedelta(seconds=-1),
        )
        with pytest.raises(TokenExpiredError):
            get_user_id_from_token(token)

    def test_missing_sub_raises(self):
        import jwt as pyjwt

        token = pyjwt.encode({"username": "alice"}, SECRET_KEY, algorithm=ALGORITHM)
        with pytest.raises(TokenInvalidError, match="sub"):
            get_user_id_from_token(token)

    def test_non_numeric_sub_raises(self):
        import jwt as pyjwt

        token = pyjwt.encode({"sub": "not-a-number"}, SECRET_KEY, algorithm=ALGORITHM)
        with pytest.raises(TokenInvalidError):
            get_user_id_from_token(token)


class TestTokenErrorHierarchy:
    def test_expired_is_token_error(self):
        assert issubclass(TokenExpiredError, Exception)

    def test_invalid_is_token_error(self):
        assert issubclass(TokenInvalidError, Exception)

    def test_catch_base_catches_both(self):
        from security.tokens import TokenError

        with pytest.raises(TokenError):
            raise TokenExpiredError("test")
        with pytest.raises(TokenError):
            raise TokenInvalidError("test")
