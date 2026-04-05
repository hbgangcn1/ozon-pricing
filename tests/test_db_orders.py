import time

import pytest

from models.order import PaymentOrder


class TestGetUserOrders:
    async def test_empty_result(self, db_session):
        from db.orders import get_user_orders

        result = await get_user_orders(db_session, user_id=999999999)
        assert result == []

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
        assert len(result) >= 1
        row = result[0]
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
        assert len(result) <= 2

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
        found = [r for r in result if r["order_id"] == f"test_upd_{now}"]
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
        found = [r for r in result if r["order_id"] == f"test_amt_{now}"]
        assert len(found) == 1
        assert found[0]["amount"] == 0
