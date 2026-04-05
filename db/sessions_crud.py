import time
from typing import Optional

from sqlalchemy import delete as sa_delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.session import ActiveSession, LoginAttempt, TrustedDevice, UserLockout
from models.user import User


async def count_active_sessions(
    session: AsyncSession,
    user_id: int,
) -> int:
    stmt = select(func.count(ActiveSession.session_id)).where(
        ActiveSession.user_id == user_id,
        ActiveSession.is_active.is_(True),
    )
    return await session.scalar(stmt) or 0


async def get_oldest_active_session(
    session: AsyncSession,
    user_id: int,
) -> Optional[ActiveSession]:
    stmt = (
        select(ActiveSession)
        .where(
            ActiveSession.user_id == user_id,
            ActiveSession.is_active.is_(True),
        )
        .order_by(ActiveSession.last_activity.asc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def deactivate_session(
    session: AsyncSession,
    session_id: str,
) -> None:
    record = await session.get(ActiveSession, session_id)
    if record:
        record.is_active = False


async def insert_session(
    session: AsyncSession,
    session_id: str,
    user_id: int,
    ip_address: str,
    user_agent: str,
    now: float,
) -> None:
    record = ActiveSession(
        session_id=session_id,
        user_id=user_id,
        created_at=now,
        last_activity=now,
        last_rotation=now,
        ip_address=ip_address,
        user_agent=user_agent,
        is_active=True,
    )
    session.add(record)


async def get_session(
    session: AsyncSession,
    session_id: str,
) -> Optional[ActiveSession]:
    return await session.get(ActiveSession, session_id)


async def get_session_with_user(
    session: AsyncSession,
    session_id: str,
) -> Optional[dict]:
    stmt = (
        select(ActiveSession, User)
        .join(User, ActiveSession.user_id == User.id)
        .where(ActiveSession.session_id == session_id)
    )
    result = await session.execute(stmt)
    row = result.one_or_none()
    if not row:
        return None
    active_session, user = row
    return {
        "session_id": active_session.session_id,
        "user_id": active_session.user_id,
        "created_at": active_session.created_at,
        "last_activity": active_session.last_activity,
        "last_rotation": active_session.last_rotation,
        "ip_address": active_session.ip_address,
        "user_agent": active_session.user_agent,
        "is_active": active_session.is_active,
        "username": user.username,
        "role": user.role,
        "is_frozen": user.is_frozen,
        "user_type": user.user_type,
    }


async def update_session_activity(
    session: AsyncSession,
    session_id: str,
    now: float,
) -> None:
    await session.execute(
        update(ActiveSession)
        .where(ActiveSession.session_id == session_id)
        .values(last_activity=now)
    )


async def deactivate_all_sessions(
    session: AsyncSession,
    user_id: int,
    exclude_session_id: Optional[str] = None,
) -> None:
    stmt = (
        update(ActiveSession)
        .where(
            ActiveSession.user_id == user_id,
            ActiveSession.is_active.is_(True),
        )
        .values(is_active=False)
    )
    if exclude_session_id:
        stmt = (
            update(ActiveSession)
            .where(
                ActiveSession.user_id == user_id,
                ActiveSession.is_active.is_(True),
                ActiveSession.session_id != exclude_session_id,
            )
            .values(is_active=False)
        )
    await session.execute(stmt)


async def get_login_attempts(
    session: AsyncSession,
    identifier: str,
    since: float,
) -> list:
    stmt = select(LoginAttempt).where(
        LoginAttempt.identifier == identifier,
        LoginAttempt.timestamp > since,
    )
    result = await session.execute(stmt)
    return result.scalars().all()


async def add_login_attempt(
    session: AsyncSession,
    identifier: str,
    ip_address: str,
    success: bool,
    user_agent: str,
) -> None:
    record = LoginAttempt(
        identifier=identifier,
        ip_address=ip_address,
        timestamp=time.time(),
        success=success,
        user_agent=user_agent,
    )
    session.add(record)


async def get_lockout(
    session: AsyncSession,
    identifier: str,
) -> Optional[UserLockout]:
    return await session.get(UserLockout, identifier)


async def set_lockout(
    session: AsyncSession,
    identifier: str,
    locked_until: float,
    attempt_count: int,
) -> None:
    record = await session.get(UserLockout, identifier)
    if record:
        record.locked_until = locked_until
        record.attempt_count = attempt_count
    else:
        record = UserLockout(
            identifier=identifier,
            locked_until=locked_until,
            attempt_count=attempt_count,
        )
        session.add(record)


async def remove_lockout(
    session: AsyncSession,
    identifier: str,
) -> None:
    await session.execute(
        sa_delete(UserLockout).where(UserLockout.identifier == identifier)
    )


async def get_trusted_device(
    session: AsyncSession,
    user_id: int,
    fingerprint: str,
) -> Optional[TrustedDevice]:
    stmt = select(TrustedDevice).where(
        TrustedDevice.user_id == user_id,
        TrustedDevice.device_fingerprint == fingerprint,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def add_trusted_device(
    session: AsyncSession,
    user_id: int,
    fingerprint: str,
    ip_address: str,
    user_agent: str,
) -> None:
    now = time.time()
    record = TrustedDevice(
        user_id=user_id,
        device_fingerprint=fingerprint,
        ip_address=ip_address,
        user_agent=user_agent,
        trusted_at=now,
        last_used=now,
        is_active=True,
    )
    session.add(record)


async def deactivate_trusted_device(
    session: AsyncSession,
    user_id: int,
    fingerprint: str,
) -> None:
    stmt = select(TrustedDevice).where(
        TrustedDevice.user_id == user_id,
        TrustedDevice.device_fingerprint == fingerprint,
    )
    result = await session.execute(stmt)
    record = result.scalar_one_or_none()
    if record:
        record.is_active = False
