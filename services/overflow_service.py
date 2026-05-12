"""Overflow trim / reselect / window-management service.

Concurrency model:
  - auto_trim_user_rules: SELECT FOR UPDATE on user's logistics rows + window
    insert in an explicit transaction. Uses SAVEPOINT when the caller already
    has an open transaction; otherwise commits its own transaction.
  - reselect_kept_rules: validates ownership + count BEFORE mutating; closes
    open window with reason='reselected' atomically.
  - close_expired_windows: bulk UPDATE used by scheduler; idempotent.

Window invariants (enforced by partial unique index uq_overflow_open_per_user):
  - At most ONE row per user with closed_at = 0.
  - close_reason in ('expired','upgraded','reselected') once closed.

mark_logistics_used 60s throttle: prevents write-amplification on every pricing
call. Tradeoff: MRU may lag <60s, acceptable for trim ordering.
"""
import time
from dataclasses import dataclass
from typing import Any, Iterable, Literal, cast

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.logistics import Logistics
from models.trial_overflow_window import TrialOverflowWindow


WINDOW_DURATION_SECONDS = 48 * 3600
MARK_USED_THROTTLE_SECONDS = 60

CloseReason = Literal["expired", "upgraded", "reselected"]


@dataclass
class TrimResult:
    trimmed_count: int
    kept_ids: list[int]
    disabled_ids: list[int]
    window_id: int


@dataclass
class ReselectResult:
    status: Literal["ok", "no_open_window", "ids_not_owned", "exceeds_limit"]
    enabled_ids: list[int]
    disabled_ids: list[int]


async def _get_open_window(session: AsyncSession, user_id: int):
    stmt = select(TrialOverflowWindow).where(
        TrialOverflowWindow.user_id == user_id,
        TrialOverflowWindow.closed_at == 0,
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def auto_trim_user_rules(
    session: AsyncSession,
    user_id: int,
    limit: int,
) -> TrimResult:
    """Disable rules beyond `limit`, MRU-preserving. Opens a 48h window.

    MRU order: last_used_at DESC, id DESC (id breaks ties when last_used_at=0).
    Only acts on is_active=1 AND disabled_by_overflow=0 rows.
    Idempotent if no overflow exists (returns trimmed_count=0, may still open
    a window if none open — caller checks). limit < 0 means unlimited (no-op).
    Commits when called standalone; when called inside a caller-owned
    transaction, uses a nested SAVEPOINT and the outer caller commits.
    """
    if limit < 0:
        return TrimResult(0, [], [], 0)

    if session.in_transaction():
        async with session.begin_nested():
            return await _auto_trim_user_rules_locked(session, user_id, limit)

    async with session.begin():
        return await _auto_trim_user_rules_locked(session, user_id, limit)


async def _auto_trim_user_rules_locked(
    session: AsyncSession,
    user_id: int,
    limit: int,
) -> TrimResult:
    """Implementation body for auto_trim_user_rules transaction wrapper."""

    stmt = (
        select(Logistics.id, Logistics.last_used_at)
        .where(
            Logistics.user_id == user_id,
            Logistics.is_active == 1,
            Logistics.disabled_by_overflow == 0,
        )
        .order_by(Logistics.last_used_at.desc(), Logistics.id.desc())
        .with_for_update()
    )
    rows = (await session.execute(stmt)).all()
    all_ids = [r[0] for r in rows]

    if len(all_ids) <= limit:
        return TrimResult(0, all_ids, [], 0)

    kept_ids = all_ids[:limit]
    to_disable = all_ids[limit:]

    await session.execute(
        update(Logistics)
        .where(Logistics.id.in_(to_disable))
        .values(disabled_by_overflow=1)
    )

    now = int(time.time())
    existing_open = await _get_open_window(session, user_id)
    if existing_open is not None:
        return TrimResult(
            trimmed_count=len(to_disable),
            kept_ids=kept_ids,
            disabled_ids=to_disable,
            window_id=existing_open.id,
        )

    win = TrialOverflowWindow(
        user_id=user_id,
        opened_at=now,
        expires_at=now + WINDOW_DURATION_SECONDS,
        closed_at=0,
        close_reason="",
    )
    session.add(win)
    await session.flush()
    return TrimResult(
        trimmed_count=len(to_disable),
        kept_ids=kept_ids,
        disabled_ids=to_disable,
        window_id=win.id,
    )


async def reselect_kept_rules(
    session: AsyncSession,
    user_id: int,
    keep_ids: set[int],
    limit: int,
) -> ReselectResult:
    """User picks which rules to keep (within new limit). Closes open window.

    Validation order (caller may inspect status to map HTTP code):
      - exceeds_limit: len(keep_ids) > limit (when limit >= 0)
      - ids_not_owned: any id not in user's logistics
      - no_open_window: nothing to reselect against
    On 'ok': enable keep_ids, disable the rest of user's overflowed rules,
    close window with close_reason='reselected'. Caller commits.
    """
    if limit >= 0 and len(keep_ids) > limit:
        return ReselectResult("exceeds_limit", [], [])

    own_stmt = select(Logistics.id).where(
        Logistics.user_id == user_id,
        Logistics.is_active == 1,
    )
    owned = {row[0] for row in (await session.execute(own_stmt)).all()}
    if not keep_ids.issubset(owned):
        return ReselectResult("ids_not_owned", [], [])

    win = await _get_open_window(session, user_id)
    if win is None:
        return ReselectResult("no_open_window", [], [])

    keep_list = list(keep_ids)
    disable_list = list(owned - keep_ids)

    if keep_list:
        await session.execute(
            update(Logistics)
            .where(Logistics.id.in_(keep_list))
            .values(disabled_by_overflow=0)
        )
    if disable_list:
        await session.execute(
            update(Logistics)
            .where(Logistics.id.in_(disable_list))
            .values(disabled_by_overflow=1)
        )

    now = int(time.time())
    win.closed_at = now
    win.close_reason = "reselected"
    return ReselectResult("ok", keep_list, disable_list)


async def restore_all_overflow(
    session: AsyncSession,
    user_id: int,
    reason: CloseReason,
) -> int:
    """Re-enable ALL overflow-disabled rules + close any open window.

    Used on upgrade. Returns count of rules restored. Caller commits.
    """
    res = await session.execute(
        update(Logistics)
        .where(
            Logistics.user_id == user_id,
            Logistics.disabled_by_overflow == 1,
        )
        .values(disabled_by_overflow=0)
    )
    restored = cast(Any, res).rowcount or 0

    win = await _get_open_window(session, user_id)
    if win is not None:
        win.closed_at = int(time.time())
        win.close_reason = reason

    return restored


async def mark_logistics_used(
    session: AsyncSession,
    user_id: int,
    rule_ids: Iterable[int],
    now: int | None = None,
) -> int:
    """Update last_used_at, throttled to once per 60s per row.

    Returns rowcount. Caller commits.
    """
    rule_ids = list(rule_ids)
    if not rule_ids:
        return 0
    cur = int(now if now is not None else time.time())
    threshold = cur - MARK_USED_THROTTLE_SECONDS
    res = await session.execute(
        update(Logistics)
        .where(
            Logistics.user_id == user_id,
            Logistics.id.in_(rule_ids),
            Logistics.last_used_at < threshold,
        )
        .values(last_used_at=cur)
    )
    return cast(Any, res).rowcount or 0


async def close_expired_windows(
    session: AsyncSession,
    now: int | None = None,
) -> int:
    """Scheduler entry: close all OPEN windows past expires_at.

    Idempotent. Returns count closed. Caller commits.
    """
    cur = int(now if now is not None else time.time())
    res = await session.execute(
        update(TrialOverflowWindow)
        .where(
            and_(
                TrialOverflowWindow.closed_at == 0,
                TrialOverflowWindow.expires_at <= cur,
            )
        )
        .values(closed_at=cur, close_reason="expired")
    )
    return cast(Any, res).rowcount or 0


__all__ = [
    "auto_trim_user_rules",
    "reselect_kept_rules",
    "restore_all_overflow",
    "mark_logistics_used",
    "close_expired_windows",
    "TrimResult",
    "ReselectResult",
    "WINDOW_DURATION_SECONDS",
    "MARK_USED_THROTTLE_SECONDS",
]
