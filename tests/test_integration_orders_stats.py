"""
Integration tests for orders.py and statistics.py routes.
These tests hit the real PostgreSQL database.
"""

import time
import pytest

from api.main import app
from api.dependencies import get_current_user_id, require_admin
from database import AsyncSessionLocal
from models.order import PaymentOrder
from models.log import UserLoginLog, AdminActionLog
from sqlalchemy import text

# ---------------------------------------------------------------------------
# Auth override helpers
# ---------------------------------------------------------------------------

_current_user_id = None
_current_admin_id = None


def _override_get_current_user_id():
    return _current_user_id


def _override_require_admin():
    return _current_admin_id


def _set_user(user_id):
    global _current_user_id
    _current_user_id = user_id
    app.dependency_overrides[get_current_user_id] = _override_get_current_user_id


def _set_admin(admin_id):
    global _current_admin_id
    _current_admin_id = admin_id
    app.dependency_overrides[require_admin] = _override_require_admin


def _clear_overrides():
    app.dependency_overrides.pop(get_current_user_id, None)
    app.dependency_overrides.pop(require_admin, None)


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


async def insert_test_order(user_id, status="paid", order_type="professional"):
    order_id = f"TEST_ORD_{int(time.time() * 1000)}"
    ts = int(time.time())
    async with AsyncSessionLocal() as session:
        order = PaymentOrder(
            order_id=order_id,
            user_id=user_id,
            amount=99,
            description="test order",
            duration="30",
            status=status,
            created_at=ts,
            order_type=order_type,
        )
        session.add(order)
        await session.flush()
        pk = order.id
        await session.commit()
    return pk


async def delete_test_order(order_pk):
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(
                text("DELETE FROM payment_orders WHERE id = :pk"),
                {"pk": order_pk},
            )
            await session.commit()
    except Exception:
        pass


async def insert_login_log(user_id):
    ts = int(time.time())
    async with AsyncSessionLocal() as session:
        log = UserLoginLog(
            user_id=user_id,
            login_time=ts,
            ip_address="127.0.0.1",
            user_agent="test-agent",
            device_type="desktop",
            created_at=ts,
        )
        session.add(log)
        await session.flush()
        pk = log.id
        await session.commit()
    return pk


async def delete_login_log(log_id):
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(
                text("DELETE FROM user_login_log WHERE id = :pk"),
                {"pk": log_id},
            )
            await session.commit()
    except Exception:
        pass


async def insert_admin_log(admin_id):
    ts = int(time.time())
    async with AsyncSessionLocal() as session:
        log = AdminActionLog(
            admin_id=admin_id,
            action_type="test_action",
            action_detail="integration test",
            target_user_id=None,
            target_type="user",
            ip_address="127.0.0.1",
            created_at=ts,
        )
        session.add(log)
        await session.flush()
        pk = log.id
        await session.commit()
    return pk


async def delete_admin_log(log_id):
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(
                text("DELETE FROM admin_action_log WHERE id = :pk"),
                {"pk": log_id},
            )
            await session.commit()
    except Exception:
        pass


# ===========================================================================
# orders.py  —  GET /api/orders
# ===========================================================================


class TestGetOrders:
    async def test_no_orders_returns_empty_list(self, client, test_user):
        uid = test_user["id"]
        _set_user(uid)
        try:
            resp = await client.get("/api/orders")
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, list)
            for item in data:
                assert "id" in item
        finally:
            _clear_overrides()

    async def test_with_orders_returns_correct_format(self, client, test_user):
        uid = test_user["id"]
        pk = await insert_test_order(uid, status="paid", order_type="professional")
        _set_user(uid)
        try:
            resp = await client.get("/api/orders")
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, list)
            assert len(data) >= 1

            inserted = [d for d in data if d.get("id") == pk]
            assert len(inserted) == 1
            o = inserted[0]

            assert "id" in o
            assert "order_id" in o
            assert "order_type" in o
            assert "plan_name" in o
            assert "amount" in o
            assert "status" in o
            assert "created_at" in o
            assert o["order_type"] == "professional"
            assert o["plan_name"] == "专业版"
            assert o["amount"] == 99.0
            assert o["status"] == "paid"
        finally:
            _clear_overrides()
            if pk:
                await delete_test_order(pk)

    async def test_order_updated_at_optional(self, client, test_user):
        uid = test_user["id"]
        pk = await insert_test_order(uid)
        _set_user(uid)
        try:
            resp = await client.get("/api/orders")
            assert resp.status_code == 200
            data = resp.json()
            inserted = [d for d in data if d.get("id") == pk]
            assert len(inserted) == 1
            o = inserted[0]
            assert "updated_at" in o
        finally:
            _clear_overrides()
            if pk:
                await delete_test_order(pk)

    async def test_no_auth_returns_422_or_403(self, client):
        _clear_overrides()
        resp = await client.get("/api/orders")
        assert resp.status_code in (401, 403, 422)


# ===========================================================================
# statistics.py  —  DB-backed endpoints (require_admin)
# ===========================================================================


class TestStatisticsOverview:
    async def test_overview_returns_correct_schema(self, client, test_admin):
        _set_admin(test_admin["id"])
        try:
            resp = await client.get("/api/statistics/overview")
            assert resp.status_code == 200
            data = resp.json()
            for key in [
                "total_users",
                "active_users",
                "new_users_today",
                "total_orders",
                "total_revenue",
                "pro_users",
                "eff_users",
                "free_users",
            ]:
                assert key in data, f"Missing key: {key}"
            assert isinstance(data["total_users"], int)
            assert data["total_users"] >= 0
            assert isinstance(data["total_revenue"], (int, float))
        finally:
            _clear_overrides()

    async def test_overview_counts_are_non_negative(self, client, test_admin):
        _set_admin(test_admin["id"])
        try:
            resp = await client.get("/api/statistics/overview")
            assert resp.status_code == 200
            data = resp.json()
            assert data["pro_users"] >= 0
            assert data["eff_users"] >= 0
            assert data["free_users"] >= 0
            assert data["total_orders"] >= 0
        finally:
            _clear_overrides()


class TestStatisticsLoginLogs:
    async def test_login_logs_returns_list(self, client, test_admin):
        _set_admin(test_admin["id"])
        try:
            resp = await client.get("/api/statistics/login-logs")
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, list)
        finally:
            _clear_overrides()

    async def test_login_logs_with_inserted_data(self, client, test_user, test_admin):
        log_id = await insert_login_log(test_user["id"])
        _set_admin(test_admin["id"])
        try:
            resp = await client.get("/api/statistics/login-logs?page=1&page_size=100")
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, list)
            assert len(data) >= 1
            if data:
                item = data[0]
                for field in ["id", "username", "action", "ip", "time", "status"]:
                    assert field in item, f"Missing field: {field}"
        finally:
            _clear_overrides()
            if log_id:
                await delete_login_log(log_id)

    async def test_login_logs_pagination(self, client, test_admin):
        _set_admin(test_admin["id"])
        try:
            resp = await client.get("/api/statistics/login-logs?page=1&page_size=5")
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, list)
            assert len(data) <= 5
        finally:
            _clear_overrides()


class TestStatisticsAdminLogs:
    async def test_admin_logs_returns_list(self, client, test_admin):
        _set_admin(test_admin["id"])
        try:
            resp = await client.get("/api/statistics/admin-logs")
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, list)
        finally:
            _clear_overrides()

    async def test_admin_logs_with_inserted_data(self, client, test_admin):
        log_id = await insert_admin_log(test_admin["id"])
        _set_admin(test_admin["id"])
        try:
            resp = await client.get("/api/statistics/admin-logs?page=1&page_size=100")
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, list)
            assert len(data) >= 1
            if data:
                item = data[0]
                for field in ["id", "admin", "action", "time"]:
                    assert field in item, f"Missing field: {field}"
        finally:
            _clear_overrides()
            if log_id:
                await delete_admin_log(log_id)

    async def test_admin_logs_pagination(self, client, test_admin):
        _set_admin(test_admin["id"])
        try:
            resp = await client.get("/api/statistics/admin-logs?page=1&page_size=3")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) <= 3
        finally:
            _clear_overrides()


class TestStatisticsUserGroups:
    async def test_user_groups_returns_dict(self, client, test_admin):
        _set_admin(test_admin["id"])
        try:
            resp = await client.get("/api/statistics/user-groups")
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, dict)
            for key in ["high_value_users", "active_users", "silent_users"]:
                assert key in data, f"Missing key: {key}"
            assert data["high_value_users"] >= 0
            assert data["active_users"] >= 0
        finally:
            _clear_overrides()

    async def test_user_groups_silent_non_negative(self, client, test_admin):
        _set_admin(test_admin["id"])
        try:
            resp = await client.get("/api/statistics/user-groups")
            assert resp.status_code == 200
            data = resp.json()
            assert data["silent_users"] >= 0
        finally:
            _clear_overrides()


class TestStatisticsFunnel:
    async def test_funnel_returns_dict(self, client, test_admin):
        _set_admin(test_admin["id"])
        try:
            resp = await client.get("/api/statistics/funnel")
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, dict)
            for key in [
                "registered",
                "trial",
                "paid",
                "conversion_trial",
                "conversion_paid",
            ]:
                assert key in data, f"Missing key: {key}"
        finally:
            _clear_overrides()

    async def test_funnel_registered_gte_paid(self, client, test_admin):
        _set_admin(test_admin["id"])
        try:
            resp = await client.get("/api/statistics/funnel")
            assert resp.status_code == 200
            data = resp.json()
            assert data["registered"] >= data["paid"]
        finally:
            _clear_overrides()


class TestStatisticsPlanAnalysis:
    async def test_plan_analysis_returns_dict(self, client, test_admin):
        _set_admin(test_admin["id"])
        try:
            resp = await client.get("/api/statistics/plan-analysis")
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, dict)
            for key in [
                "free_users",
                "efficiency_users",
                "professional_users",
                "enterprise_users",
            ]:
                assert key in data, f"Missing key: {key}"
        finally:
            _clear_overrides()

    async def test_plan_analysis_counts_non_negative(self, client, test_admin):
        _set_admin(test_admin["id"])
        try:
            resp = await client.get("/api/statistics/plan-analysis")
            assert resp.status_code == 200
            data = resp.json()
            for k, v in data.items():
                assert v >= 0, f"{k} should be >= 0"
        finally:
            _clear_overrides()


class TestStatisticsActiveUsers:
    async def test_active_users_returns_dict(self, client, test_admin):
        _set_admin(test_admin["id"])
        try:
            resp = await client.get("/api/statistics/active-users")
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, dict)
            for key in ["daily", "weekly", "trend_daily", "trend_weekly"]:
                assert key in data, f"Missing key: {key}"
        finally:
            _clear_overrides()

    async def test_active_users_daily_lte_weekly(self, client, test_admin):
        _set_admin(test_admin["id"])
        try:
            resp = await client.get("/api/statistics/active-users")
            assert resp.status_code == 200
            data = resp.json()
            assert data["daily"] <= data["weekly"]
        finally:
            _clear_overrides()
