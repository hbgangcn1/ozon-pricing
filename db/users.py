import logging
import time
from typing import Optional

from sqlalchemy import delete as sa_delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.password import hash_password, is_bcrypt_hash, verify_password
from models.log import AdminActionLog, AlertRecord, UserBehaviorLog, UserLoginLog
from models.logistics import Logistics
from models.order import PaymentOrder
from models.session import ActiveSession, LoginAttempt, UserLockout
from models.user import SubscriptionUpgradeHistory, User

logger = logging.getLogger(__name__)


def _get_remaining_calculations(user_type):
    if user_type == "free":
        return 10
    elif user_type in [
        "test",
        "gratitude",
        "efficiency",
        "professional",
        "enterprise",
    ]:
        return -1
    else:
        return 10


async def create_user(
    session: AsyncSession,
    username,
    password,
    role="user",
    email=None,
    user_type="free",
    is_test_user=False,
) -> Optional[int]:
    if not username or len(username.strip()) == 0:
        return None

    stmt = select(User).where(func.lower(User.username) == func.lower(username))
    result = await session.execute(stmt)
    if result.scalar_one_or_none():
        return None

    if email:
        stmt = select(User).where(func.lower(User.email) == func.lower(email))
        result = await session.execute(stmt)
        if result.scalar_one_or_none():
            return None

    try:
        remaining = _get_remaining_calculations(user_type)
        user = User(
            username=username,
            password=hash_password(password),
            role=role,
            email=email,
            user_type=user_type,
            subscription_type=user_type,
            remaining_calculations=remaining,
            created_at=str(int(time.time())),
            is_test_user=1 if is_test_user else 0,
        )
        session.add(user)
        await session.flush()
        return user.id
    except Exception as e:
        logger.warning("创建用户失败: %s", e)
        return None


async def verify_user(
    session: AsyncSession,
    identifier,
    password,
) -> Optional[dict]:
    stmt = select(User).where(
        or_(
            func.lower(User.username) == func.lower(identifier),
            func.lower(User.email) == func.lower(identifier),
        )
    )
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        return None

    stored = user.password or ""
    if not verify_password(password, stored):
        return None

    # Auto-migrate legacy SHA-256 hash to bcrypt
    if not is_bcrypt_hash(stored):
        user.password = hash_password(password)
        logger.info("Migrated password hash to bcrypt for user %s", user.username)

    return {
        "id": user.id,
        "username": user.username,
        "password": user.password,
        "role": user.role,
        "email": user.email,
        "user_type": user.user_type or "free",
        "subscription_type": user.subscription_type or "free",
        "remaining_calculations": user.remaining_calculations,
    }


async def update_user_password(
    session: AsyncSession,
    user_id,
    current_password,
    new_password,
) -> bool:
    user = await session.get(User, user_id)
    if not user:
        return False

    stored = user.password or ""
    if not verify_password(current_password, stored):
        return False

    user.password = hash_password(new_password)
    return True


async def delete_user(
    session: AsyncSession,
    user_id,
) -> bool:
    user = await session.get(User, user_id)
    if not user:
        logger.info("删除失败: 用户 ID=%s 不存在", user_id)
        return False

    if user.role == "admin":
        logger.info("删除失败: 用户 %s 是管理员，不允许删除", user.username)
        return False

    username = user.username

    await session.execute(sa_delete(Logistics).where(Logistics.user_id == user_id))
    await session.execute(
        sa_delete(PaymentOrder).where(PaymentOrder.user_id == user_id)
    )
    await session.execute(
        sa_delete(SubscriptionUpgradeHistory).where(
            SubscriptionUpgradeHistory.user_id == user_id
        )
    )
    await session.execute(
        sa_delete(ActiveSession).where(ActiveSession.user_id == user_id)
    )
    if username:
        await session.execute(
            sa_delete(LoginAttempt).where(LoginAttempt.identifier == username)
        )
        await session.execute(
            sa_delete(UserLockout).where(UserLockout.identifier == username)
        )
    await session.execute(
        sa_delete(UserLoginLog).where(UserLoginLog.user_id == user_id)
    )
    await session.execute(
        sa_delete(UserBehaviorLog).where(UserBehaviorLog.user_id == user_id)
    )
    await session.execute(
        sa_delete(AdminActionLog).where(
            or_(
                AdminActionLog.admin_id == user_id,
                AdminActionLog.target_user_id == user_id,
            )
        )
    )
    await session.execute(
        update(AlertRecord)
        .where(AlertRecord.handled_by == user_id)
        .values(handled_by=None)
    )

    await session.delete(user)
    logger.info("成功删除用户 %s (ID=%s)", username, user_id)
    return True


async def get_user_preferred_mode(
    session: AsyncSession,
    user_id,
) -> Optional[str]:
    stmt = select(User.preferred_mode).where(User.id == user_id)
    result = await session.execute(stmt)
    row = result.one_or_none()
    return row[0] if row else None


async def update_user_preferred_mode(
    session: AsyncSession,
    user_id,
    mode,
) -> None:
    user = await session.get(User, user_id)
    if user:
        user.preferred_mode = mode


async def find_by_username(
    session: AsyncSession,
    username,
) -> Optional[User]:
    stmt = select(User).where(func.lower(User.username) == func.lower(username))
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_user_by_id(
    session: AsyncSession,
    user_id,
) -> Optional[User]:
    return await session.get(User, user_id)


async def get_user_role(
    session: AsyncSession,
    user_id,
) -> Optional[str]:
    stmt = select(User.role).where(User.id == user_id)
    result = await session.execute(stmt)
    row = result.one_or_none()
    return row[0] if row else None
