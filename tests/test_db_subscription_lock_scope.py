import asyncio

import pytest
from sqlalchemy import select, text

from database import AsyncSessionLocal
from db.subscriptions import apply_paid_subscription
from models.user import User


@pytest.mark.asyncio
async def test_paid_subscription_lock_does_not_block_readonly_select(test_user):
    user_id = test_user["id"]

    async def locked_update() -> None:
        async with AsyncSessionLocal() as session:
            await apply_paid_subscription(
                session,
                user_id,
                "professional",
                source="lock-scope-test",
                duration_days=30,
            )
            await session.execute(text("SELECT pg_sleep(0.35)"))
            await session.commit()

    async def readonly_select() -> str:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
            await asyncio.sleep(0.05)
            result = await asyncio.wait_for(
                session.execute(
                    select(User.subscription_type).where(User.id == user_id)
                ),
                timeout=0.2,
            )
            return result.scalar_one()

    update_task = asyncio.create_task(locked_update())
    read_value = await readonly_select()
    await update_task

    assert read_value == "free"
