from datetime import timedelta

import pytest

from sqlalchemy import select

from models.password_reset_token import PasswordResetToken
from security.tokens import (
    TokenInvalidError,
    create_access_token,
    decode_access_token,
    decode_password_reset_token,
)
from services.password_reset_service import (
    create_reset_token,
    purge_user_reset_tokens,
    validate_and_consume_reset_token,
)


async def test_create_reset_token_success(db_session, test_user):
    token = await create_reset_token(test_user["id"])
    payload = decode_password_reset_token(token)

    result = await db_session.execute(
        select(PasswordResetToken).where(PasswordResetToken.jti == payload["jti"])
    )
    row = result.scalar_one()

    assert payload["purpose"] == "password_reset"
    assert row.user_id == test_user["id"]
    assert row.used_at is None


async def test_validate_and_consume_reset_token_marks_used(db_session, test_user):
    token = await create_reset_token(test_user["id"])
    payload = decode_password_reset_token(token)

    ok, user_id, reason = await validate_and_consume_reset_token(token)
    db_session.expire_all()
    row = await db_session.get(PasswordResetToken, payload["jti"])

    assert ok is True
    assert user_id == test_user["id"]
    assert reason == "ok"
    assert row is not None
    assert row.used_at is not None


async def test_validate_and_consume_reset_token_rejects_replay(test_user):
    token = await create_reset_token(test_user["id"])

    first = await validate_and_consume_reset_token(token)
    second = await validate_and_consume_reset_token(token)

    assert first == (True, test_user["id"], "ok")
    assert second == (False, None, "used")


async def test_validate_and_consume_reset_token_rejects_expired(test_user):
    expired = create_access_token(
        user_id=test_user["id"],
        username="password-reset",
        expires_delta=timedelta(seconds=-1),
        extra_claims={"purpose": "password_reset", "jti": "expired-jti"},
    )

    assert await validate_and_consume_reset_token(expired) == (False, None, "expired")


async def test_validate_and_consume_reset_token_rejects_wrong_purpose(test_user):
    token = create_access_token(
        user_id=test_user["id"],
        username="password-reset",
        extra_claims={"purpose": "not-reset", "jti": "wrong-purpose-jti"},
    )

    assert await validate_and_consume_reset_token(token) == (False, None, "invalid")


async def test_purge_user_reset_tokens_returns_deleted_count(db_session, test_user):
    first_token = await create_reset_token(test_user["id"])
    second_token = await create_reset_token(test_user["id"])
    first = decode_password_reset_token(first_token)
    second = decode_password_reset_token(second_token)
    await validate_and_consume_reset_token(first_token)

    deleted = await purge_user_reset_tokens(test_user["id"])
    db_session.expire_all()

    used_row = await db_session.get(PasswordResetToken, first["jti"])
    unused_row = await db_session.get(PasswordResetToken, second["jti"])

    assert deleted == 1
    assert used_row is not None
    assert used_row.used_at is not None
    assert unused_row is None


async def test_reset_token_rejected_as_access_token(test_user):
    """W6-SEC-NEW-1: reset token must not be usable as Bearer access token."""
    token = await create_reset_token(test_user["id"])
    with pytest.raises(TokenInvalidError, match="Password reset token"):
        decode_access_token(token)
