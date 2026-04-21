import time

from db.admin import get_all_users, get_logistics_counts_for_users
from db.users import create_user
from models.logistics import Logistics


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


async def test_get_logistics_counts_for_users_empty_returns_empty_dict(db_session):
    result = await get_logistics_counts_for_users(db_session, [])
    assert result == {}


async def test_get_logistics_counts_for_users_returns_multiple_counts(db_session):
    first_id = await _create_test_user(db_session, "helper_count_a")
    second_id = await _create_test_user(db_session, "helper_count_b")
    db_session.add_all(
        [
            Logistics(user_id=first_id, name="helper_l1"),
            Logistics(user_id=first_id, name="helper_l2"),
            Logistics(user_id=second_id, name="helper_l3"),
        ]
    )
    await db_session.flush()

    result = await get_logistics_counts_for_users(db_session, [first_id, second_id])

    assert result[first_id] == 2
    assert result[second_id] == 1


async def test_get_all_users_returns_batched_logistics_counts(db_session):
    prefix = f"batch_count_{int(time.time() * 1000)}"
    first_id = await _create_test_user(db_session, f"{prefix}_a")
    second_id = await _create_test_user(db_session, f"{prefix}_b")
    db_session.add_all(
        [
            Logistics(user_id=first_id, name=f"{prefix}_l1"),
            Logistics(user_id=first_id, name=f"{prefix}_l2"),
            Logistics(user_id=second_id, name=f"{prefix}_l3"),
        ]
    )
    await db_session.flush()

    result = await get_all_users(db_session, search=prefix, page=1, per_page=10)

    counts = {row["id"]: row["current_logistics_count"] for row in result["users"]}
    assert counts[first_id] == 2
    assert counts[second_id] == 1
