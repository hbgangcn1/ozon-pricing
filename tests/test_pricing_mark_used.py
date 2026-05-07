"""Task 3.2 QA: pricing route must call mark_logistics_used on winner rule ids.

Verifies winner-id collection helpers + that mark_logistics_used updates
last_used_at for winner rows only.
"""
import time

import pytest
from sqlalchemy import select

from api.routes.pricing import (
    _collect_winner_ids_from_grouped,
    _collect_winner_ids_from_res_dict,
)
from models.logistics import Logistics
from services.overflow_service import mark_logistics_used


def test_collect_winner_ids_from_res_dict_extracts_best_land_and_air():
    res_map = {
        "低价优先": {"best_land": {"id": 1, "name": "L"}, "best_air": {"id": 2, "name": "A"}},
        "速度优先": {"best_land": {"id": 1, "name": "L"}, "best_air": {"id": 3, "name": "A2"}},
    }
    assert _collect_winner_ids_from_res_dict(res_map) == {1, 2, 3}


def test_collect_winner_ids_from_res_dict_handles_none_and_missing():
    res_map = {
        "低价优先": None,
        "速度优先": {"best_land": None, "best_air": {"id": 5}},
        "x": {},
    }
    assert _collect_winner_ids_from_res_dict(res_map) == {5}


def test_collect_winner_ids_from_grouped_walks_all_groups():
    grouped = {
        "rfbs_ru": {
            "price_priority": {"best_land": {"id": 10}, "best_air": {"id": 11}},
            "speed_priority": {"best_land": {"id": 10}, "best_air": None},
            "filtered_logistics": {},
        },
        "fbp_ru": {
            "price_priority": {"best_land": {"id": 12}, "best_air": {"id": 13}},
            "speed_priority": None,
        },
    }
    assert _collect_winner_ids_from_grouped(grouped) == {10, 11, 12, 13}


@pytest.mark.asyncio
async def test_mark_logistics_used_updates_winners_only(test_user, db_session):
    user_id = test_user["id"]
    now = int(time.time())

    winner = Logistics(
        user_id=user_id, name="winner", type="land",
        is_active=1, disabled_by_overflow=0, last_used_at=0,
    )
    loser = Logistics(
        user_id=user_id, name="loser", type="land",
        is_active=1, disabled_by_overflow=0, last_used_at=0,
    )
    db_session.add_all([winner, loser])
    await db_session.commit()
    await db_session.refresh(winner)
    await db_session.refresh(loser)

    rowcount = await mark_logistics_used(db_session, user_id, {winner.id}, now=now)
    await db_session.commit()

    assert rowcount == 1

    rows = (
        await db_session.execute(
            select(Logistics).where(Logistics.user_id == user_id)
        )
    ).scalars().all()
    by_name = {r.name: r for r in rows}

    assert by_name["winner"].last_used_at == now
    assert by_name["loser"].last_used_at == 0
