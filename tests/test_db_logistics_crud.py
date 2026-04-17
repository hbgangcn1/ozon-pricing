# pyright: reportPrivateUsage=false, reportOptionalSubscript=false, reportUnusedVariable=false

from decimal import Decimal

import pytest
from models.logistics import Logistics
from db.logistics_crud import (
    get_logistics_list,
    get_logistics_by_filters,
    get_logistics_by_id,
    create_logistics,
    update_logistics,
    delete_logistics,
    batch_delete_logistics,
    _logistics_to_dict,
)


def _make_logistics(user_id: int, **kwargs) -> Logistics:
    return Logistics(user_id=user_id, **kwargs)


async def _insert(session, record: Logistics) -> Logistics:
    session.add(record)
    await session.flush()
    return record


class TestLogisticsToDict:
    async def test_returns_dict(self, db_session, test_user):
        record = await _insert(db_session, _make_logistics(test_user["id"], name="DHL"))
        result = _logistics_to_dict(record)
        assert isinstance(result, dict)

    async def test_dict_contains_all_column_names(self, db_session, test_user):
        record = await _insert(db_session, _make_logistics(test_user["id"], name="UPS"))
        result = _logistics_to_dict(record)
        expected_keys = {c.name for c in Logistics.__table__.columns}
        assert set(result.keys()) == expected_keys

    async def test_dict_values_match_record(self, db_session, test_user):
        record = await _insert(
            db_session, _make_logistics(test_user["id"], name="FedEx", type="air")
        )
        result = _logistics_to_dict(record)
        assert result["name"] == "FedEx"
        assert result["type"] == "air"
        assert result["user_id"] == test_user["id"]
        assert result["id"] == record.id


class TestGetLogisticsList:
    async def test_empty_returns_empty_list_and_zero(self, db_session, test_user):
        rows, total = await get_logistics_list(db_session, test_user["id"])
        assert rows == []
        assert total == 0

    async def test_returns_records_for_user(self, db_session, test_user):
        await _insert(db_session, _make_logistics(test_user["id"], name="A"))
        await _insert(db_session, _make_logistics(test_user["id"], name="B"))
        rows, total = await get_logistics_list(db_session, test_user["id"])
        assert total == 2
        assert len(rows) == 2

    async def test_does_not_return_other_users_records(
        self, db_session, test_user, test_admin
    ):
        await _insert(db_session, _make_logistics(test_admin["id"], name="Other"))
        rows, total = await get_logistics_list(db_session, test_user["id"])
        assert total == 0
        assert rows == []

    async def test_rows_are_dicts(self, db_session, test_user):
        await _insert(db_session, _make_logistics(test_user["id"], name="X"))
        rows, total = await get_logistics_list(db_session, test_user["id"])
        assert total == 1
        assert isinstance(rows[0], dict)

    async def test_ordered_by_id_desc(self, db_session, test_user):
        r1 = await _insert(db_session, _make_logistics(test_user["id"], name="First"))
        r2 = await _insert(db_session, _make_logistics(test_user["id"], name="Second"))
        rows, _ = await get_logistics_list(db_session, test_user["id"])
        assert rows[0]["id"] == r2.id
        assert rows[1]["id"] == r1.id

    async def test_limit_pagination(self, db_session, test_user):
        for i in range(5):
            await _insert(db_session, _make_logistics(test_user["id"], name=f"L{i}"))
        rows, total = await get_logistics_list(
            db_session, test_user["id"], limit=2, offset=0
        )
        assert total == 5
        assert len(rows) == 2

    async def test_offset_pagination(self, db_session, test_user):
        for i in range(5):
            await _insert(db_session, _make_logistics(test_user["id"], name=f"L{i}"))
        rows, total = await get_logistics_list(
            db_session, test_user["id"], limit=100, offset=3
        )
        assert total == 5
        assert len(rows) == 2

    async def test_limit_offset_combined(self, db_session, test_user):
        for i in range(10):
            await _insert(db_session, _make_logistics(test_user["id"], name=f"L{i}"))
        rows, total = await get_logistics_list(
            db_session, test_user["id"], limit=3, offset=4
        )
        assert total == 10
        assert len(rows) == 3

    async def test_offset_beyond_total_returns_empty(self, db_session, test_user):
        await _insert(db_session, _make_logistics(test_user["id"], name="Only"))
        rows, total = await get_logistics_list(
            db_session, test_user["id"], limit=10, offset=100
        )
        assert total == 1
        assert rows == []

    async def test_returns_tuple(self, db_session, test_user):
        result = await get_logistics_list(db_session, test_user["id"])
        assert isinstance(result, tuple)
        assert len(result) == 2


class TestGetLogisticsById:
    async def test_found_returns_dict(self, db_session, test_user):
        record = await _insert(
            db_session, _make_logistics(test_user["id"], name="Found")
        )
        result = await get_logistics_by_id(db_session, record.id, test_user["id"])
        assert result is not None
        assert isinstance(result, dict)
        assert result["id"] == record.id

    async def test_wrong_id_returns_none(self, db_session, test_user):
        result = await get_logistics_by_id(db_session, 999999999, test_user["id"])
        assert result is None

    async def test_wrong_user_id_returns_none(self, db_session, test_user):
        record = await _insert(
            db_session, _make_logistics(test_user["id"], name="Mine")
        )
        result = await get_logistics_by_id(
            db_session, record.id, test_user["id"] + 99999
        )
        assert result is None

    async def test_correct_user_id_and_logistics_id(self, db_session, test_user):
        record = await _insert(
            db_session,
            _make_logistics(test_user["id"], name="Precise", type="sea"),
        )
        result = await get_logistics_by_id(db_session, record.id, test_user["id"])
        assert result["name"] == "Precise"
        assert result["type"] == "sea"


class TestCreateLogistics:
    async def test_returns_integer_id(self, db_session, test_user):
        new_id = await create_logistics(db_session, test_user["id"], {})
        assert isinstance(new_id, int)
        assert new_id > 0

    async def test_record_persisted_in_session(self, db_session, test_user):
        new_id = await create_logistics(
            db_session, test_user["id"], {"name": "Created"}
        )
        result = await get_logistics_by_id(db_session, new_id, test_user["id"])
        assert result is not None
        assert result["id"] == new_id

    async def test_fields_saved_correctly(self, db_session, test_user):
        data = {
            "name": "Express",
            "type": "air",
            "min_days": 1,
            "max_days": 3,
            "price_limit_cny": Decimal("88.8"),
            "price_min_cny": Decimal("12.3"),
        }
        new_id = await create_logistics(db_session, test_user["id"], data)
        result = await get_logistics_by_id(db_session, new_id, test_user["id"])
        assert result["name"] == "Express"
        assert result["type"] == "air"
        assert result["min_days"] == 1
        assert result["max_days"] == 3
        assert result["price_limit_cny"] == Decimal("88.8")
        assert result["price_min_cny"] == Decimal("12.3")

    async def test_user_id_set_correctly(self, db_session, test_user):
        new_id = await create_logistics(db_session, test_user["id"], {})
        result = await get_logistics_by_id(db_session, new_id, test_user["id"])
        assert result["user_id"] == test_user["id"]

    async def test_multiple_creates_unique_ids(self, db_session, test_user):
        id1 = await create_logistics(db_session, test_user["id"], {"name": "A"})
        id2 = await create_logistics(db_session, test_user["id"], {"name": "B"})
        assert id1 != id2


class TestUpdateLogistics:
    async def test_found_returns_true(self, db_session, test_user):
        record = await _insert(
            db_session, _make_logistics(test_user["id"], name="Before")
        )
        result = await update_logistics(
            db_session, record.id, test_user["id"], {"name": "After"}
        )
        assert result is True

    async def test_not_found_returns_false(self, db_session, test_user):
        result = await update_logistics(
            db_session, 999999999, test_user["id"], {"name": "X"}
        )
        assert result is False

    async def test_wrong_user_id_returns_false(self, db_session, test_user):
        record = await _insert(
            db_session, _make_logistics(test_user["id"], name="Mine")
        )
        result = await update_logistics(
            db_session, record.id, test_user["id"] + 99999, {"name": "Hacked"}
        )
        assert result is False

    async def test_valid_key_field_updated(self, db_session, test_user):
        record = await _insert(db_session, _make_logistics(test_user["id"], name="Old"))
        await update_logistics(db_session, record.id, test_user["id"], {"name": "New"})
        result = await get_logistics_by_id(db_session, record.id, test_user["id"])
        assert result["name"] == "New"

    async def test_invalid_key_ignored_hasattr_false(self, db_session, test_user):
        record = await _insert(
            db_session, _make_logistics(test_user["id"], name="Stable")
        )
        returned = await update_logistics(
            db_session,
            record.id,
            test_user["id"],
            {"nonexistent_column": "value"},
        )
        assert returned is True
        result = await get_logistics_by_id(db_session, record.id, test_user["id"])
        assert result["name"] == "Stable"

    async def test_mixed_valid_and_invalid_keys(self, db_session, test_user):
        record = await _insert(db_session, _make_logistics(test_user["id"], name="Mix"))
        await update_logistics(
            db_session,
            record.id,
            test_user["id"],
            {"name": "Updated", "bogus_field": "ignored"},
        )
        result = await get_logistics_by_id(db_session, record.id, test_user["id"])
        assert result["name"] == "Updated"

    async def test_empty_fields_dict_returns_true(self, db_session, test_user):
        record = await _insert(
            db_session, _make_logistics(test_user["id"], name="NoChange")
        )
        result = await update_logistics(db_session, record.id, test_user["id"], {})
        assert result is True

    async def test_multiple_valid_fields_updated(self, db_session, test_user):
        record = await _insert(
            db_session,
            _make_logistics(test_user["id"], name="Multi", type="sea", min_days=5),
        )
        await update_logistics(
            db_session,
            record.id,
            test_user["id"],
            {"name": "MultiNew", "type": "air", "min_days": 2},
        )
        result = await get_logistics_by_id(db_session, record.id, test_user["id"])
        assert result["name"] == "MultiNew"
        assert result["type"] == "air"
        assert result["min_days"] == 2

    async def test_old_price_limit_fields_are_ignored(self, db_session, test_user):
        new_id = await create_logistics(
            db_session,
            test_user["id"],
            {
                "name": "CNY only",
                "price_limit": Decimal("999.0"),
                "price_limit_rub": Decimal("888.0"),
                "price_min": Decimal("777.0"),
                "price_min_rub": Decimal("666.0"),
                "price_limit_currency": "USD",
                "price_min_currency": "RUB",
                "price_limit_cny": Decimal("123.0"),
                "price_min_cny": Decimal("45.0"),
            },
        )

        result = await get_logistics_by_id(db_session, new_id, test_user["id"])

        assert result["price_limit_cny"] == Decimal("123.0")
        assert result["price_min_cny"] == Decimal("45.0")
        assert result["price_limit"] is None
        assert result["price_limit_rub"] is None
        assert result["price_min"] == Decimal("0.0")
        assert result["price_min_rub"] == Decimal("0.0")
        assert result["price_limit_currency"] == "RUB"
        assert result["price_min_currency"] == "RUB"


class TestDeleteLogistics:
    async def test_found_returns_true(self, db_session, test_user):
        record = await _insert(
            db_session, _make_logistics(test_user["id"], name="ToDelete")
        )
        result = await delete_logistics(db_session, record.id, test_user["id"])
        assert result is True

    async def test_record_removed_after_delete(self, db_session, test_user):
        record = await _insert(
            db_session, _make_logistics(test_user["id"], name="Gone")
        )
        await delete_logistics(db_session, record.id, test_user["id"])
        result = await get_logistics_by_id(db_session, record.id, test_user["id"])
        assert result is None

    async def test_not_found_returns_false(self, db_session, test_user):
        result = await delete_logistics(db_session, 999999999, test_user["id"])
        assert result is False

    async def test_wrong_user_id_returns_false(self, db_session, test_user):
        record = await _insert(
            db_session, _make_logistics(test_user["id"], name="Protected")
        )
        result = await delete_logistics(db_session, record.id, test_user["id"] + 99999)
        assert result is False

    async def test_wrong_user_id_does_not_remove_record(self, db_session, test_user):
        record = await _insert(
            db_session, _make_logistics(test_user["id"], name="Safe")
        )
        await delete_logistics(db_session, record.id, test_user["id"] + 99999)
        still_there = await get_logistics_by_id(db_session, record.id, test_user["id"])
        assert still_there is not None


class TestBatchDeleteLogistics:
    async def test_success_returns_count(self, db_session, test_user):
        r1 = await _insert(db_session, _make_logistics(test_user["id"], name="B1"))
        r2 = await _insert(db_session, _make_logistics(test_user["id"], name="B2"))
        count = await batch_delete_logistics(
            db_session, [r1.id, r2.id], test_user["id"]
        )
        assert count == 2

    async def test_records_removed_after_batch_delete(self, db_session, test_user):
        r1 = await _insert(db_session, _make_logistics(test_user["id"], name="Del1"))
        r2 = await _insert(db_session, _make_logistics(test_user["id"], name="Del2"))
        await batch_delete_logistics(db_session, [r1.id, r2.id], test_user["id"])
        assert await get_logistics_by_id(db_session, r1.id, test_user["id"]) is None
        assert await get_logistics_by_id(db_session, r2.id, test_user["id"]) is None

    async def test_no_match_returns_zero(self, db_session, test_user):
        count = await batch_delete_logistics(
            db_session, [999999991, 999999992], test_user["id"]
        )
        assert count == 0

    async def test_empty_list_returns_zero(self, db_session, test_user):
        count = await batch_delete_logistics(db_session, [], test_user["id"])
        assert count == 0

    async def test_partial_match_returns_partial_count(
        self, db_session, test_user, test_admin
    ):
        r1 = await _insert(db_session, _make_logistics(test_user["id"], name="Mine"))
        r2 = await _insert(db_session, _make_logistics(test_admin["id"], name="Others"))
        count = await batch_delete_logistics(
            db_session, [r1.id, r2.id], test_user["id"]
        )
        assert count == 1

    async def test_partial_leaves_other_user_record_intact(
        self, db_session, test_user, test_admin
    ):
        r_mine = await _insert(
            db_session, _make_logistics(test_user["id"], name="Mine")
        )
        r_other = await _insert(
            db_session, _make_logistics(test_admin["id"], name="NotMine")
        )
        await batch_delete_logistics(
            db_session, [r_mine.id, r_other.id], test_user["id"]
        )
        from sqlalchemy import select as sa_select

        stmt = sa_select(Logistics).where(Logistics.id == r_other.id)
        result = await db_session.execute(stmt)
        row = result.scalar_one_or_none()
        assert row is not None

    async def test_single_id_delete(self, db_session, test_user):
        record = await _insert(
            db_session, _make_logistics(test_user["id"], name="Single")
        )
        count = await batch_delete_logistics(db_session, [record.id], test_user["id"])
        assert count == 1


class TestGetLogisticsByFilters:
    async def test_filter_by_type_land(self, db_session, test_user):
        await _insert(
            db_session, _make_logistics(test_user["id"], name="Land1", type="land")
        )
        await _insert(
            db_session, _make_logistics(test_user["id"], name="Air1", type="air")
        )
        items, total = await get_logistics_by_filters(
            db_session, test_user["id"], type="land"
        )
        assert total == 1
        assert all(i["type"] == "land" for i in items)

    async def test_filter_by_type_air(self, db_session, test_user):
        await _insert(
            db_session, _make_logistics(test_user["id"], name="Land1", type="land")
        )
        await _insert(
            db_session, _make_logistics(test_user["id"], name="Air1", type="air")
        )
        await _insert(
            db_session, _make_logistics(test_user["id"], name="Air2", type="air")
        )
        items, total = await get_logistics_by_filters(
            db_session, test_user["id"], type="air"
        )
        assert total == 2
        assert all(i["type"] == "air" for i in items)

    async def test_no_type_filter_returns_all(self, db_session, test_user):
        await _insert(
            db_session, _make_logistics(test_user["id"], name="L", type="land")
        )
        await _insert(
            db_session, _make_logistics(test_user["id"], name="A", type="air")
        )
        items, total = await get_logistics_by_filters(db_session, test_user["id"])
        assert total == 2
        assert len(items) == 2

    async def test_type_combined_with_fulfillment(self, db_session, test_user):
        await _insert(
            db_session,
            _make_logistics(
                test_user["id"], name="FBA-L", type="land", fulfillment_type="FBA"
            ),
        )
        await _insert(
            db_session,
            _make_logistics(
                test_user["id"], name="FBM-L", type="land", fulfillment_type="FBM"
            ),
        )
        await _insert(
            db_session,
            _make_logistics(
                test_user["id"], name="FBA-A", type="air", fulfillment_type="FBA"
            ),
        )
        items, total = await get_logistics_by_filters(
            db_session, test_user["id"], type="land", fulfillment_type="FBA"
        )
        assert total == 1
        assert items[0]["name"] == "FBA-L"

    async def test_type_filter_with_pagination(self, db_session, test_user):
        for i in range(5):
            await _insert(
                db_session,
                _make_logistics(test_user["id"], name=f"Land{i}", type="land"),
            )
        items, total = await get_logistics_by_filters(
            db_session, test_user["id"], type="land", limit=2, offset=0
        )
        assert total == 5
        assert len(items) == 2
