"""Password reset token lifecycle invariants.

Guards single-use semantics, expiry handling, and bulk purge of
unused tokens for a user. The 4 reason codes returned by
validate_and_consume_reset_token (ok/expired/invalid/used) form the
public contract consumed by api.routes.auth password-reset endpoints.
"""
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from models.password_reset_token import PasswordResetToken
from security.tokens import create_access_token
from services.password_reset_service import (
    create_reset_token,
    purge_user_reset_tokens,
    validate_and_consume_reset_token,
)


def _forge_reset_token(user_id: int, jti: str, *,
                       expires_delta: timedelta = timedelta(minutes=5)) -> str:
    return create_access_token(
        user_id=user_id,
        username="password-reset",
        expires_delta=expires_delta,
        extra_claims={"purpose": "password_reset", "jti": jti},
    )


@pytest.mark.asyncio
async def test_create_reset_token_persists_jti(db_session, test_user):
    uid = test_user["id"]
    token = await create_reset_token(uid)

    assert isinstance(token, str) and len(token) > 20
    rows = await db_session.execute(
        select(PasswordResetToken).where(PasswordResetToken.user_id == uid)
    )
    persisted = rows.scalars().all()
    assert len(persisted) == 1
    assert persisted[0].used_at is None


@pytest.mark.asyncio
async def test_validate_ok_marks_used_and_returns_user_id(test_user):
    uid = test_user["id"]
    token = await create_reset_token(uid)

    ok, returned_uid, reason = await validate_and_consume_reset_token(token)

    assert ok is True
    assert returned_uid == uid
    assert reason == "ok"


@pytest.mark.asyncio
async def test_validate_used_token_returns_used(test_user):
    uid = test_user["id"]
    token = await create_reset_token(uid)
    await validate_and_consume_reset_token(token)

    ok, returned_uid, reason = await validate_and_consume_reset_token(token)

    assert ok is False
    assert returned_uid is None
    assert reason == "used"


@pytest.mark.asyncio
async def test_validate_expired_token_returns_expired(test_user):
    uid = test_user["id"]
    expired_token = _forge_reset_token(
        uid, uuid4().hex, expires_delta=timedelta(seconds=-1),
    )

    ok, returned_uid, reason = await validate_and_consume_reset_token(
        expired_token
    )

    assert ok is False
    assert returned_uid is None
    assert reason == "expired"


@pytest.mark.asyncio
async def test_validate_garbage_token_returns_invalid():
    ok, returned_uid, reason = await validate_and_consume_reset_token(
        "not.a.jwt"
    )

    assert ok is False
    assert returned_uid is None
    assert reason == "invalid"


@pytest.mark.asyncio
async def test_validate_unknown_jti_returns_invalid(test_user):
    uid = test_user["id"]
    forged = _forge_reset_token(uid, uuid4().hex)

    ok, returned_uid, reason = await validate_and_consume_reset_token(forged)

    assert ok is False
    assert returned_uid is None
    assert reason == "invalid"


@pytest.mark.asyncio
async def test_validate_access_token_returns_invalid(test_user):
    uid = test_user["id"]
    access_token = create_access_token(
        user_id=uid, username="x", expires_delta=timedelta(minutes=5),
    )

    ok, _, reason = await validate_and_consume_reset_token(access_token)

    assert ok is False
    assert reason == "invalid"


@pytest.mark.asyncio
async def test_purge_removes_only_unused_tokens_for_user(
    db_session, test_user, test_admin
):
    uid = test_user["id"]
    other_uid = test_admin["id"]
    await create_reset_token(uid)
    await create_reset_token(uid)
    consumed_token = await create_reset_token(uid)
    await create_reset_token(other_uid)
    await validate_and_consume_reset_token(consumed_token)

    deleted = await purge_user_reset_tokens(uid)
    await db_session.commit()

    assert deleted == 2
    remaining = await db_session.execute(
        select(PasswordResetToken).where(PasswordResetToken.user_id == uid)
    )
    rows = remaining.scalars().all()
    assert len(rows) == 1
    assert rows[0].used_at is not None

    other_remaining = await db_session.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.user_id == other_uid
        )
    )
    assert len(other_remaining.scalars().all()) == 1


@pytest.mark.asyncio
async def test_purge_returns_zero_when_no_tokens(test_user):
    uid = test_user["id"]

    deleted = await purge_user_reset_tokens(uid)

    assert deleted == 0
