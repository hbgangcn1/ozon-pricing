"""Trial claim and status helpers.

Concurrency model: claim_trial uses a conditional UPDATE with WHERE filter
on trial_used=0 AND eligible plan, then COMMIT. The DB enforces single-
winner semantics across N parallel claims via row-level lock + WHERE clause
re-check (rowcount==1 means we won, rowcount==0 means somebody else did).
We never read-then-write because that races.
"""
import time
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User
from services.plan_resolution import is_in_trial


TRIAL_DURATION_SECONDS = 7 * 24 * 3600
ELIGIBLE_PLANS_FOR_TRIAL = ("free", "efficiency")

ClaimStatus = Literal["claimed", "already_used", "ineligible_plan", "user_not_found"]


@dataclass
class ClaimResult:
    status: ClaimStatus
    trial_started_at: int = 0
    trial_expires_at: int = 0


@dataclass
class TrialStatus:
    eligible: bool
    in_trial: bool
    trial_used: bool
    remaining_seconds: int
    trial_expires_at: int
    trial_started_at: int


async def claim_trial(session: AsyncSession, user_id: int) -> ClaimResult:
    """Atomically claim the 7-day professional trial for user_id.

    Returns ClaimResult with status:
      - claimed: trial activated by this call
      - already_used: trial_used=1 already
      - ineligible_plan: subscription_type not in ELIGIBLE_PLANS_FOR_TRIAL
      - user_not_found: no such user

    Caller MUST commit the session for the claim to persist.
    """
    user = await session.get(User, user_id)
    if user is None:
        return ClaimResult(status="user_not_found")

    if (user.trial_used or 0) == 1:
        return ClaimResult(status="already_used")

    current_plan = user.subscription_type or "free"
    if current_plan not in ELIGIBLE_PLANS_FOR_TRIAL:
        return ClaimResult(status="ineligible_plan")

    now = int(time.time())
    expires = now + TRIAL_DURATION_SECONDS

    stmt = (
        update(User)
        .where(
            User.id == user_id,
            User.trial_used == 0,
            User.subscription_type.in_(ELIGIBLE_PLANS_FOR_TRIAL),
        )
        .values(
            trial_used=1,
            trial_started_at=now,
            trial_expires_at=expires,
            trial_plan_at_start=current_plan,
        )
    )
    result = await session.execute(stmt)
    if (result.rowcount or 0) == 0:
        return ClaimResult(status="already_used")

    await session.commit()
    return ClaimResult(
        status="claimed",
        trial_started_at=now,
        trial_expires_at=expires,
    )


def get_trial_status(user) -> TrialStatus:
    """Compute TrialStatus from a User instance (no DB I/O)."""
    trial_used = bool((getattr(user, "trial_used", 0) or 0) == 1)
    expires = int(getattr(user, "trial_expires_at", 0) or 0)
    started = int(getattr(user, "trial_started_at", 0) or 0)
    plan = getattr(user, "subscription_type", None) or "free"
    in_trial = is_in_trial(user)
    eligible = (not trial_used) and (plan in ELIGIBLE_PLANS_FOR_TRIAL)
    remaining = max(0, expires - int(time.time())) if in_trial else 0
    return TrialStatus(
        eligible=eligible,
        in_trial=in_trial,
        trial_used=trial_used,
        remaining_seconds=remaining,
        trial_expires_at=expires,
        trial_started_at=started,
    )
