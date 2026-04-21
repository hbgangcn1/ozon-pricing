import time

from db.admin import batch_update_users
from db.users import create_user
from models.user import User


async def _create_test_user(db_session, username_prefix: str) -> int:
    timestamp = int(time.time() * 1000)
    user_id = await create_user(
        db_session,
        f"{username_prefix}_{timestamp}",
        "Password123!",
        email=f"{username_prefix}_{timestamp}@test.com",
        is_test_user=True,
    )
    assert user_id is not None
    return user_id


async def test_batch_update_users_updates_multiple_users_in_single_query(
    db_session, test_user, test_admin
):
    extra_user_id = await _create_test_user(db_session, "batch_update")

    count = await batch_update_users(
        db_session,
        [test_user["id"], extra_user_id],
        {"remaining_calculations": 66},
        test_admin["id"],
    )

    first_user = await db_session.get(User, test_user["id"])
    second_user = await db_session.get(User, extra_user_id)
    assert first_user is not None
    assert second_user is not None
    assert count == 2
    assert first_user.remaining_calculations == 66
    assert second_user.remaining_calculations == 66


async def test_batch_update_users_skips_admin_self(db_session, test_admin):
    original_admin = await db_session.get(User, test_admin["id"])
    assert original_admin is not None
    original_value = original_admin.remaining_calculations

    count = await batch_update_users(
        db_session,
        [test_admin["id"]],
        {"remaining_calculations": 123},
        test_admin["id"],
    )

    refreshed_admin = await db_session.get(User, test_admin["id"])
    assert refreshed_admin is not None
    assert count == 0
    assert refreshed_admin.remaining_calculations == original_value
