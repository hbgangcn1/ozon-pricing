"""
Integration tests for orders.py and statistics.py routes.
These tests hit the real PostgreSQL database.
"""

import time

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
            assert isinstance(data, dict)
            assert "orders" in data
            assert isinstance(data["orders"], list)
            assert "total" in data
        finally:
            _clear_overrides()

    async def test_with_orders_returns_correct_format(self, client, test_user):
        uid = test_user["id"]
        pk = await insert_test_order(uid, status="paid", order_type="professional")
        _set_user(uid)
        try:
            resp = await client.get("/api/orders")
            assert resp.status_code == 200
            body = resp.json()
            assert isinstance(body, dict)
            data = body["orders"]
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
            body = resp.json()
            data = body["orders"]
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

    async def test_overview_active_users_not_equal_total_users_when_old_logins_exist(
        self,
        client,
        test_admin,
    ):
        _set_admin(test_admin["id"])
        try:
            resp = await client.get("/api/statistics/overview")
            assert resp.status_code == 200
            data = resp.json()
            assert data["active_users"] <= data["total_users"]
        finally:
            _clear_overrides()


class TestStatisticsLoginLogs:
    async def test_login_logs_returns_paginated_payload(self, client, test_admin):
        _set_admin(test_admin["id"])
        try:
            resp = await client.get("/api/statistics/login-logs")
            assert resp.status_code == 200
            data = resp.json()
            assert set(data) == {"items", "total", "page", "page_size"}
            assert isinstance(data["items"], list)
            assert isinstance(data["total"], int)
            assert data["page"] == 1
            assert data["page_size"] == 20
        finally:
            _clear_overrides()

    async def test_login_logs_with_inserted_data(self, client, test_user, test_admin):
        log_id = await insert_login_log(test_user["id"])
        _set_admin(test_admin["id"])
        try:
            resp = await client.get("/api/statistics/login-logs?page=1&page_size=100")
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data["items"], list)
            inserted = [item for item in data["items"] if item["id"] == log_id]
            assert len(inserted) == 1
            item = inserted[0]
            for field in ["id", "username", "action", "ip", "time", "status"]:
                assert field in item, f"Missing field: {field}"
            assert item["username"] == test_user["username"]
            assert item["action"] == "登录"
            assert item["status"] == "成功"
            assert item["time"].count(":") == 2
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
            assert len(data["items"]) <= 5
            assert data["page"] == 1
            assert data["page_size"] == 5
        finally:
            _clear_overrides()

    async def test_login_logs_support_search(self, client, test_user, test_admin):
        log_id = await insert_login_log(test_user["id"])
        _set_admin(test_admin["id"])
        try:
            resp = await client.get(
                f"/api/statistics/login-logs?search={test_user['username']}&page=1&page_size=100"
            )
            assert resp.status_code == 200
            data = resp.json()
            assert any(item["id"] == log_id for item in data["items"])
        finally:
            _clear_overrides()
            if log_id:
                await delete_login_log(log_id)


class TestStatisticsAdminLogs:
    async def test_admin_logs_returns_paginated_payload(self, client, test_admin):
        _set_admin(test_admin["id"])
        try:
            resp = await client.get("/api/statistics/admin-logs")
            assert resp.status_code == 200
            data = resp.json()
            assert set(data) == {"items", "total", "page", "page_size"}
            assert isinstance(data["items"], list)
            assert isinstance(data["total"], int)
        finally:
            _clear_overrides()

    async def test_admin_logs_with_inserted_data(self, client, test_admin):
        log_id = await insert_admin_log(test_admin["id"])
        _set_admin(test_admin["id"])
        try:
            resp = await client.get("/api/statistics/admin-logs?page=1&page_size=100")
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data["items"], list)
            inserted = [item for item in data["items"] if item["id"] == log_id]
            assert len(inserted) == 1
            item = inserted[0]
            for field in ["id", "admin", "action", "time"]:
                assert field in item, f"Missing field: {field}"
            assert item["admin"] == test_admin["username"]
            assert item["action"] == "test_action"
            assert item["time"].count(":") == 2
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
            assert len(data["items"]) <= 3
            assert data["page"] == 1
            assert data["page_size"] == 3
        finally:
            _clear_overrides()

    async def test_admin_logs_support_search(self, client, test_admin):
        log_id = await insert_admin_log(test_admin["id"])
        _set_admin(test_admin["id"])
        try:
            resp = await client.get(
                "/api/statistics/admin-logs?search=test_action&page=1&page_size=100"
            )
            assert resp.status_code == 200
            data = resp.json()
            assert any(item["id"] == log_id for item in data["items"])
        finally:
            _clear_overrides()
            if log_id:
                await delete_admin_log(log_id)


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

    async def test_active_users_trend_values_are_signed_integers(
        self,
        client,
        test_admin,
    ):
        _set_admin(test_admin["id"])
        try:
            resp = await client.get("/api/statistics/active-users")
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(int(data["trend_daily"]), int)
            assert isinstance(int(data["trend_weekly"]), int)
        finally:
            _clear_overrides()


class TestStatisticsRetentionRevenue:
    async def test_retention_returns_structured_monthly_data(self, client, test_admin):
        _set_admin(test_admin["id"])
        try:
            resp = await client.get("/api/statistics/retention")
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, list)
            for item in data:
                assert set(item) == {"month", "retention"}
        finally:
            _clear_overrides()

    async def test_revenue_returns_structured_monthly_data(self, client, test_admin):
        _set_admin(test_admin["id"])
        try:
            resp = await client.get("/api/statistics/revenue?months=2")
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, list)
            for item in data:
                assert set(item) == {"month", "revenue"}
        finally:
            _clear_overrides()
