from unittest.mock import AsyncMock, MagicMock

import pytest

from db.products import (
    _assign_priority_group,
    _calculate_group_averages,
    add_product,
    batch_delete_products,
    batch_update_pricing_params,
    calculate_and_update_priority_groups,
    cleanup_test_products,
    delete_product,
    get_all_products_for_user,
    get_product_by_id,
    update_product,
)
from models.logistics import Logistics
from models.product import Product


async def _add(session, user_id, **kwargs):
    data = {"name": "Test Product", **kwargs}
    pid = await add_product(session, user_id, data)
    assert pid is not None
    return pid


async def test_add_product_minimal(db_session, test_user):
    pid = await _add(db_session, test_user["id"])
    assert isinstance(pid, int)
    assert pid > 0


async def test_add_product_bool_true_stored_as_1(db_session, test_user):
    pid = await _add(db_session, test_user["id"], name="CylTrue", is_cylinder=True)
    row = await get_product_by_id(db_session, pid, test_user["id"])
    assert row is not None
    assert row["is_cylinder"] == 1


async def test_add_product_bool_false_stored_as_0(db_session, test_user):
    pid = await _add(db_session, test_user["id"], name="BatFalse", has_battery=False)
    row = await get_product_by_id(db_session, pid, test_user["id"])
    assert row is not None
    assert row["has_battery"] == 0


async def test_add_product_all_bool_fields(db_session, test_user):
    pid = await _add(
        db_session,
        test_user["id"],
        name="AllBools",
        is_cylinder=True,
        has_battery=True,
        has_msds=False,
        has_liquid=False,
    )
    row = await get_product_by_id(db_session, pid, test_user["id"])
    assert row is not None
    assert row["is_cylinder"] == 1
    assert row["has_battery"] == 1
    assert row["has_msds"] == 0
    assert row["has_liquid"] == 0


async def test_add_product_full_data(db_session, test_user):
    pid = await _add(
        db_session,
        test_user["id"],
        name="Full Product",
        russian_name="Полный продукт",
        category="electronics",
        model="X100",
        unit_price=29.99,
        weight_g=500,
        length_cm=20,
        width_cm=10,
        height_cm=5,
    )
    row = await get_product_by_id(db_session, pid, test_user["id"])
    assert row is not None
    assert row["name"] == "Full Product"
    assert row["russian_name"] == "Полный продукт"
    assert row["unit_price"] == pytest.approx(29.99)
    assert row["weight_g"] == 500


async def test_add_product_disallowed_fields_filtered(db_session, test_user):
    pid = await _add(
        db_session,
        test_user["id"],
        name="FilterTest",
        nonexistent_field="should_be_ignored",
    )
    row = await get_product_by_id(db_session, pid, test_user["id"])
    assert row is not None
    assert row["user_id"] == test_user["id"]


async def test_get_all_products_empty(db_session, test_user):
    result = await get_all_products_for_user(db_session, test_user["id"])
    assert result == []


async def test_get_all_products_returns_list(db_session, test_user):
    await _add(db_session, test_user["id"], name="P1")
    await _add(db_session, test_user["id"], name="P2")
    result = await get_all_products_for_user(db_session, test_user["id"])
    assert len(result) >= 2
    names = [r["name"] for r in result]
    assert "P1" in names
    assert "P2" in names


async def test_get_product_by_id_found(db_session, test_user):
    pid = await _add(db_session, test_user["id"])
    row = await get_product_by_id(db_session, pid, test_user["id"])
    assert row is not None
    assert row["id"] == pid
    assert row["user_id"] == test_user["id"]


async def test_get_product_by_id_not_found(db_session, test_user):
    row = await get_product_by_id(db_session, 999999999, test_user["id"])
    assert row is None


async def test_get_product_by_id_none_user_id_raises(db_session):
    with pytest.raises(ValueError):
        await get_product_by_id(db_session, 1, None)  # type: ignore[arg-type]


async def test_get_product_by_id_wrong_user(db_session, test_user):
    pid = await _add(db_session, test_user["id"])
    row = await get_product_by_id(db_session, pid, test_user["id"] + 99999)
    assert row is None


async def test_delete_product_found(db_session, test_user):
    pid = await _add(db_session, test_user["id"])
    result = await delete_product(db_session, pid, test_user["id"])
    assert result is True
    row = await get_product_by_id(db_session, pid, test_user["id"])
    assert row is None


async def test_delete_product_not_found(db_session, test_user):
    result = await delete_product(db_session, 999999999, test_user["id"])
    assert result is False


async def test_batch_delete_empty_ids(db_session, test_user):
    result = await batch_delete_products(db_session, [], test_user["id"])
    assert result == 0


async def test_batch_delete_valid_ids(db_session, test_user):
    p1 = await _add(db_session, test_user["id"])
    p2 = await _add(db_session, test_user["id"])
    result = await batch_delete_products(db_session, [p1, p2], test_user["id"])
    assert result == 2


async def test_batch_delete_partial_ids(db_session, test_user):
    p1 = await _add(db_session, test_user["id"])
    result = await batch_delete_products(db_session, [p1, 999999998], test_user["id"])
    assert result == 1


async def test_update_product_empty_data_returns_false(db_session, test_user):
    pid = await _add(db_session, test_user["id"])
    result = await update_product(db_session, pid, test_user["id"], {})
    assert result is False


async def test_update_product_not_found_returns_false(db_session, test_user):
    result = await update_product(db_session, 999999999, test_user["id"], {"name": "x"})
    assert result is False


async def test_update_product_success(db_session, test_user):
    pid = await _add(db_session, test_user["id"])
    result = await update_product(
        db_session,
        pid,
        test_user["id"],
        {"name": "Updated Name", "unit_price": 99.0},
    )
    assert result is True
    row = await get_product_by_id(db_session, pid, test_user["id"])
    assert row is not None
    assert row["name"] == "Updated Name"
    assert row["unit_price"] == pytest.approx(99.0)


async def test_update_product_disallowed_field_ignored(db_session, test_user):
    pid = await _add(db_session, test_user["id"])
    result = await update_product(
        db_session,
        pid,
        test_user["id"],
        {"nonexistent_xyz": "value", "name": "KeepGoing"},
    )
    assert result is True
    row = await get_product_by_id(db_session, pid, test_user["id"])
    assert row is not None
    assert row["name"] == "KeepGoing"


async def test_batch_update_pricing_params_empty_returns_0(db_session, test_user):
    result = await batch_update_pricing_params(db_session, test_user["id"], {})
    assert result == 0


async def test_batch_update_pricing_params_only_invalid_fields_returns_0(
    db_session, test_user
):
    result = await batch_update_pricing_params(
        db_session, test_user["id"], {"totally_invalid": 1.0}
    )
    assert result == 0


async def test_batch_update_pricing_params_updates_all_products(db_session, test_user):
    p1 = await _add(db_session, test_user["id"])
    p2 = await _add(db_session, test_user["id"])
    result = await batch_update_pricing_params(
        db_session,
        test_user["id"],
        {"commission_rate": 0.20, "vat_rate": 0.10},
    )
    assert result >= 2
    row1 = await get_product_by_id(db_session, p1, test_user["id"])
    row2 = await get_product_by_id(db_session, p2, test_user["id"])
    assert row1 is not None
    assert row2 is not None
    assert row1["commission_rate"] == pytest.approx(0.20)
    assert row2["vat_rate"] == pytest.approx(0.10)


async def test_cleanup_test_products_with_user_id(db_session, test_user):
    await add_product(
        db_session,
        test_user["id"],
        {"name": "TempTestProduct", "is_test_data": 1},
    )
    result = await cleanup_test_products(db_session, user_id=test_user["id"])
    assert isinstance(result, int)
    assert result >= 1


async def test_cleanup_test_products_without_user_id(db_session, test_user):
    await add_product(
        db_session,
        test_user["id"],
        {"name": "GlobalTest", "is_test_data": 1},
    )
    result = await cleanup_test_products(db_session, user_id=None)
    assert isinstance(result, int)
    assert result >= 1


async def test_cleanup_test_products_exception_returns_0():
    mock_session = MagicMock()
    mock_session.execute = AsyncMock(side_effect=Exception("DB error"))
    result = await cleanup_test_products(mock_session, user_id=1)
    assert result == 0


def test_calculate_group_averages_empty_list():
    assert _calculate_group_averages([]) == (0, 0, 0)


def test_calculate_group_averages_all_zero_days():
    data = [
        {"min_days": 0, "max_days": 0},
        {"min_days": 0, "max_days": 5},
        {"min_days": 3, "max_days": 0},
    ]
    assert _calculate_group_averages(data) == (0, 0, 0)


def test_calculate_group_averages_valid_data():
    data = [
        {"min_days": 2, "max_days": 4},
        {"min_days": 4, "max_days": 8},
    ]
    avg_fastest, avg_slowest, avg_overall = _calculate_group_averages(data)
    assert avg_fastest == pytest.approx(3.0)
    assert avg_slowest == pytest.approx(6.0)
    assert avg_overall == pytest.approx(4.5)


def test_calculate_group_averages_mixed_valid_invalid():
    data = [
        {"min_days": 0, "max_days": 4},
        {"min_days": 2, "max_days": 4},
        {"min_days": 4, "max_days": 8},
    ]
    avg_fastest, avg_slowest, avg_overall = _calculate_group_averages(data)
    assert avg_fastest == pytest.approx(3.0)
    assert avg_slowest == pytest.approx(6.0)
    assert avg_overall == pytest.approx(4.5)


def test_assign_priority_group_E_both_zero():
    log = {"min_days": 0, "max_days": 0}
    assert _assign_priority_group(log, 3.0, 6.0, 4.5) == "E"


def test_assign_priority_group_A_all_three_below():
    log = {"min_days": 1, "max_days": 3}
    assert _assign_priority_group(log, 3.0, 6.0, 4.5) == "A"


def test_assign_priority_group_B_two_below():
    log = {"min_days": 1, "max_days": 7}
    assert _assign_priority_group(log, 3.0, 6.0, 4.5) == "B"


def test_assign_priority_group_C_one_below():
    log = {"min_days": 2, "max_days": 7}
    assert _assign_priority_group(log, 3.0, 6.0, 4.5) == "C"


def test_assign_priority_group_D_none_below():
    log = {"min_days": 5, "max_days": 8}
    assert _assign_priority_group(log, 3.0, 6.0, 4.5) == "D"


def test_assign_priority_group_D_equal_averages():
    log = {"min_days": 3, "max_days": 6}
    assert _assign_priority_group(log, 3.0, 6.0, 4.5) == "D"


async def test_calculate_and_update_priority_groups_with_logistics(
    db_session, test_user
):
    from sqlalchemy import select

    uid = test_user["id"]

    land1 = Logistics(
        user_id=uid, name="Land Fast", type="land", min_days=2, max_days=4
    )
    land2 = Logistics(
        user_id=uid, name="Land Slow", type="land", min_days=6, max_days=10
    )
    air1 = Logistics(user_id=uid, name="Air Fast", type="air", min_days=1, max_days=2)
    air2 = Logistics(user_id=uid, name="Air Slow", type="air", min_days=5, max_days=9)

    db_session.add_all([land1, land2, air1, air2])
    await db_session.flush()

    await calculate_and_update_priority_groups(db_session, uid)
    await db_session.flush()

    stmt = select(Logistics).where(Logistics.user_id == uid)
    result = await db_session.execute(stmt)
    rows = result.scalars().all()
    groups = {r.name: r.priority_group for r in rows}

    valid_groups = {"A", "B", "C", "D", "E"}
    for name, grp in groups.items():
        assert grp in valid_groups, f"{name} has invalid group {grp!r}"


async def test_calculate_and_update_priority_groups_empty_logistics(
    db_session, test_user
):
    await calculate_and_update_priority_groups(db_session, test_user["id"])


async def test_product_to_dict_has_all_columns(db_session, test_user):
    pid = await add_product(
        db_session,
        test_user["id"],
        {
            "name": "DictTest",
            "unit_price": 10.0,
            "weight_g": 200,
            "is_cylinder": False,
            "has_battery": True,
            "has_msds": False,
            "has_liquid": True,
        },
    )
    assert pid is not None
    row = await get_product_by_id(db_session, pid, test_user["id"])
    assert row is not None

    expected_keys = {c.name for c in Product.__table__.columns}
    assert expected_keys == set(row.keys())


async def test_add_product_with_commission_category_id(db_session, test_user):
    pid = await _add(
        db_session,
        test_user["id"],
        name="CommissionCategoryProduct",
        commission_category_id=42,
    )
    row = await get_product_by_id(db_session, pid, test_user["id"])
    assert row is not None
    assert row["commission_category_id"] == 42


async def test_update_product_commission_category_id(db_session, test_user):
    pid = await _add(db_session, test_user["id"], name="CommissionUpdate")
    result = await update_product(
        db_session,
        pid,
        test_user["id"],
        {"commission_category_id": 99},
    )
    assert result is True
    row = await get_product_by_id(db_session, pid, test_user["id"])
    assert row is not None
    assert row["commission_category_id"] == 99


async def test_add_product_commission_category_id_defaults_none(db_session, test_user):
    pid = await _add(db_session, test_user["id"], name="CommissionDefault")
    row = await get_product_by_id(db_session, pid, test_user["id"])
    assert row is not None
    assert row["commission_category_id"] is None
