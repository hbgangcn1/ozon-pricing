import asyncio
import sys
import time

import pytest

from database import AsyncSessionLocal, engine
from db.commission_categories import create, get_all, get_by_id, soft_delete, update


if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(_LOOP)


def _run(coro):
    return _LOOP.run_until_complete(coro)


async def _in_session(callback):
    await engine.dispose()
    async with AsyncSessionLocal() as session:
        try:
            return await callback(session)
        finally:
            await session.rollback()
            await engine.dispose()


def _unique_name(label: str) -> str:
    return f"test_commission_{label}_{int(time.time() * 1000000)}"


def _category_data(name: str, **overrides) -> dict:
    data = {
        "name": name,
        "rfbs_tier1_rate": 1.51,
        "rfbs_tier2_rate": 2.51,
        "rfbs_tier3_rate": 3.51,
        "fbp_tier1_rate": 1.5,
        "fbp_tier2_rate": 2.5,
        "fbp_tier3_rate": 3.5,
        "is_active": 1,
    }
    data.update(overrides)
    return data


def test_create_category_returns_id_and_persists_values():
    async def scenario(session):
        name = _unique_name("create")

        category_id = await create(session, _category_data(name))

        assert isinstance(category_id, int)
        assert category_id > 0

        row = await get_by_id(session, category_id)
        assert row is not None
        assert row["name"] == name
        assert row["fbp_tier1_rate"] == pytest.approx(1.5)
        assert row["is_active"] == 1

    _run(_in_session(scenario))


def test_create_category_returns_none_for_duplicate_name():
    async def scenario(session):
        name = _unique_name("duplicate")

        first_id = await create(session, _category_data(name))
        second_id = await create(session, _category_data(name, rfbs_tier1_rate=9.9))

        assert first_id is not None
        assert second_id is None

    _run(_in_session(scenario))


def test_get_all_categories_excludes_inactive_by_default():
    async def scenario(session):
        active_name = _unique_name("active")
        inactive_name = _unique_name("inactive")

        await create(session, _category_data(active_name))
        inactive_id = await create(session, _category_data(inactive_name))
        assert inactive_id is not None
        assert await soft_delete(session, inactive_id) is True

        rows = await get_all(session)
        names = {row["name"] for row in rows}

        assert active_name in names
        assert inactive_name not in names

    _run(_in_session(scenario))


def test_get_all_categories_include_inactive_returns_soft_deleted_rows():
    async def scenario(session):
        active_name = _unique_name("all_active")
        inactive_name = _unique_name("all_inactive")

        await create(session, _category_data(active_name))
        inactive_id = await create(session, _category_data(inactive_name))
        assert inactive_id is not None
        assert await soft_delete(session, inactive_id) is True

        rows = await get_all(session, include_inactive=True)
        by_name = {row["name"]: row for row in rows}

        assert by_name[active_name]["is_active"] == 1
        assert by_name[inactive_name]["is_active"] == 0

    _run(_in_session(scenario))


def test_get_category_by_id_returns_matching_row():
    async def scenario(session):
        name = _unique_name("by_id")
        category_id = await create(session, _category_data(name))
        assert category_id is not None

        row = await get_by_id(session, category_id)

        assert row is not None
        assert row["id"] == category_id
        assert row["name"] == name

    _run(_in_session(scenario))


def test_get_category_by_id_returns_none_for_missing_row():
    async def scenario(session):
        row = await get_by_id(session, 999999999)
        assert row is None

    _run(_in_session(scenario))


def test_update_category_changes_allowed_fields_only():
    async def scenario(session):
        name = _unique_name("update")
        category_id = await create(session, _category_data(name))
        assert category_id is not None

        result = await update(
            session,
            category_id,
            {
                "name": _unique_name("updated"),
                "rfbs_tier2_rate": 8.8,
                "not_a_field": "ignored",
            },
        )

        assert result is True

        row = await get_by_id(session, category_id)
        assert row is not None
        assert row["name"].startswith("test_commission_updated_")
        assert row["rfbs_tier2_rate"] == pytest.approx(8.8)
        assert "not_a_field" not in row

    _run(_in_session(scenario))


def test_update_category_rejects_duplicate_name():
    async def scenario(session):
        existing_name = _unique_name("existing")
        target_name = _unique_name("target")

        await create(session, _category_data(existing_name))
        target_id = await create(session, _category_data(target_name))
        assert target_id is not None

        result = await update(session, target_id, {"name": existing_name})

        assert result is False

        row = await get_by_id(session, target_id)
        assert row is not None
        assert row["name"] == target_name

    _run(_in_session(scenario))


def test_soft_delete_category_marks_row_inactive():
    async def scenario(session):
        name = _unique_name("soft_delete")
        category_id = await create(session, _category_data(name))
        assert category_id is not None

        result = await soft_delete(session, category_id)

        assert result is True

        row = await get_by_id(session, category_id)
        assert row is not None
        assert row["is_active"] == 0

    _run(_in_session(scenario))


def test_soft_delete_category_returns_false_for_missing_row():
    async def scenario(session):
        result = await soft_delete(session, 999999999)
        assert result is False

    _run(_in_session(scenario))
