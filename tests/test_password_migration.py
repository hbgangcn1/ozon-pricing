import hashlib
import time

import pytest

from db.password import is_bcrypt_hash
from db.users import verify_user
from models.user import User


def _sha256_hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


@pytest.fixture
async def sha256_user(db_session):
    username = f"test_sha256_{int(time.time() * 1000)}"
    password = "LegacyP@ss123"

    user = User(
        username=username,
        password=_sha256_hash(password),
        role="user",
        user_type="free",
        subscription_type="free",
        remaining_calculations=10,
        created_at=time.strftime("%Y-%m-%d %H:%M:%S"),
        is_test_user=1,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.commit()

    yield {"id": user.id, "username": username, "password": password}

    await db_session.rollback()

    from database import AsyncSessionLocal
    from tests.conftest import _delete_test_user_async

    async with AsyncSessionLocal() as cleanup:
        try:
            await _delete_test_user_async(cleanup, user.id, username)
            await cleanup.commit()
        except Exception as exc:
            print(f"[sha256_user cleanup] FAILED: {exc}")
            await cleanup.rollback()


@pytest.mark.asyncio
async def test_sha256_user_login_migrates_to_bcrypt(db_session, sha256_user):
    from database import AsyncSessionLocal
    from sqlalchemy import select

    result = await verify_user(
        db_session, sha256_user["username"], sha256_user["password"]
    )

    assert result is not None
    assert result["username"] == sha256_user["username"]

    await db_session.commit()

    async with AsyncSessionLocal() as verify_session:
        stmt = select(User).where(User.id == sha256_user["id"])
        row = await verify_session.execute(stmt)
        updated_user = row.scalar_one_or_none()
        assert updated_user is not None
        stored = updated_user.password or ""
        assert is_bcrypt_hash(stored), "Password should have been migrated to bcrypt"


@pytest.mark.asyncio
async def test_bcrypt_user_login_no_migration(db_session, test_user):
    from database import AsyncSessionLocal
    from sqlalchemy import select

    original_hash_stmt = select(User.password).where(User.id == test_user["id"])
    original_row = await db_session.execute(original_hash_stmt)
    original_hash = original_row.scalar_one()

    result = await verify_user(db_session, test_user["username"], test_user["password"])

    assert result is not None

    async with AsyncSessionLocal() as verify_session:
        stmt = select(User.password).where(User.id == test_user["id"])
        row = await verify_session.execute(stmt)
        current_hash = row.scalar_one()
        assert current_hash == original_hash, "bcrypt hash should not be changed"


@pytest.mark.asyncio
async def test_after_migration_user_can_still_login(db_session, sha256_user):
    """After migration, user can still log in with the same password."""
    from database import AsyncSessionLocal

    await verify_user(db_session, sha256_user["username"], sha256_user["password"])
    await db_session.commit()

    async with AsyncSessionLocal() as new_session:
        result = await verify_user(
            new_session, sha256_user["username"], sha256_user["password"]
        )
        assert result is not None
        assert result["username"] == sha256_user["username"]


@pytest.mark.asyncio
async def test_failed_login_sha256_no_migration(db_session, sha256_user):
    """Failed login with SHA-256 hash → no migration happens."""
    from database import AsyncSessionLocal
    from sqlalchemy import select

    result = await verify_user(db_session, sha256_user["username"], "WrongPassword!")

    assert result is None

    async with AsyncSessionLocal() as verify_session:
        stmt = select(User.password).where(User.id == sha256_user["id"])
        row = await verify_session.execute(stmt)
        stored = row.scalar_one() or ""
        assert not is_bcrypt_hash(stored), "Failed login should not trigger migration"


@pytest.mark.asyncio
async def test_verify_user_returns_correct_fields_after_migration(
    db_session, sha256_user
):
    result = await verify_user(
        db_session, sha256_user["username"], sha256_user["password"]
    )

    assert result is not None
    assert "id" in result
    assert "username" in result
    assert "password" in result
    assert "role" in result
    assert "email" in result
    assert "user_type" in result
    assert "subscription_type" in result
    assert "remaining_calculations" in result
    assert is_bcrypt_hash(result["password"] or ""), (
        "Returned password field should be the new bcrypt hash"
    )
