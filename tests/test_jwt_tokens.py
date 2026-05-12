import time
from datetime import timedelta

import pytest

from security.tokens import (
    AUDIENCE,
    ISSUER,
    create_access_token,
    create_access_token_from_payload,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    get_user_id_from_token,
    TokenExpiredError,
    TokenInvalidError,
    TOKEN_TYPE_ACCESS,
    TOKEN_TYPE_REFRESH,
    SECRET_KEY,
    ALGORITHM,
    ACCESS_TOKEN_EXPIRE_SECONDS,
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
        assert payload["iss"] == ISSUER
        assert payload["aud"] == AUDIENCE
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

    def test_missing_iss_raises(self):
        import jwt as pyjwt

        token = pyjwt.encode(
            {
                "sub": "1",
                "username": "alice",
                "type": TOKEN_TYPE_ACCESS,
                "iat": 1,
                "exp": 2,
                "aud": AUDIENCE,
            },
            SECRET_KEY,
            algorithm=ALGORITHM,
        )
        with pytest.raises(TokenInvalidError):
            decode_access_token(token)

    def test_missing_aud_raises(self):
        import jwt as pyjwt

        token = pyjwt.encode(
            {
                "sub": "1",
                "username": "alice",
                "type": TOKEN_TYPE_ACCESS,
                "iat": 1,
                "exp": 2,
                "iss": ISSUER,
            },
            SECRET_KEY,
            algorithm=ALGORITHM,
        )
        with pytest.raises(TokenInvalidError):
            decode_access_token(token)

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

        payload = {
            "sub": "1",
            "username": "alice",
            "type": TOKEN_TYPE_ACCESS,
            "iat": 1,
            "exp": 2,
            "iss": ISSUER,
            "aud": AUDIENCE,
        }
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

        token = pyjwt.encode(
            {
                "username": "alice",
                "iat": 1,
                "exp": 9999999999,
                "iss": ISSUER,
                "aud": AUDIENCE,
            },
            SECRET_KEY,
            algorithm=ALGORITHM,
        )
        with pytest.raises(TokenInvalidError, match="sub"):
            get_user_id_from_token(token)

    def test_non_numeric_sub_raises(self):
        import jwt as pyjwt

        token = pyjwt.encode(
            {
                "sub": "not-a-number",
                "iat": 1,
                "exp": 9999999999,
                "iss": ISSUER,
                "aud": AUDIENCE,
            },
            SECRET_KEY,
            algorithm=ALGORITHM,
        )
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


class TestCreateRefreshToken:
    def test_returns_string(self):
        token = create_refresh_token(user_id=1, sid="sid-123")
        assert isinstance(token, str)
        assert len(token) > 0

    def test_payload_contains_required_fields(self):
        token = create_refresh_token(user_id=42, sid="sid-abc")
        payload = decode_refresh_token(token)
        assert payload["sub"] == "42"
        assert payload["sid"] == "sid-abc"
        assert payload["type"] == TOKEN_TYPE_REFRESH
        assert "iat" in payload
        assert "exp" in payload

    def test_default_expiry_is_days_not_minutes(self):
        token = create_refresh_token(user_id=1, sid="sid")
        payload = decode_refresh_token(token)
        ttl = payload["exp"] - payload["iat"]
        assert ttl >= 86400, f"Refresh token TTL should be ≥1 day, got {ttl}s"


class TestDecodeRefreshToken:
    def test_valid_refresh_token(self):
        token = create_refresh_token(user_id=7, sid="sid-x")
        payload = decode_refresh_token(token)
        assert payload["sub"] == "7"

    def test_expired_refresh_token_raises(self):
        token = create_refresh_token(
            user_id=1, sid="sid", expires_delta=timedelta(seconds=-1)
        )
        with pytest.raises(TokenExpiredError):
            decode_refresh_token(token)

    def test_access_token_rejected_as_refresh(self):
        access = create_access_token(user_id=1, username="alice")
        with pytest.raises(TokenInvalidError, match="refresh"):
            decode_refresh_token(access)

    def test_refresh_token_rejected_as_access(self):
        refresh = create_refresh_token(user_id=1, sid="sid")
        with pytest.raises(TokenInvalidError, match="[Rr]efresh"):
            decode_access_token(refresh)

    def test_missing_sid_raises(self):
        import jwt as pyjwt

        token = pyjwt.encode(
            {
                "sub": "1",
                "type": TOKEN_TYPE_REFRESH,
                "iat": 1,
                "exp": 9999999999,
                "iss": ISSUER,
                "aud": AUDIENCE,
            },
            SECRET_KEY,
            algorithm=ALGORITHM,
        )
        with pytest.raises(TokenInvalidError, match="sid"):
            decode_refresh_token(token)

    def test_wrong_type_raises(self):
        import jwt as pyjwt

        token = pyjwt.encode(
            {
                "sub": "1",
                "sid": "x",
                "type": "other",
                "iat": 1,
                "exp": 9999999999,
                "iss": ISSUER,
                "aud": AUDIENCE,
            },
            SECRET_KEY,
            algorithm=ALGORITHM,
        )
        with pytest.raises(TokenInvalidError, match="refresh"):
            decode_refresh_token(token)

    def test_tampered_refresh_token_raises(self):
        token = create_refresh_token(user_id=1, sid="sid")
        tampered = token[:-4] + "XXXX"
        with pytest.raises(TokenInvalidError):
            decode_refresh_token(tampered)


class TestAccessTokenTypeField:
    def test_access_token_marked_with_type(self):
        token = create_access_token(user_id=1, username="alice")
        payload = decode_access_token(token)
        assert payload["type"] == TOKEN_TYPE_ACCESS


class TestCreateAccessTokenFromPayload:
    def test_returns_string(self):
        original = create_access_token(user_id=1, username="alice", role="admin")
        original_payload = decode_access_token(original)
        new_token = create_access_token_from_payload(original_payload)
        assert isinstance(new_token, str)
        assert len(new_token) > 0

    def test_preserves_user_id_username_role(self):
        original = create_access_token(user_id=99, username="bob", role="moderator")
        original_payload = decode_access_token(original)
        new_token = create_access_token_from_payload(original_payload)
        new_payload = decode_access_token(new_token)
        assert new_payload["sub"] == "99"
        assert new_payload["username"] == "bob"
        assert new_payload["role"] == "moderator"

    def test_updates_iat_and_exp(self):
        original = create_access_token(user_id=1, username="alice")
        original_payload = decode_access_token(original)
        time.sleep(1.1)
        new_token = create_access_token_from_payload(original_payload)
        new_payload = decode_access_token(new_token)
        assert new_payload["iat"] > original_payload["iat"]
        assert new_payload["exp"] > original_payload["exp"]

    def test_default_expiry_is_standard_duration(self):
        original = create_access_token(user_id=1, username="alice")
        original_payload = decode_access_token(original)
        new_token = create_access_token_from_payload(original_payload)
        new_payload = decode_access_token(new_token)
        ttl = new_payload["exp"] - new_payload["iat"]
        assert ttl == ACCESS_TOKEN_EXPIRE_SECONDS

    def test_custom_expires_delta(self):
        original = create_access_token(user_id=1, username="alice")
        original_payload = decode_access_token(original)
        new_token = create_access_token_from_payload(
            original_payload, expires_delta=timedelta(seconds=30)
        )
        new_payload = decode_access_token(new_token)
        ttl = new_payload["exp"] - new_payload["iat"]
        assert ttl == 30

    def test_preserves_sid_if_present(self):
        token = create_access_token(
            user_id=1, username="alice", extra_claims={"sid": "session-abc"}
        )
        payload = decode_access_token(token)
        new_token = create_access_token_from_payload(payload)
        new_payload = decode_access_token(new_token)
        assert new_payload["sid"] == "session-abc"

    def test_type_field_is_access(self):
        original = create_access_token(user_id=1, username="alice")
        original_payload = decode_access_token(original)
        new_token = create_access_token_from_payload(original_payload)
        new_payload = decode_access_token(new_token)
        assert new_payload["type"] == TOKEN_TYPE_ACCESS

    def test_different_token_from_original(self):
        original = create_access_token(user_id=1, username="alice")
        original_payload = decode_access_token(original)
        time.sleep(1.1)
        new_token = create_access_token_from_payload(original_payload)
        assert new_token != original
