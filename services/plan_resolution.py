"""Plan resolution helpers for trial-aware effective plan/limit lookup.

These pure helpers are the SINGLE source of truth for "what plan / limit
does this user effectively have right now?". The trial overlay (in_trial =>
professional) lives here so callers (pricing, logistics CRUD, scheduler)
never need to special-case trial users.
"""
import time

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.plans import get_plan_by_code
from models.logistics import Logistics


# Hardcoded fallback limits when the plans table lookup fails. These match
# the seeded values in production but exist so plan_resolution stays usable
# in unit tests that do not seed Plan rows.
_FALLBACK_LIMITS = {
    "free": 1,
    "efficiency": 3,
    "professional": 10,
    "enterprise": -1,
    "gratitude": -1,
}


def is_in_trial(user) -> bool:
    """Return True iff user has an unexpired professional trial active.

    Narrow defensive cast: only int/float values count as a real trial
    expiry. Anything else (None, MagicMock from tests, malformed strings,
    arbitrary objects) is treated as "no trial". The User ORM column is
    Integer nullable=False default 0, so production values are always
    int/None — this guard exists so test doubles and edge objects cannot
    blow up the global plan-gate path with a TypeError.
    """
    raw = getattr(user, "trial_expires_at", None)
    expires = int(raw) if isinstance(raw, (int, float)) and not isinstance(raw, bool) else 0
    if expires <= 0:
        return False
    return int(time.time()) < expires


def get_effective_plan(user) -> str:
    """Return the plan code that should govern feature access right now.

    During an active trial this returns 'professional' regardless of the
    underlying users.subscription_type column (which is never modified by
    trial claim). Outside trial it returns the stored subscription_type.
    """
    if is_in_trial(user):
        return "professional"
    plan = getattr(user, "subscription_type", None) or "free"
    return plan


async def get_effective_logistics_limit(
    session: AsyncSession,
    user,
) -> int:
    """Resolve the logistics rule limit for the user's effective plan.

    Returns -1 for unlimited (enterprise/gratitude). Falls back to a
    hardcoded table if the plans row is missing (defensive against
    misconfigured environments).
    """
    plan_code = get_effective_plan(user)
    plan = await get_plan_by_code(session, plan_code)
    if plan and plan.get("logistics_limit") is not None:
        return int(plan["logistics_limit"])
    return _FALLBACK_LIMITS.get(plan_code, 1)


async def count_user_active_rules(
    session: AsyncSession,
    user_id: int,
) -> int:
    """Count rules that count against the user's logistics_limit.

    Active means is_active=1 AND disabled_by_overflow=0. Overflow-disabled
    rules are intentionally excluded so a downgrade->reselect cycle does
    not double-count the trimmed rules against the new limit.
    """
    stmt = (
        select(func.count())
        .select_from(Logistics)
        .where(
            Logistics.user_id == user_id,
            Logistics.is_active == 1,
            Logistics.disabled_by_overflow == 0,
        )
    )
    result = await session.execute(stmt)
    return int(result.scalar_one() or 0)
