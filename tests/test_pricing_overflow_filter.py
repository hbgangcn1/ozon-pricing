"""Task 3.1 QA: rules with disabled_by_overflow=1 must NOT participate in pricing.

Seeds 1 active rule and 1 active+overflow-disabled rule, runs the pricing entrypoint
get_user_logistics, and asserts the disabled rule is excluded.
"""
import pytest

from api.routes._pricing_helpers import get_user_logistics
from models.logistics import Logistics


@pytest.mark.asyncio
async def test_get_user_logistics_excludes_overflow_disabled(test_user, db_session):
    user_id = test_user["id"]

    kept = Logistics(
        user_id=user_id,
        name="kept-rule",
        type="land",
        is_active=1,
        disabled_by_overflow=0,
        last_used_at=0,
    )
    overflow_disabled = Logistics(
        user_id=user_id,
        name="overflow-disabled-rule",
        type="land",
        is_active=1,
        disabled_by_overflow=1,
        last_used_at=0,
    )
    inactive = Logistics(
        user_id=user_id,
        name="inactive-rule",
        type="land",
        is_active=0,
        disabled_by_overflow=0,
        last_used_at=0,
    )
    db_session.add_all([kept, overflow_disabled, inactive])
    await db_session.commit()

    rows = await get_user_logistics(db_session, user_id)
    names = {r["name"] for r in rows}

    assert "kept-rule" in names
    assert "overflow-disabled-rule" not in names
    assert "inactive-rule" not in names


@pytest.mark.asyncio
async def test_get_user_logistics_type_filter_still_applies(test_user, db_session):
    user_id = test_user["id"]

    db_session.add_all([
        Logistics(
            user_id=user_id, name="land-ok", type="land",
            is_active=1, disabled_by_overflow=0, last_used_at=0,
        ),
        Logistics(
            user_id=user_id, name="air-ok", type="air",
            is_active=1, disabled_by_overflow=0, last_used_at=0,
        ),
        Logistics(
            user_id=user_id, name="land-overflow", type="land",
            is_active=1, disabled_by_overflow=1, last_used_at=0,
        ),
    ])
    await db_session.commit()

    land_rows = await get_user_logistics(db_session, user_id, logistics_type="land")
    land_names = {r["name"] for r in land_rows}

    assert land_names == {"land-ok"}
