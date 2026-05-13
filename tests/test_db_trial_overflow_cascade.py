import time

import pytest
from sqlalchemy import func, select

from models.trial_overflow_window import TrialOverflowWindow
from models.user import User


@pytest.mark.asyncio
async def test_trial_overflow_window_cascades_when_user_deleted(db_session):
    user = User(
        username=f"test_trial_cascade_{int(time.time() * 1000)}",
        password="hashed",
        role="user",
        user_type="free",
        subscription_type="free",
        created_at="2026-05-13 00:00:00",
        is_test_user=1,
    )
    db_session.add(user)
    await db_session.flush()

    window = TrialOverflowWindow(
        user_id=user.id,
        opened_at=100,
        expires_at=200,
    )
    db_session.add(window)
    await db_session.commit()

    await db_session.delete(user)
    await db_session.commit()

    orphan_count = await db_session.scalar(
        select(func.count()).select_from(TrialOverflowWindow).where(
            TrialOverflowWindow.user_id == user.id,
        )
    )
    assert orphan_count == 0
