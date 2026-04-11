# pyright: reportOptionalSubscript=false
import pytest
from db.priority_group import compute_priority_groups

_ = pytest


class TestComputePriorityGroups:
    """Unit tests for the pure priority group algorithm."""

    def test_empty_list_returns_empty(self):
        result = compute_priority_groups([])
        assert result == {}

    def test_all_invalid_get_group_e(self):
        """Logistics with missing/zero min_days or max_days -> group E."""
        items = [
            {"id": 1, "type": "land", "min_days": 0, "max_days": 10},
            {"id": 2, "type": "land", "min_days": 5, "max_days": None},
            {"id": 3, "type": "land", "min_days": None, "max_days": None},
        ]
        result = compute_priority_groups(items)
        assert result == {1: "E", 2: "E", 3: "E"}

    def test_single_valid_item_gets_group_a(self):
        """Single valid item: all 3 metrics == averages -> all <= -> group A."""
        items = [{"id": 1, "type": "air", "min_days": 5, "max_days": 10}]
        result = compute_priority_groups(items)
        assert result == {1: "A"}

    def test_mixed_valid_and_invalid(self):
        """Invalid items get E; valid items scored against valid-only avgs."""
        items = [
            {"id": 1, "type": "land", "min_days": 3, "max_days": 5},
            {"id": 2, "type": "land", "min_days": 0, "max_days": 10},
            {"id": 3, "type": "land", "min_days": 7, "max_days": 9},
        ]
        result = compute_priority_groups(items)
        assert result[2] == "E"
        # avg_min=5, avg_max=7, avg_avg=6
        # id=1: min=3<=5, max=5<=7, avg=4<=6 -> 3 -> A
        assert result[1] == "A"
        # id=3: min=7>5, max=9>7, avg=8>6 -> 0 -> D
        assert result[3] == "D"

    def test_types_calculated_independently(self):
        """Land and air logistics are scored separately."""
        items = [
            {"id": 1, "type": "land", "min_days": 10, "max_days": 20},
            {"id": 2, "type": "air", "min_days": 2, "max_days": 4},
        ]
        result = compute_priority_groups(items)
        # Each is the only item in its type -> equals average -> A
        assert result[1] == "A"
        assert result[2] == "A"

    def test_types_independent_scoring(self):
        """A slow land item is not penalized by fast air items."""
        items = [
            {"id": 1, "type": "land", "min_days": 10, "max_days": 20},
            {"id": 2, "type": "land", "min_days": 20, "max_days": 30},
            {"id": 3, "type": "air", "min_days": 1, "max_days": 2},
        ]
        result = compute_priority_groups(items)
        # land: avg_min=15, avg_max=25, avg_avg=20
        # id=1: 10<=15, 20<=25, 15<=20 -> A
        assert result[1] == "A"
        # id=2: 20>15, 30>25, 25>20 -> D
        assert result[2] == "D"
        # air: single item -> A
        assert result[3] == "A"

    def test_group_b_exact(self):
        """Construct a scenario where exactly 2 metrics pass -> B."""
        items = [
            {"id": 1, "type": "land", "min_days": 1, "max_days": 10},
            {"id": 2, "type": "land", "min_days": 3, "max_days": 6},
            {"id": 3, "type": "land", "min_days": 5, "max_days": 4},
            {"id": 4, "type": "land", "min_days": 7, "max_days": 8},
        ]
        result = compute_priority_groups(items)
        # avg_min=4, avg_max=7, avg_avg=5.5
        # id=1: min=1<=4, max=10>7, avg=5.5<=5.5 -> 2 -> B
        assert result[1] == "B"
        # id=2: min=3<=4, max=6<=7, avg=4.5<=5.5 -> 3 -> A
        assert result[2] == "A"
        # id=3: min=5>4, max=4<=7, avg=4.5<=5.5 -> 2 -> B
        assert result[3] == "B"
        # id=4: min=7>4, max=8>7, avg=7.5>5.5 -> 0 -> D
        assert result[4] == "D"

    def test_group_c_exact(self):
        """Construct a scenario where exactly 1 metric passes -> C."""
        items = [
            {"id": 1, "type": "air", "min_days": 2, "max_days": 3},
            {"id": 2, "type": "air", "min_days": 4, "max_days": 5},
            {"id": 3, "type": "air", "min_days": 3, "max_days": 8},
        ]
        result = compute_priority_groups(items)
        # avg_min=3, avg_max=5.33, avg_avg=4.17
        # id=1: min=2<=3, max=3<=5.33, avg=2.5<=4.17 -> 3 -> A
        assert result[1] == "A"
        # id=2: min=4>3, max=5<=5.33, avg=4.5>4.17 -> 1 -> C
        assert result[2] == "C"
        # id=3: min=3<=3, max=8>5.33, avg=5.5>4.17 -> 1 -> C
        assert result[3] == "C"

    def test_none_min_days_is_invalid(self):
        items = [{"id": 1, "type": "land", "min_days": None, "max_days": 5}]
        result = compute_priority_groups(items)
        assert result[1] == "E"

    def test_none_max_days_is_invalid(self):
        items = [{"id": 1, "type": "land", "min_days": 5, "max_days": None}]
        result = compute_priority_groups(items)
        assert result[1] == "E"

    def test_zero_min_days_is_invalid(self):
        items = [{"id": 1, "type": "land", "min_days": 0, "max_days": 5}]
        result = compute_priority_groups(items)
        assert result[1] == "E"

    def test_zero_max_days_is_invalid(self):
        items = [{"id": 1, "type": "land", "min_days": 5, "max_days": 0}]
        result = compute_priority_groups(items)
        assert result[1] == "E"

    def test_missing_type_defaults_to_land(self):
        items = [{"id": 1, "min_days": 5, "max_days": 10}]
        result = compute_priority_groups(items)
        assert result[1] == "A"


from db.priority_group import recalculate_priority_groups
from db.logistics_crud import (
    create_logistics,
    get_logistics_by_id,
    update_logistics,
    delete_logistics,
)


class TestRecalculatePriorityGroups:
    """Integration tests using real DB session."""

    async def test_recalculate_with_no_logistics(self, db_session, test_user):
        """No logistics -> no error, no changes."""
        await recalculate_priority_groups(db_session, test_user["id"])

    async def test_recalculate_sets_groups(self, db_session, test_user):
        """Create logistics and verify groups are computed."""
        uid = test_user["id"]
        id1 = await create_logistics(
            db_session,
            uid,
            {
                "name": "Fast",
                "type": "land",
                "min_days": 3,
                "max_days": 5,
            },
        )
        id2 = await create_logistics(
            db_session,
            uid,
            {
                "name": "Slow",
                "type": "land",
                "min_days": 10,
                "max_days": 15,
            },
        )
        await db_session.flush()

        await recalculate_priority_groups(db_session, uid)
        await db_session.flush()

        r1 = await get_logistics_by_id(db_session, id1, uid)
        r2 = await get_logistics_by_id(db_session, id2, uid)
        # Fast: min=3<=6.5, max=5<=10, avg=4<=8.25 -> A
        assert r1["priority_group"] == "A"
        # Slow: min=10>6.5, max=15>10, avg=12.5>8.25 -> D
        assert r2["priority_group"] == "D"

    async def test_recalculate_invalid_gets_e(self, db_session, test_user):
        """Logistics with zero days gets E."""
        uid = test_user["id"]
        id1 = await create_logistics(
            db_session,
            uid,
            {
                "name": "NoDays",
                "type": "air",
                "min_days": 0,
                "max_days": 0,
            },
        )
        await db_session.flush()

        await recalculate_priority_groups(db_session, uid)
        await db_session.flush()

        r1 = await get_logistics_by_id(db_session, id1, uid)
        assert r1["priority_group"] == "E"

    async def test_recalculate_does_not_affect_other_users(
        self, db_session, test_user, test_admin
    ):
        """Recalculating for user A does not change user B."""
        uid_a = test_user["id"]
        uid_b = test_admin["id"]

        await create_logistics(
            db_session,
            uid_a,
            {
                "name": "A-Fast",
                "type": "land",
                "min_days": 2,
                "max_days": 3,
            },
        )
        id_b = await create_logistics(
            db_session,
            uid_b,
            {
                "name": "B-Slow",
                "type": "land",
                "min_days": 20,
                "max_days": 30,
                "priority_group": "X",
            },
        )
        await db_session.flush()

        await recalculate_priority_groups(db_session, uid_a)
        await db_session.flush()

        r_b = await get_logistics_by_id(db_session, id_b, uid_b)
        assert r_b["priority_group"] == "X"  # Unchanged

    async def test_recalculate_splits_by_type(self, db_session, test_user):
        """Land and air are computed independently."""
        uid = test_user["id"]
        id_land = await create_logistics(
            db_session,
            uid,
            {
                "name": "Land",
                "type": "land",
                "min_days": 10,
                "max_days": 20,
            },
        )
        id_air = await create_logistics(
            db_session,
            uid,
            {
                "name": "Air",
                "type": "air",
                "min_days": 2,
                "max_days": 4,
            },
        )
        await db_session.flush()

        await recalculate_priority_groups(db_session, uid)
        await db_session.flush()

        r_land = await get_logistics_by_id(db_session, id_land, uid)
        r_air = await get_logistics_by_id(db_session, id_air, uid)
        # Each is sole item in type -> A
        assert r_land["priority_group"] == "A"
        assert r_air["priority_group"] == "A"


class TestPriorityGroupRouteIntegration:
    """Verify priority groups update after CRUD mutations,
    simulating what happens in API endpoints."""

    async def test_create_triggers_recalculation(self, db_session, test_user):
        """After creating new logistics, groups shift."""
        uid = test_user["id"]
        id1 = await create_logistics(
            db_session,
            uid,
            {
                "name": "Fast",
                "type": "land",
                "min_days": 3,
                "max_days": 5,
            },
        )
        await db_session.flush()
        await recalculate_priority_groups(db_session, uid)
        await db_session.flush()

        r1 = await get_logistics_by_id(db_session, id1, uid)
        assert r1["priority_group"] == "A"

        # Create slower item -> averages shift
        id2 = await create_logistics(
            db_session,
            uid,
            {
                "name": "Slow",
                "type": "land",
                "min_days": 10,
                "max_days": 15,
            },
        )
        await db_session.flush()
        await recalculate_priority_groups(db_session, uid)
        await db_session.flush()

        r1 = await get_logistics_by_id(db_session, id1, uid)
        r2 = await get_logistics_by_id(db_session, id2, uid)
        assert r1["priority_group"] == "A"
        assert r2["priority_group"] == "D"

    async def test_delete_triggers_recalculation(self, db_session, test_user):
        """After deleting logistics, remaining recalculated."""
        uid = test_user["id"]
        id1 = await create_logistics(
            db_session,
            uid,
            {
                "name": "Fast",
                "type": "land",
                "min_days": 3,
                "max_days": 5,
            },
        )
        id2 = await create_logistics(
            db_session,
            uid,
            {
                "name": "Slow",
                "type": "land",
                "min_days": 10,
                "max_days": 15,
            },
        )
        await db_session.flush()
        await recalculate_priority_groups(db_session, uid)
        await db_session.flush()

        # Delete fast -> slow becomes sole item -> A
        await delete_logistics(db_session, id1, uid)
        await db_session.flush()
        await recalculate_priority_groups(db_session, uid)
        await db_session.flush()

        r2 = await get_logistics_by_id(db_session, id2, uid)
        assert r2["priority_group"] == "A"

    async def test_update_days_triggers_recalculation(self, db_session, test_user):
        """Changing min/max_days causes recalculation."""
        uid = test_user["id"]
        id1 = await create_logistics(
            db_session,
            uid,
            {
                "name": "L1",
                "type": "air",
                "min_days": 3,
                "max_days": 5,
            },
        )
        id2 = await create_logistics(
            db_session,
            uid,
            {
                "name": "L2",
                "type": "air",
                "min_days": 10,
                "max_days": 15,
            },
        )
        await db_session.flush()
        await recalculate_priority_groups(db_session, uid)
        await db_session.flush()

        r2 = await get_logistics_by_id(db_session, id2, uid)
        assert r2["priority_group"] == "D"

        # Make L2 faster than L1
        await update_logistics(
            db_session,
            id2,
            uid,
            {
                "min_days": 1,
                "max_days": 2,
            },
        )
        await db_session.flush()
        await recalculate_priority_groups(db_session, uid)
        await db_session.flush()

        r1 = await get_logistics_by_id(db_session, id1, uid)
        r2 = await get_logistics_by_id(db_session, id2, uid)
        # Now L2 faster -> A, L1 slower -> D
        assert r2["priority_group"] == "A"
        assert r1["priority_group"] == "D"
