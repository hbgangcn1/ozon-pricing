from contextlib import asynccontextmanager

from sqlalchemy import event, select

from database import engine
from db.priority_group import recalculate_priority_groups
from db.products import calculate_and_update_priority_groups
from models.logistics import Logistics


@asynccontextmanager
async def _query_counter():
    count = {"n": 0}

    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith(("SELECT", "UPDATE")):
            count["n"] += 1

    event.listen(engine.sync_engine, "before_cursor_execute", before_cursor_execute)
    try:
        yield count
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", before_cursor_execute)


def _logistics(user_id: int, idx: int) -> Logistics:
    return Logistics(
        user_id=user_id,
        name=f"N1-{idx}",
        type="land" if idx % 2 == 0 else "air",
        min_days=idx + 1,
        max_days=idx + 3,
        priority_group="Z",
    )


async def test_recalculate_priority_groups_uses_select_plus_bulk_update(
    db_session, test_user
):
    uid = test_user["id"]
    db_session.add_all([_logistics(uid, idx) for idx in range(12)])
    await db_session.flush()

    async with _query_counter() as queries:
        await recalculate_priority_groups(db_session, uid)

    assert queries["n"] <= 2


async def test_calculate_and_update_priority_groups_uses_single_bulk_update(
    db_session, test_user
):
    uid = test_user["id"]
    db_session.add_all([_logistics(uid, idx) for idx in range(12)])
    await db_session.flush()

    async with _query_counter() as queries:
        await calculate_and_update_priority_groups(db_session, uid)

    rows = (
        await db_session.execute(select(Logistics).where(Logistics.user_id == uid))
    ).scalars().all()
    assert queries["n"] <= 2
    assert all(row.priority_group in {"A", "B", "C", "D", "E"} for row in rows)
