from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import select

from db.users import create_user
from models.password_reset_token import PasswordResetToken
from models.user import User


def _jti() -> str:
    return uuid4().hex


async def test_password_reset_token_insert_and_query(db_session, test_user):
    token = PasswordResetToken(jti=_jti(), user_id=test_user["id"])

    db_session.add(token)
    await db_session.flush()

    result = await db_session.execute(
        select(PasswordResetToken).where(PasswordResetToken.jti == token.jti)
    )
    row = result.scalar_one()

    assert row.user_id == test_user["id"]
    assert row.created_at is not None
    assert row.used_at is None


async def test_password_reset_token_updates_used_at(db_session, test_user):
    token = PasswordResetToken(jti=_jti(), user_id=test_user["id"])
    token_jti = token.jti
    used_at = datetime.utcnow() + timedelta(seconds=1)

    db_session.add(token)
    await db_session.flush()
    token.used_at = used_at
    await db_session.flush()
    db_session.expire_all()

    row = await db_session.get(PasswordResetToken, token_jti)

    assert row is not None
    assert row.used_at == used_at


async def test_password_reset_token_cascades_on_user_delete(db_session):
    username = f"test_reset_model_{uuid4().hex[:12]}"
    user_id = await create_user(
        db_session,
        username,
        "TestP@ss123456",
        is_test_user=True,
    )
    assert user_id is not None

    token = PasswordResetToken(jti=_jti(), user_id=user_id)
    token_jti = token.jti
    db_session.add(token)
    await db_session.flush()

    user = await db_session.get(User, user_id)
    await db_session.delete(user)
    await db_session.flush()
    db_session.expire_all()

    row = await db_session.get(PasswordResetToken, token_jti)

    assert row is None
