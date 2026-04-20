import logging
import time
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from models.log import (
    UserLoginLog,
    UserBehaviorLog,
    AdminActionLog,
    AlertRecord,
)

logger = logging.getLogger(__name__)


async def log_user_login(
    session: AsyncSession,
    user_id: int,
    ip_address: str = "",
    user_agent: str = "",
    device_type: str = "",
) -> None:
    try:
        if not device_type and user_agent:
            ua_lower = user_agent.lower()
            if "mobile" in ua_lower or "android" in ua_lower:
                device_type = "mobile"
            elif "tablet" in ua_lower or "ipad" in ua_lower:
                device_type = "tablet"
            else:
                device_type = "desktop"
        record = UserLoginLog(
            user_id=user_id,
            login_time=int(time.time()),
            ip_address=ip_address,
            user_agent=user_agent,
            device_type=device_type,
        )
        session.add(record)
    except Exception:
        logger.warning("记录用户登录失败", exc_info=True)


async def log_user_behavior(
    session: AsyncSession,
    user_id: int,
    behavior_type: str,
    behavior_detail: str = "",
    calculation_mode: str = "",
) -> None:
    try:
        record = UserBehaviorLog(
            user_id=user_id,
            behavior_type=behavior_type,
            behavior_detail=behavior_detail,
            calculation_mode=calculation_mode,
        )
        session.add(record)
    except Exception:
        logger.warning("记录用户行为失败", exc_info=True)


async def log_admin_action(
    session: AsyncSession,
    admin_id: int,
    action_type: str,
    action_detail: str = "",
    target_user_id: Optional[int] = None,
    target_type: str = "",
    ip_address: str = "",
) -> None:
    try:
        record = AdminActionLog(
            admin_id=admin_id,
            action_type=action_type,
            action_detail=action_detail,
            target_user_id=target_user_id,
            target_type=target_type,
            ip_address=ip_address,
        )
        session.add(record)
    except Exception:
        logger.warning("记录管理员操作失败", exc_info=True)


async def create_alert(
    session: AsyncSession,
    alert_type: str,
    alert_level: str,
    description: str,
    threshold_value: Optional[float] = None,
    actual_value: Optional[float] = None,
) -> Optional[int]:
    try:
        record = AlertRecord(
            alert_type=alert_type,
            alert_level=alert_level,
            description=description,
            threshold_value=threshold_value,
            actual_value=actual_value,
        )
        session.add(record)
        await session.flush()
        return record.id
    except Exception:
        logger.warning("创建告警失败", exc_info=True)
        return None
