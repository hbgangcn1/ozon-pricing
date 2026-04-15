import time

import pytest

from models.order import PaymentOrder


class TestGetUserOrders:
    async def test_empty_result(self, db_session):
        from db.orders import get_user_orders

        result = await get_user_orders(db_session, user_id=999999999)
        assert result["orders"] == []
        assert result["total"] == 0

    async def test_returns_orders_with_correct_shape(self, db_session, test_user):
        from db.orders import get_user_orders

        now = int(time.time())
        order = PaymentOrder(
            order_id=f"test_ord_{now}",
            user_id=test_user["id"],
            amount=100,
            description="test order",
            status="PENDING",
            order_type="subscription",
            created_at=now,
        )
        db_session.add(order)
        await db_session.flush()

        result = await get_user_orders(db_session, user_id=test_user["id"])
        assert len(result["orders"]) >= 1
        row = result["orders"][0]
        assert row["order_id"] == f"test_ord_{now}"
        assert row["amount"] == 100.0
        assert row["status"] == "PENDING"
        assert row["order_type"] == "subscription"
        assert "id" in row
        assert "created_at" in row

    async def test_limit_and_offset(self, db_session, test_user):
        from db.orders import get_user_orders

        now = int(time.time())
        for i in range(3):
            order = PaymentOrder(
                order_id=f"test_pag_{now}_{i}",
                user_id=test_user["id"],
                amount=10 * (i + 1),
                description=f"pag order {i}",
                status="PAID",
                order_type="subscription",
                created_at=now + i,
            )
            db_session.add(order)
        await db_session.flush()

        result = await get_user_orders(
            db_session,
            user_id=test_user["id"],
            limit=2,
            offset=0,
        )
        assert len(result["orders"]) <= 2

    async def test_updated_at_none_returns_none(self, db_session, test_user):
        from db.orders import get_user_orders

        now = int(time.time())
        order = PaymentOrder(
            order_id=f"test_upd_{now}",
            user_id=test_user["id"],
            amount=50,
            description="no update",
            status="PENDING",
            order_type="subscription",
            created_at=now,
            updated_at=None,
        )
        db_session.add(order)
        await db_session.flush()

        result = await get_user_orders(db_session, user_id=test_user["id"])
        found = [r for r in result["orders"] if r["order_id"] == f"test_upd_{now}"]
        assert len(found) == 1
        assert found[0]["updated_at"] is None

    async def test_amount_none_returns_zero(self, db_session, test_user):
        from db.orders import get_user_orders

        now = int(time.time())
        order = PaymentOrder(
            order_id=f"test_amt_{now}",
            user_id=test_user["id"],
            amount=0,
            description="zero amount",
            status="PENDING",
            order_type="subscription",
            created_at=now,
        )
        db_session.add(order)
        await db_session.flush()

        result = await get_user_orders(db_session, user_id=test_user["id"])
        found = [r for r in result["orders"] if r["order_id"] == f"test_amt_{now}"]
        assert len(found) == 1
        assert found[0]["amount"] == 0

    async def test_status_filter(self, db_session, test_user):
        from db.orders import get_user_orders

        now = int(time.time())
        for i, status in enumerate(["PENDING", "SUCCESS", "FAILED"]):
            order = PaymentOrder(
                order_id=f"test_sf_{now}_{i}",
                user_id=test_user["id"],
                amount=100,
                description=f"status filter {i}",
                status=status,
                order_type="subscription",
                created_at=now + i,
            )
            db_session.add(order)
        await db_session.flush()

        result = await get_user_orders(
            db_session,
            user_id=test_user["id"],
            status="SUCCESS",
        )
        assert result["total"] == 1
        assert len(result["orders"]) == 1
        assert result["orders"][0]["status"] == "SUCCESS"

    async def test_page_pagination(self, db_session, test_user):
        from db.orders import get_user_orders

        now = int(time.time())
        for i in range(5):
            order = PaymentOrder(
                order_id=f"test_pp_{now}_{i}",
                user_id=test_user["id"],
                amount=10 * (i + 1),
                description=f"page order {i}",
                status="PAID",
                order_type="subscription",
                created_at=now + i,
            )
            db_session.add(order)
        await db_session.flush()

        r1 = await get_user_orders(
            db_session,
            user_id=test_user["id"],
            page=1,
            page_size=2,
        )
        assert len(r1["orders"]) == 2
        assert r1["total"] == 5

        r2 = await get_user_orders(
            db_session,
            user_id=test_user["id"],
            page=2,
            page_size=2,
        )
        assert len(r2["orders"]) == 2
        assert r2["total"] == 5

        ids1 = {o["order_id"] for o in r1["orders"]}
        ids2 = {o["order_id"] for o in r2["orders"]}
        assert ids1.isdisjoint(ids2)

    async def test_page_pagination_last_page(self, db_session, test_user):
        from db.orders import get_user_orders

        now = int(time.time())
        for i in range(5):
            order = PaymentOrder(
                order_id=f"test_lp_{now}_{i}",
                user_id=test_user["id"],
                amount=10,
                description=f"last page {i}",
                status="PAID",
                order_type="subscription",
                created_at=now + i,
            )
            db_session.add(order)
        await db_session.flush()

        result = await get_user_orders(
            db_session,
            user_id=test_user["id"],
            page=3,
            page_size=2,
        )
        assert len(result["orders"]) == 1
        assert result["total"] == 5

    async def test_total_with_status_filter(self, db_session, test_user):
        from db.orders import get_user_orders

        now = int(time.time())
        for i in range(3):
            db_session.add(
                PaymentOrder(
                    order_id=f"test_tsf_s_{now}_{i}",
                    user_id=test_user["id"],
                    amount=100,
                    description=f"success {i}",
                    status="SUCCESS",
                    order_type="subscription",
                    created_at=now + i,
                )
            )
        for i in range(2):
            db_session.add(
                PaymentOrder(
                    order_id=f"test_tsf_p_{now}_{i}",
                    user_id=test_user["id"],
                    amount=50,
                    description=f"pending {i}",
                    status="PENDING",
                    order_type="subscription",
                    created_at=now + 10 + i,
                )
            )
        await db_session.flush()

        result = await get_user_orders(
            db_session,
            user_id=test_user["id"],
            status="SUCCESS",
        )
        assert result["total"] == 3
        assert len(result["orders"]) == 3
        for o in result["orders"]:
            assert o["status"] == "SUCCESS"
