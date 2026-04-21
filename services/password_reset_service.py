from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import delete, select

from database import AsyncSessionLocal
from models.password_reset_token import PasswordResetToken
from security.tokens import (
    TokenExpiredError,
    TokenInvalidError,
    create_access_token,
    decode_access_token,
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
        payload = decode_access_token(token)
    except TokenExpiredError:
        return False, None, "expired"
    except TokenInvalidError:
        return False, None, "invalid"

    if payload.get("purpose") != _RESET_PURPOSE:
        return False, None, "invalid"

    jti = payload.get("jti")
    user_id = _extract_user_id(payload)
    if not isinstance(jti, str) or not jti or user_id is None:
        return False, None, "invalid"

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(PasswordResetToken)
            .where(PasswordResetToken.jti == jti)
            .with_for_update()
        )
        token_row = result.scalar_one_or_none()
        if token_row is None or token_row.user_id != user_id:
            await session.rollback()
            return False, None, "invalid"
        if token_row.used_at is not None:
            await session.rollback()
            return False, None, "used"

        token_row.used_at = datetime.utcnow()
        await session.commit()
        return True, user_id, "ok"


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
