# -*- coding: utf-8 -*-
"""
Tests for db/plans.py - comprehensive coverage of all 9 functions.
"""

import time

import pytest

from db.plans import (
    create_plan,
    delete_plan,
    get_plan_by_code,
    get_plan_by_id,
    get_plan_price,
    get_plans,
    toggle_plan_active,
    update_plan,
)
from models.user import Plan


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _unique_code(suffix: str) -> str:
    """Return a plan_code that is unique across tests."""
    ts = int(time.time() * 1000)
    return f"tp_{suffix}_{ts}"


def _make_plan_data(code: str, *, sort_order: int = 99) -> dict:
    """Minimal valid data to create a Plan row."""
    return {
        "plan_code": code,
        "plan_name": f"Test Plan {code}",
        "display_price_month": 9.99,
        "display_price_year": 99.99,
        "actual_price_month": 8.99,
        "actual_price_year": 89.99,
        "test_price_month": 0.01,
        "test_price_year": 0.10,
        "calc_limit": 100,
        "logistics_limit": 10,
        "description": "A test plan",
        "features": "feature1,feature2",
        "is_active": 1,
        "sort_order": sort_order,
    }


async def _create_plan_row(db_session, code: str, **overrides) -> Plan:
    """Create and flush a Plan row, returning the ORM object."""
    data = _make_plan_data(code)
    data.update(overrides)
    plan = Plan(**data)
    db_session.add(plan)
    await db_session.flush()
    return plan


# ===========================================================================
# _plan_to_dict  (tested indirectly through get_plan_by_id / get_plan_by_code)
# ===========================================================================


class TestPlanToDict:
    async def test_all_keys_present(self, db_session):
        code = _unique_code("dict_keys")
        plan = await _create_plan_row(db_session, code)

        result = await get_plan_by_id(db_session, plan.id)

        expected_keys = {
            "id",
            "plan_code",
            "plan_name",
            "display_price_month",
            "display_price_year",
            "actual_price_month",
            "actual_price_year",
            "test_price_month",
            "test_price_year",
            "calc_limit",
            "logistics_limit",
            "description",
            "features",
            "is_active",
            "sort_order",
            "created_at",
            "updated_at",
        }
        assert expected_keys == set(result.keys())

    async def test_values_match_model(self, db_session):
        code = _unique_code("dict_vals")
        plan = await _create_plan_row(db_session, code)

        result = await get_plan_by_id(db_session, plan.id)

        assert result["plan_code"] == code
        assert result["plan_name"] == f"Test Plan {code}"
        assert result["actual_price_month"] == 8.99
        assert result["test_price_year"] == 0.10
        assert result["is_active"] == 1


# ===========================================================================
# get_plans
# ===========================================================================


class TestGetPlans:
    async def test_active_only_false_include_free_true(self, db_session):
        """Default call returns all plans including inactive and free."""
        code_active = _unique_code("gp_a")
        code_inactive = _unique_code("gp_i")
        code_free = _unique_code("free_gp")

        await _create_plan_row(db_session, code_active, is_active=1)
        await _create_plan_row(db_session, code_inactive, is_active=0)
        await _create_plan_row(db_session, code_free, plan_code=code_free)

        result = await get_plans(db_session, active_only=False, include_free=True)
        codes = {r["plan_code"] for r in result}

        assert code_active in codes
        assert code_inactive in codes
        assert code_free in codes

    async def test_active_only_true_excludes_inactive(self, db_session):
        code_active = _unique_code("gp_ao_a")
        code_inactive = _unique_code("gp_ao_i")

        await _create_plan_row(db_session, code_active, is_active=1)
        await _create_plan_row(db_session, code_inactive, is_active=0)

        result = await get_plans(db_session, active_only=True, include_free=True)
        codes = {r["plan_code"] for r in result}

        assert code_active in codes
        assert code_inactive not in codes

    async def test_include_free_false_excludes_free_code(self, db_session):
        """When include_free=False, rows with plan_code == 'free' are excluded."""
        code_paid = _unique_code("gp_nf_paid")
        # Use literal 'free' suffix so plan_code == 'free' matches the filter
        code_free_literal = "free"

        await _create_plan_row(db_session, code_paid, is_active=1)
        # Only add a 'free' row if it doesn't already exist (unique constraint).
        from sqlalchemy import select

        existing = (
            await db_session.execute(select(Plan).where(Plan.plan_code == "free"))
        ).scalar_one_or_none()
        if existing is None:
            await _create_plan_row(db_session, code_free_literal)

        result = await get_plans(db_session, active_only=False, include_free=False)
        codes = {r["plan_code"] for r in result}

        assert "free" not in codes
        assert code_paid in codes

    async def test_active_only_and_no_free(self, db_session):
        """active_only=True AND include_free=False — both filters applied."""
        code = _unique_code("gp_both")
        await _create_plan_row(db_session, code, is_active=1)

        result = await get_plans(db_session, active_only=True, include_free=False)
        codes = {r["plan_code"] for r in result}

        assert code in codes
        assert "free" not in codes

    async def test_returns_list_of_dicts(self, db_session):
        code = _unique_code("gp_list")
        await _create_plan_row(db_session, code)

        result = await get_plans(db_session)
        assert isinstance(result, list)
        assert all(isinstance(r, dict) for r in result)

    async def test_ordered_by_sort_order(self, db_session):
        code_low = _unique_code("gp_ord_low")
        code_high = _unique_code("gp_ord_high")

        await _create_plan_row(db_session, code_high, sort_order=200)
        await _create_plan_row(db_session, code_low, sort_order=1)

        result = await get_plans(db_session)
        # Within our test codes, low-sort-order item must appear before high
        our_codes = [
            r["plan_code"] for r in result if r["plan_code"] in {code_low, code_high}
        ]
        assert our_codes == [code_low, code_high]

    async def test_empty_when_all_inactive_and_active_only(self, db_session):
        code = _unique_code("gp_empty")
        await _create_plan_row(db_session, code, is_active=0)

        result = await get_plans(db_session, active_only=True)
        # Our newly created inactive plan must not appear
        codes = {r["plan_code"] for r in result}
        assert code not in codes


# ===========================================================================
# get_plan_by_code
# ===========================================================================


class TestGetPlanByCode:
    async def test_found(self, db_session):
        code = _unique_code("gpbc_found")
        plan = await _create_plan_row(db_session, code)

        result = await get_plan_by_code(db_session, code)

        assert result is not None
        assert result["id"] == plan.id
        assert result["plan_code"] == code

    async def test_not_found(self, db_session):
        result = await get_plan_by_code(db_session, "nonexistent_plan_xyz_99999")
        assert result is None

    async def test_returns_dict(self, db_session):
        code = _unique_code("gpbc_dict")
        await _create_plan_row(db_session, code)

        result = await get_plan_by_code(db_session, code)
        assert isinstance(result, dict)


# ===========================================================================
# get_plan_by_id
# ===========================================================================


class TestGetPlanById:
    async def test_found(self, db_session):
        code = _unique_code("gpbi_found")
        plan = await _create_plan_row(db_session, code)

        result = await get_plan_by_id(db_session, plan.id)

        assert result is not None
        assert result["id"] == plan.id
        assert result["plan_code"] == code

    async def test_not_found(self, db_session):
        result = await get_plan_by_id(db_session, 99999999)
        assert result is None

    async def test_returns_dict(self, db_session):
        code = _unique_code("gpbi_dict")
        plan = await _create_plan_row(db_session, code)

        result = await get_plan_by_id(db_session, plan.id)
        assert isinstance(result, dict)


# ===========================================================================
# create_plan
# ===========================================================================


class TestCreatePlan:
    async def test_returns_id(self, db_session):
        code = _unique_code("cp_ret")
        data = _make_plan_data(code)

        plan_id = await create_plan(db_session, data)

        assert isinstance(plan_id, int)
        assert plan_id > 0

    async def test_plan_persisted(self, db_session):
        code = _unique_code("cp_persist")
        data = _make_plan_data(code)

        plan_id = await create_plan(db_session, data)

        fetched = await get_plan_by_id(db_session, plan_id)
        assert fetched is not None
        assert fetched["plan_code"] == code

    async def test_all_fields_stored(self, db_session):
        code = _unique_code("cp_fields")
        data = _make_plan_data(code)

        plan_id = await create_plan(db_session, data)
        result = await get_plan_by_id(db_session, plan_id)

        assert result["plan_name"] == data["plan_name"]
        assert result["display_price_month"] == pytest.approx(
            data["display_price_month"], rel=1e-4
        )
        assert result["calc_limit"] == data["calc_limit"]
        assert result["logistics_limit"] == data["logistics_limit"]
        assert result["description"] == data["description"]
        assert result["features"] == [data["features"]]


# ===========================================================================
# update_plan
# ===========================================================================


class TestUpdatePlan:
    async def test_found_returns_true(self, db_session):
        code = _unique_code("up_true")
        plan = await _create_plan_row(db_session, code)

        result = await update_plan(db_session, plan.id, {"plan_name": "Updated Name"})
        assert result is True

    async def test_not_found_returns_false(self, db_session):
        result = await update_plan(db_session, 99999999, {"plan_name": "ghost"})
        assert result is False

    async def test_valid_key_updated(self, db_session):
        code = _unique_code("up_valid")
        plan = await _create_plan_row(db_session, code)

        await update_plan(db_session, plan.id, {"plan_name": "New Name"})

        fetched = await get_plan_by_id(db_session, plan.id)
        assert fetched["plan_name"] == "New Name"

    async def test_invalid_key_ignored(self, db_session):
        """Keys not present as model attributes must be silently skipped."""
        code = _unique_code("up_invalid_key")
        plan = await _create_plan_row(db_session, code)
        original_name = plan.plan_name

        # Pass a non-existent attribute — should not raise and should return True
        result = await update_plan(
            db_session,
            plan.id,
            {"nonexistent_field_xyz": "value", "plan_name": original_name},
        )
        assert result is True

        fetched = await get_plan_by_id(db_session, plan.id)
        assert fetched["plan_name"] == original_name

    async def test_mixed_keys_partial_update(self, db_session):
        """Valid keys updated, invalid keys silently skipped."""
        code = _unique_code("up_mixed")
        plan = await _create_plan_row(db_session, code)

        await update_plan(
            db_session,
            plan.id,
            {
                "plan_name": "Mixed Update",
                "bogus_key": "ignored",
            },
        )

        fetched = await get_plan_by_id(db_session, plan.id)
        assert fetched["plan_name"] == "Mixed Update"

    async def test_multiple_valid_fields(self, db_session):
        code = _unique_code("up_multi")
        plan = await _create_plan_row(db_session, code)

        await update_plan(
            db_session,
            plan.id,
            {
                "plan_name": "Multi Field",
                "calc_limit": 500,
                "is_active": 0,
            },
        )

        fetched = await get_plan_by_id(db_session, plan.id)
        assert fetched["plan_name"] == "Multi Field"
        assert fetched["calc_limit"] == 500
        assert fetched["is_active"] == 0


# ===========================================================================
# delete_plan
# ===========================================================================


class TestDeletePlan:
    async def test_found_returns_true(self, db_session):
        code = _unique_code("dp_true")
        plan = await _create_plan_row(db_session, code)

        result = await delete_plan(db_session, plan.id)
        assert result is True

    async def test_not_found_returns_false(self, db_session):
        result = await delete_plan(db_session, 99999999)
        assert result is False

    async def test_plan_removed_after_delete(self, db_session):
        code = _unique_code("dp_gone")
        plan = await _create_plan_row(db_session, code)
        plan_id = plan.id

        await delete_plan(db_session, plan_id)
        await db_session.flush()

        fetched = await get_plan_by_id(db_session, plan_id)
        assert fetched is None


# ===========================================================================
# toggle_plan_active
# ===========================================================================


class TestTogglePlanActive:
    async def test_active_to_inactive(self, db_session):
        code = _unique_code("tpa_1to0")
        plan = await _create_plan_row(db_session, code, is_active=1)

        new_state = await toggle_plan_active(db_session, plan.id)
        assert new_state == 0

    async def test_inactive_to_active(self, db_session):
        code = _unique_code("tpa_0to1")
        plan = await _create_plan_row(db_session, code, is_active=0)

        new_state = await toggle_plan_active(db_session, plan.id)
        assert new_state == 1

    async def test_not_found_returns_none(self, db_session):
        result = await toggle_plan_active(db_session, 99999999)
        assert result is None

    async def test_model_updated_after_toggle(self, db_session):
        code = _unique_code("tpa_persist")
        plan = await _create_plan_row(db_session, code, is_active=1)

        await toggle_plan_active(db_session, plan.id)
        await db_session.flush()

        fetched = await get_plan_by_id(db_session, plan.id)
        assert fetched["is_active"] == 0

    async def test_double_toggle_returns_original(self, db_session):
        code = _unique_code("tpa_double")
        plan = await _create_plan_row(db_session, code, is_active=1)

        await toggle_plan_active(db_session, plan.id)
        final = await toggle_plan_active(db_session, plan.id)
        assert final == 1


# ===========================================================================
# get_plan_price
# ===========================================================================


class TestGetPlanPrice:
    async def test_actual_price_month(self, db_session):
        code = _unique_code("gpp_am")
        await _create_plan_row(db_session, code)

        price = await get_plan_price(
            db_session, code, billing_cycle="month", use_test_price=False
        )
        assert price == pytest.approx(8.99, rel=1e-4)

    async def test_actual_price_year(self, db_session):
        code = _unique_code("gpp_ay")
        await _create_plan_row(db_session, code)

        price = await get_plan_price(
            db_session, code, billing_cycle="year", use_test_price=False
        )
        assert price == pytest.approx(89.99, rel=1e-4)

    async def test_test_price_month(self, db_session):
        code = _unique_code("gpp_tm")
        await _create_plan_row(db_session, code)

        price = await get_plan_price(
            db_session, code, billing_cycle="month", use_test_price=True
        )
        assert price == pytest.approx(0.01, rel=1e-3)

    async def test_test_price_year(self, db_session):
        code = _unique_code("gpp_ty")
        await _create_plan_row(db_session, code)

        price = await get_plan_price(
            db_session, code, billing_cycle="year", use_test_price=True
        )
        assert price == pytest.approx(0.10, rel=1e-4)

    async def test_not_found_returns_none(self, db_session):
        price = await get_plan_price(db_session, "nonexistent_plan_xyz_99999")
        assert price is None

    async def test_default_args_actual_month(self, db_session):
        """Default billing_cycle='month', use_test_price=False."""
        code = _unique_code("gpp_default")
        await _create_plan_row(db_session, code)

        price = await get_plan_price(db_session, code)
        assert price == pytest.approx(8.99, rel=1e-4)

    async def test_test_price_default_billing_cycle(self, db_session):
        """use_test_price=True with default billing_cycle='month'."""
        code = _unique_code("gpp_tp_default")
        await _create_plan_row(db_session, code)

        price = await get_plan_price(db_session, code, use_test_price=True)
        assert price == pytest.approx(0.01, rel=1e-3)


# ===========================================================================
# Edge / integration tests
# ===========================================================================


class TestEdgeCases:
    async def test_create_then_get_by_code(self, db_session):
        code = _unique_code("edge_create_code")
        data = _make_plan_data(code)

        plan_id = await create_plan(db_session, data)
        by_code = await get_plan_by_code(db_session, code)
        by_id = await get_plan_by_id(db_session, plan_id)

        assert by_code is not None
        assert by_id is not None
        assert by_code["id"] == by_id["id"]

    async def test_delete_then_not_findable(self, db_session):
        code = _unique_code("edge_del_notfound")
        plan = await _create_plan_row(db_session, code)
        plan_id = plan.id

        await delete_plan(db_session, plan_id)
        await db_session.flush()

        assert await get_plan_by_id(db_session, plan_id) is None
        assert await get_plan_by_code(db_session, code) is None

    async def test_update_price_then_get_price(self, db_session):
        code = _unique_code("edge_price_update")
        plan = await _create_plan_row(db_session, code)

        await update_plan(db_session, plan.id, {"actual_price_month": 19.99})

        price = await get_plan_price(db_session, code, billing_cycle="month")
        assert price == 19.99

    async def test_toggle_active_reflects_in_get_plans(self, db_session):
        code = _unique_code("edge_toggle_visible")
        plan = await _create_plan_row(db_session, code, is_active=1)

        # Initially appears in active_only results
        before = await get_plans(db_session, active_only=True)
        codes_before = {r["plan_code"] for r in before}
        assert code in codes_before

        # After toggling off, should not appear
        await toggle_plan_active(db_session, plan.id)
        after = await get_plans(db_session, active_only=True)
        codes_after = {r["plan_code"] for r in after}
        assert code not in codes_after

    async def test_get_plans_returns_zero_fields_matching_none(self, db_session):
        """Sanity: get_plans with active_only=True on all-inactive session data."""
        code = _unique_code("edge_all_inactive")
        await _create_plan_row(db_session, code, is_active=0)

        result = await get_plans(db_session, active_only=True)
        codes = {r["plan_code"] for r in result}
        assert code not in codes
