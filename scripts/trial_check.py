"""Trial expiry + overflow window scheduler (systemd-driven, cross-process safe).

Run hourly from systemd timer (`deploy/trial-check.timer`). Two responsibilities:

1. **Trial expiry**: For users whose 7-day professional trial has ended
   (``trial_expires_at <= now AND trial_plan_at_start <> ''``), evaluate the
   post-trial limit. If they now exceed it, auto-trim by MRU and open a 48h
   reselection window. Always clear ``trial_plan_at_start`` to mark the user
   as "processed" (this is the idempotency key — re-runs skip them).

2. **Window expiry**: Close any ``trial_overflow_window`` rows whose 48h
   deadline has passed (``close_reason = 'expired'``).

Cross-process safety: ``FOR UPDATE SKIP LOCKED`` on the user row prevents
two timer firings (or a manual ad-hoc run) from double-processing the same
user. ``apply_subscription_change`` is intentionally NOT called — the trial
overlay never wrote to ``users.subscription_type``, so there is no plan
field to flip; only the trim + window logic runs.
"""
import argparse
import asyncio
import logging
import sys
import time

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from database import AsyncSessionLocal
from models.user import User
from services.overflow_service import (
    auto_trim_user_rules,
    close_expired_windows,
)
from services.plan_resolution import (
    count_user_active_rules,
    get_effective_logistics_limit,
)


logger = logging.getLogger("trial_check")


async def _expire_trials(session: AsyncSession, now: int, dry_run: bool) -> int:
    # Lock candidate rows so concurrent timer fires (or an admin re-run)
    # cannot double-process the same user. SKIP LOCKED keeps each process
    # working on disjoint subsets without blocking.
    stmt = (
        select(User)
        .where(
            User.trial_expires_at > 0,
            User.trial_expires_at <= now,
            User.trial_plan_at_start != "",
        )
        .with_for_update(skip_locked=True)
    )
    users = (await session.execute(stmt)).scalars().all()
    processed = 0
    trimmed_users = 0

    for user in users:
        # After expiry the trial overlay is gone — get_effective_plan now
        # returns the stored subscription_type (free/efficiency/etc.), so
        # the limit reflects the *real* plan the user is dropping back to.
        limit = await get_effective_logistics_limit(session, user)
        active_count = await count_user_active_rules(session, user.id)

        if limit > 0 and active_count > limit:
            if not dry_run:
                await auto_trim_user_rules(session, user.id, limit)
            trimmed_users += 1
            logger.info(
                "user %s: trim %s -> %s (plan=%s)",
                user.id, active_count, limit, user.subscription_type,
            )

        if not dry_run:
            # Clear the marker AFTER the trim so a crash between trim and
            # marker-clear leaves the user re-eligible for retry.
            await session.execute(
                update(User)
                .where(User.id == user.id)
                .values(trial_plan_at_start="")
            )
        processed += 1

    logger.info(
        "trials: %s processed, %s trimmed (dry_run=%s)",
        processed, trimmed_users, dry_run,
    )
    return processed


async def _close_windows(session: AsyncSession, now: int, dry_run: bool) -> int:
    if dry_run:
        # Mirror close_expired_windows' WHERE clause without writing so the
        # dry-run log reports an accurate count.
        from models.trial_overflow_window import TrialOverflowWindow
        stmt = select(TrialOverflowWindow.id).where(
            TrialOverflowWindow.closed_at == 0,
            TrialOverflowWindow.expires_at <= now,
        )
        count = len((await session.execute(stmt)).all())
        logger.info("windows: %s would close (dry_run=True)", count)
        return count

    closed = await close_expired_windows(session, now)
    logger.info("windows: %s closed", closed)
    return closed


async def run(dry_run: bool) -> int:
    now = int(time.time())
    async with AsyncSessionLocal() as session:
        try:
            users = await _expire_trials(session, now, dry_run)
            windows = await _close_windows(session, now, dry_run)
            if dry_run:
                # Roll back to guarantee zero side-effects even if a future
                # change introduces an accidental write.
                await session.rollback()
                logger.info(
                    "dry-run, would process %s users, %s windows",
                    users, windows,
                )
            else:
                await session.commit()
                logger.info(
                    "processed %s users, %s windows", users, windows,
                )
        except Exception:
            await session.rollback()
            raise
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    # --once is the only supported mode today; declared explicitly so
    # systemd unit + future loop modes share one CLI surface.
    parser.add_argument("--once", action="store_true", default=True,
                        help="Run a single sweep then exit (default).")
    parser.add_argument("--dry-run", action="store_true", default=False,
                        help="Log actions without committing.")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    return asyncio.run(run(dry_run=args.dry_run))


if __name__ == "__main__":
    sys.exit(main())
