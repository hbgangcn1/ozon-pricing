import asyncio
import sys
import time

import pytest
from sqlalchemy import func, select

from database import AsyncSessionLocal, engine
from db.logistics_pool import delete_all, get_all, get_by_id, get_by_ids, set_active, upsert
from models.logistics_pool import LogisticsPool


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


def _unique_token(label: str) -> str:
    return f"test_pool_{label}_{int(time.time() * 1000000)}"


def _pool_data(token: str, **overrides) -> dict:
    data = {
        "name": f"Pool {token}",
        "type": "standard",
        "min_days": 3,
        "max_days": 7,
        "price_limit_cny": 199.0,
        "price_min_cny": 20.0,
        "delivery_method": f"method_{token}",
        "fulfillment_type": "fbp",
        "destination": f"DEST_{token}",
        "fbp_service_level": f"level_{token}",
        "source_file": f"source_{token}.xlsx",
        "is_active": 1,
    }
    data.update(overrides)
    return data


def test_get_all_pool_items_returns_filtered_rows_and_total():
    async def scenario(session):
        token = _unique_token("filter")
        destination = f"DEST_SHARED_{token}"
        shared_level = f"level_shared_{token}"

        first_id = await upsert(
            session,
            _pool_data(
                f"{token}_a",
                destination=destination,
                fbp_service_level=shared_level,
            ),
        )
        second_id = await upsert(
            session,
            _pool_data(
                f"{token}_b",
                destination=destination,
                fbp_service_level=shared_level,
            ),
        )
        await upsert(
            session,
            _pool_data(f"{token}_other", destination=f"DEST_OTHER_{token}"),
        )

        rows, total = await get_all(
            session,
            destination=destination,
            fbp_service_level=shared_level,
            limit=10,
            offset=0,
        )

        ids = [row["id"] for row in rows]
        assert total == 2
        assert ids == [second_id, first_id]
        assert all(row["destination"] == destination for row in rows)

    _run(_in_session(scenario))


def test_get_all_pool_items_applies_pagination_without_changing_total():
    async def scenario(session):
        token = _unique_token("paginate")
        destination = f"DEST_PAGE_{token}"

        first_id = await upsert(
            session, _pool_data(f"{token}_a", destination=destination)
        )
        second_id = await upsert(
            session, _pool_data(f"{token}_b", destination=destination)
        )

        rows, total = await get_all(session, destination=destination, limit=1, offset=1)

        assert total == 2
        assert len(rows) == 1
        assert rows[0]["id"] == first_id
        assert rows[0]["id"] != second_id

    _run(_in_session(scenario))


def test_get_pool_item_by_id_returns_matching_row():
    async def scenario(session):
        token = _unique_token("by_id")
        pool_id = await upsert(session, _pool_data(token))

        row = await get_by_id(session, pool_id)

        assert row is not None
        assert row["id"] == pool_id
        assert row["source_file"] == f"source_{token}.xlsx"

    _run(_in_session(scenario))


def test_get_pool_item_by_id_returns_none_for_missing_row():
    async def scenario(session):
        row = await get_by_id(session, 999999999)
        assert row is None

    _run(_in_session(scenario))


def test_get_pool_items_by_ids_empty_returns_empty_dict():
    async def scenario(session):
        rows = await get_by_ids(session, [])
        assert rows == {}

    _run(_in_session(scenario))


def test_get_pool_items_by_ids_returns_multiple_matches():
    async def scenario(session):
        token = _unique_token("batch_by_id")
        first_id = await upsert(session, _pool_data(f"{token}_a"))
        second_id = await upsert(session, _pool_data(f"{token}_b"))

        rows = await get_by_ids(session, [first_id, second_id, 999999999])

        assert set(rows) == {first_id, second_id}
        assert rows[first_id]["id"] == first_id
        assert rows[second_id]["id"] == second_id

    _run(_in_session(scenario))


def test_upsert_pool_item_creates_new_row():
    async def scenario(session):
        token = _unique_token("create")

        pool_id = await upsert(session, _pool_data(token))

        assert isinstance(pool_id, int)
        assert pool_id > 0

        row = await get_by_id(session, pool_id)
        assert row is not None
        assert row["name"] == f"Pool {token}"
        assert row["price_limit_cny"] == pytest.approx(199.0)
        assert row["price_min_cny"] == pytest.approx(20.0)

    _run(_in_session(scenario))


def test_upsert_pool_item_updates_existing_row_in_place():
    async def scenario(session):
        token = _unique_token("update")
        original_id = await upsert(session, _pool_data(token))

        updated_id = await upsert(
            session,
            _pool_data(
                token,
                name=f"Updated Pool {token}",
                max_days=12,
                price_limit_cny=321.0,
                id=999999,
            ),
        )

        assert updated_id == original_id

        row = await get_by_id(session, original_id)
        assert row is not None
        assert row["name"] == f"Updated Pool {token}"
        assert row["max_days"] == 12
        assert row["price_limit_cny"] == pytest.approx(321.0)
        assert row["id"] == original_id

        count = await session.scalar(
            select(func.count(LogisticsPool.id))
            .where(LogisticsPool.source_file == f"source_{token}.xlsx")
            .where(LogisticsPool.delivery_method == f"method_{token}")
            .where(LogisticsPool.destination == f"DEST_{token}")
        )
        assert count == 1

    _run(_in_session(scenario))


def test_set_pool_item_active_updates_flag():
    async def scenario(session):
        token = _unique_token("set_active")
        pool_id = await upsert(session, _pool_data(token))

        result = await set_active(session, pool_id, 0)

        assert result is True

        row = await get_by_id(session, pool_id)
        assert row is not None
        assert row["is_active"] == 0

    _run(_in_session(scenario))


def test_set_pool_item_active_returns_false_for_missing_row():
    async def scenario(session):
        result = await set_active(session, 999999999, 0)
        assert result is False

    _run(_in_session(scenario))


def test_delete_all_pool_items_removes_every_row_and_returns_count():
    async def scenario(session):
        token = _unique_token("delete_all")
        first_id = await upsert(session, _pool_data(f"{token}_a"))
        second_id = await upsert(session, _pool_data(f"{token}_b"))

        deleted = await delete_all(session)
        assert deleted >= 2

        remaining = await session.scalar(
            select(func.count(LogisticsPool.id)).where(
                LogisticsPool.id.in_([first_id, second_id])
            )
        )
        assert remaining == 0

    _run(_in_session(scenario))
