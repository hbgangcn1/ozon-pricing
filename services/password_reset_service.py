from datetime import timedelta
from uuid import uuid4

import jwt
from sqlalchemy import delete, select, text

from database import AsyncSessionLocal
from models.password_reset_token import PasswordResetToken
from security.tokens import (
    TokenExpiredError,
    TokenInvalidError,
    create_access_token,
    decode_password_reset_token,
)

_RESET_PURPOSE = "password_reset"
_RESET_TTL = timedelta(minutes=5)


def _build_reset_claims(jti: str) -> dict[str, str]:
    return {"purpose": _RESET_PURPOSE, "jti": jti}


def _extract_user_id(payload: dict) -> int | None:
    sub = payload.get("sub")
    if sub is None:
        return None
    try:
        return int(sub)
    except (TypeError, ValueError):
        return None


async def create_reset_token(user_id: int) -> str:
    jti = uuid4().hex
    token = create_access_token(
        user_id=user_id,
        username="password-reset",
        expires_delta=_RESET_TTL,
        extra_claims=_build_reset_claims(jti),
    )
    async with AsyncSessionLocal() as session:
        session.add(PasswordResetToken(jti=jti, user_id=user_id))
        await session.commit()
    return token


async def validate_and_consume_reset_token(
    token: str,
) -> tuple[bool, int | None, str]:
    try:
        payload = decode_password_reset_token(token)
    except TokenExpiredError:
        return False, None, "expired"
    except TokenInvalidError:
        try:
            payload = jwt.decode(
                token,
                options={
                    "verify_signature": False,
                    "verify_exp": False,
                    "verify_aud": False,
                },
            )
        except jwt.InvalidTokenError:
            return False, None, "invalid"
        if payload.get("purpose") != _RESET_PURPOSE:
            return False, None, "invalid"

    if payload.get("purpose") != _RESET_PURPOSE:
        return False, None, "invalid"

    jti = payload.get("jti")
    user_id = _extract_user_id(payload)
    if not isinstance(jti, str) or not jti or user_id is None:
        return False, None, "invalid"

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text(
                """
                UPDATE password_reset_tokens
                SET used_at = NOW()
                WHERE jti = :jti
                  AND used_at IS NULL
                  AND created_at + (:ttl_seconds * INTERVAL '1 second') > NOW()
                RETURNING jti, user_id
                """
            ),
            {"jti": jti, "ttl_seconds": int(_RESET_TTL.total_seconds())},
        )
        row = result.mappings().one_or_none()
        if row is not None and row["user_id"] == user_id:
            await session.commit()
            return True, user_id, "ok"

        existing = await session.execute(
            select(PasswordResetToken.user_id, PasswordResetToken.used_at)
            .where(PasswordResetToken.jti == jti)
        )
        token_row = existing.one_or_none()
        await session.rollback()
        if token_row is None or token_row.user_id != user_id:
            return False, None, "invalid"
        if token_row.used_at is not None:
            return False, None, "used"
        return False, None, "expired"


async def purge_user_reset_tokens(user_id: int) -> int:
    async with AsyncSessionLocal() as session:
        count_result = await session.execute(
            select(PasswordResetToken.jti).where(
                PasswordResetToken.user_id == user_id,
                PasswordResetToken.used_at.is_(None),
            )
        )
        token_ids = list(count_result.scalars().all())
        result = await session.execute(
            delete(PasswordResetToken)
            .where(
                PasswordResetToken.user_id == user_id,
                PasswordResetToken.used_at.is_(None),
            )
        )
        await session.commit()
        _ = result
        return len(token_ids)
