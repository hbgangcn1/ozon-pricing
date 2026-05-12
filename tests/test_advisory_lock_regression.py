"""W10 TEST#4 — Advisory lock concurrency regression.

W9 SEC#2 introduced ``pg_advisory_xact_lock`` to serialize per-user plan-limit
checks on hot write paths (``POST /api/logistics``,
``POST /api/logistics-pool/...``). Without the lock, concurrent inserts could
all observe ``count<limit`` and exceed the plan cap. With the lock, the
per-user critical section is serialized.

This regression test fires 20 concurrent ``POST /api/logistics`` requests and
asserts:

1. **No 5xx errors** — the lock must not cause SQL errors, deadlocks, or
   driver-level failures (asyncpg ``InterfaceError``, etc.).
2. **Plan cap respected** — total active rules in DB stays ≤ effective limit.
3. **Status codes are well-formed** — every response is either 201 (created)
   or 403 (limit reached). Anything else (500, 502, 422) is a regression.

The test uses real PostgreSQL (worker-isolated schema, see
``tests/_db_isolation.py``) — no mocks, so it exercises the actual
``pg_advisory_xact_lock`` semantics.
"""

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from api import dependencies
from api.main import app
from database import AsyncSessionLocal, get_db
from models.logistics import Logistics
from models.user import User


CONCURRENCY = 20
"""Number of concurrent POST requests fired at the locked endpoint."""


def _override_user(user_id: int):
    return lambda: user_id


def _payload(name: str) -> dict:
    return {
        "name": name,
        "type": "land",
        "min_days": 5,
        "max_days": 30,
        "base_fee": 10,
        "min_weight": 0,
        "max_weight": 30000,
        "max_sum_of_sides": 200,
        "max_longest_side": 100,
        "volume_mode": "longest_side",
        "longest_side_threshold": 60,
        "fee_mode": "first_continue",
        "first_fee": 10,
        "first_weight_g": 500,
        "continue_fee": 5,
        "continue_unit": "g",
        "fulfillment_type": "rfbs",
        "destination": "RU",
        "is_active": True,
    }


async def _independent_get_db():
    """Per-request session — required for true concurrency.

    Reusing a single ``AsyncSession`` across concurrent ASGI requests would
    serialize them at the SQLAlchemy session level, defeating the purpose of
    this regression test.
    """
    async with AsyncSessionLocal() as s:
        try:
            yield s
            await s.commit()
        except Exception:
            await s.rollback()
            raise


@pytest.mark.asyncio
async def test_advisory_lock_no_500_under_20_concurrent_posts(
    db_session,
    test_user,
):
    """20 concurrent POSTs to the advisory-lock-protected endpoint.

    Asserts:
      * All responses have ``status_code < 500`` (no SQL/driver/lock errors).
      * Every response is either 201 or 403 (well-formed plan-limit outcome).
      * DB row count never exceeds the effective plan limit (lock holds).
    """
    user_id = test_user["id"]

    # Give the user a free plan with limit=1 so 19 of 20 requests will be
    # rejected with 403 — the interesting assertion is no 500s.
    user = await db_session.get(User, user_id)
    user.subscription_type = "free"
    user.trial_expires_at = 0
    await db_session.commit()
    await db_session.rollback()

    app.dependency_overrides[dependencies.get_current_user_id] = _override_user(
        user_id
    )
    app.dependency_overrides[get_db] = _independent_get_db

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            tasks = [
                ac.post("/api/logistics", json=_payload(f"adv_lock_{i}"))
                for i in range(CONCURRENCY)
            ]
            responses = await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        app.dependency_overrides.pop(dependencies.get_current_user_id, None)
        app.dependency_overrides.pop(get_db, None)

    # 1. No raised exceptions (driver-level / asyncio failures).
    raised = [r for r in responses if isinstance(r, BaseException)]
    assert not raised, (
        f"{len(raised)}/{CONCURRENCY} requests raised exceptions: "
        f"{[type(e).__name__ + ': ' + str(e) for e in raised[:3]]}"
    )

    ok_responses = [r for r in responses if not isinstance(r, BaseException)]

    # 2. No 5xx responses (server-side errors).
    server_errors = [r for r in ok_responses if r.status_code >= 500]
    assert not server_errors, (
        f"{len(server_errors)}/{CONCURRENCY} responses returned 5xx: "
        f"statuses={[r.status_code for r in server_errors[:5]]}, "
        f"first_body={server_errors[0].text[:300] if server_errors else ''}"
    )

    # 3. Every response is either 201 (created) or 403 (limit reached).
    statuses = [r.status_code for r in ok_responses]
    unexpected = [s for s in statuses if s not in (201, 403)]
    assert not unexpected, (
        f"unexpected status codes (expected only 201/403): {unexpected}; "
        f"full distribution: {sorted(statuses)}"
    )

    # 4. DB row count must respect plan cap (free plan = 1 active rule).
    async with AsyncSessionLocal() as verify:
        row_count = (
            await verify.execute(
                select(func.count())
                .select_from(Logistics)
                .where(Logistics.user_id == user_id)
            )
        ).scalar_one()

    success_count = sum(1 for s in statuses if s == 201)
    assert row_count <= 1, (
        f"DB row count {row_count} exceeds free-plan limit 1 — "
        f"advisory lock failed to serialize concurrent inserts "
        f"(success_count={success_count}, statuses={sorted(statuses)})"
    )
    assert row_count == success_count, (
        f"DB row count {row_count} != HTTP 201 count {success_count} — "
        f"transaction commit/rollback inconsistency"
    )
