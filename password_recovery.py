# -*- coding: utf-8 -*-
"""
密码找回功能模块
基于安全问题的密码找回机制
"""

import bcrypt
import time
import logging
from typing import Optional, Dict, Any
from datetime import datetime

from database import AsyncSessionLocal
from models.user import User
from models.log import PasswordRecoveryLog
from db.password import hash_password
from sqlalchemy import select, update
from security_questions import validate_security_answers
from password_utils import validate_password_strength

# 配置日志
logger = logging.getLogger(__name__)

# 密码找回配置
MAX_RESET_ATTEMPTS = 3  # 最大尝试次数
RESET_LOCK_DURATION = 1800  # 锁定时长（秒），30分钟


async def log_password_recovery_event(
    username: str,
    event_type: str,
    success: bool = False,
    attempt_count: int = 0,
    admin_name: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> None:
    """
    记录密码找回相关事件到日志

    Args:
        username: 用户名
        event_type: 事件类型（request/success/failure/admin_reset）
        success: 是否成功
        attempt_count: 尝试次数
        admin_name: 管理员名称（如果是管理员操作）
        ip_address: IP地址
    """
    if not ip_address:
        ip_address = "unknown"

    async with AsyncSessionLocal() as session:
        log_entry = PasswordRecoveryLog(
            username=username,
            ip_address=ip_address,
            event_type=event_type,
            success=1 if success else 0,
            attempt_count=attempt_count,
            admin_name=admin_name,
            created_at=int(time.time()),
        )
        session.add(log_entry)
        await session.commit()

    log_msg = (
        f"密码找回事件 - 用户: {username}, 类型: {event_type}, "
        f"成功: {success}, 尝试次数: {attempt_count}, IP: {ip_address}"
    )
    if admin_name:
        log_msg += f", 管理员: {admin_name}"

    if success:
        logger.info(log_msg)
    else:
        logger.warning(log_msg)


async def get_user_security_questions(username: str) -> Optional[Dict[str, Any]]:
    """
    获取用户的安全问题

    Args:
        username: 用户名

    Returns:
        包含安全问题的字典，如果用户不存在或未设置安全问题则返回None
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()

        if not user:
            return None

        reset_locked_until = user.reset_locked_until
        reset_attempt_count = user.reset_attempt_count or 0

        if reset_locked_until is not None:
            try:
                reset_locked_until = float(reset_locked_until)
            except (TypeError, ValueError):
                reset_locked_until = None

        if not user.security_q1:
            return {
                "has_questions": False,
                "reset_locked_until": reset_locked_until,
                "reset_attempt_count": reset_attempt_count,
            }

        current_time = time.time()
        is_locked = False
        if reset_locked_until:
            if current_time < reset_locked_until:
                is_locked = True
            else:
                # 锁定已过期，清除锁定状态
                user.reset_locked_until = None
                user.reset_attempt_count = 0
                await session.commit()
                reset_locked_until = None
                reset_attempt_count = 0

        return {
            "has_questions": True,
            "security_q1": user.security_q1,
            "is_locked": is_locked,
            "reset_locked_until": reset_locked_until,
            "reset_attempt_count": reset_attempt_count,
            "locked_until": datetime.fromtimestamp(reset_locked_until).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            if reset_locked_until
            else None,
        }


async def verify_security_answers(
    username: str, answer: str
) -> tuple[bool, str]:
    """
    校验单个安全问题答案

    Args:
        username: 用户名
        answer: 答案

    Returns:
        tuple: (是否验证成功, 错误信息)
    """
    is_valid, error_msg = validate_security_answers(answer)
    if not is_valid:
        return False, error_msg

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()

        if not user:
            await log_password_recovery_event(username, "failure", False, 0)
            return False, "用户不存在"

        if not user.security_a1:
            return False, "用户未设置安全问题"

        current_time = time.time()
        reset_locked_until = user.reset_locked_until
        if reset_locked_until and current_time < float(reset_locked_until):
            locked_until = datetime.fromtimestamp(float(reset_locked_until)).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            return False, (
                f"账号已被锁定，请于 {locked_until} 后重试。或联系管理员解锁。"
            )

        answer_lower = answer.strip().lower()

        try:
            a_valid = bcrypt.checkpw(
                answer_lower.encode("utf-8"), user.security_a1.encode("utf-8")
            )
        except Exception as e:
            logger.error(f"验证答案时出错: {e}")
            return False, "验证过程出错，请重试"

        attempt_count = user.reset_attempt_count or 0

        if a_valid:
            user.reset_attempt_count = 0
            user.reset_locked_until = None
            user.reset_last_attempt = current_time
            await session.commit()
            await log_password_recovery_event(username, "success", True, attempt_count)
            return True, "验证成功"
        else:
            new_attempt_count = attempt_count + 1
            new_locked_until = None

            if new_attempt_count >= MAX_RESET_ATTEMPTS:
                new_locked_until = current_time + RESET_LOCK_DURATION
                locked_until_str = datetime.fromtimestamp(new_locked_until).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                err = (
                    f"安全验证失败（{new_attempt_count}/{MAX_RESET_ATTEMPTS}次），"
                    f"账号已锁定至 {locked_until_str}。"
                    "请稍后重试或联系管理员解锁。"
                )
            else:
                err = (
                    f"安全验证失败（{new_attempt_count}/{MAX_RESET_ATTEMPTS}次），"
                    "请重新输入。"
                )

            user.reset_attempt_count = new_attempt_count
            user.reset_locked_until = new_locked_until
            user.reset_last_attempt = current_time
            await session.commit()
            await log_password_recovery_event(
                username, "failure", False, new_attempt_count
            )
            return False, err


async def reset_password(username: str, new_password: str) -> tuple[bool, str]:
    """
    重置用户密码

    Args:
        username: 用户名
        new_password: 新密码

    Returns:
        tuple: (是否成功, 错误信息)
    """
    pwd_result = validate_password_strength(new_password)
    if not pwd_result.get("is_valid", False):
        errors = pwd_result.get("errors", [])
        return False, f"密码强度不够：{', '.join(errors)}"

    hashed_password = hash_password(new_password)

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()
        if not user:
            return False, "用户不存在"

        user.password = hashed_password
        user.reset_attempt_count = 0
        user.reset_locked_until = None
        await session.commit()

    await log_password_recovery_event(username, "password_reset", True, 0)
    return True, "密码重置成功"


async def unlock_user(username: str, admin_name: str) -> tuple[bool, str]:
    """
    管理员解锁用户

    Args:
        username: 用户名
        admin_name: 管理员名称

    Returns:
        tuple: (是否成功, 错误信息)
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()
        if not user:
            return False, "用户不存在"

        user.reset_locked_until = None
        user.reset_attempt_count = 0
        await session.commit()

    await log_password_recovery_event(username, "admin_unlock", True, 0, admin_name)
    return True, "用户已解锁"


async def admin_reset_password(
    username: str, new_password: str, admin_name: str
) -> tuple[bool, str]:
    """
    管理员重置用户密码

    Args:
        username: 用户名
        new_password: 新密码
        admin_name: 管理员名称

    Returns:
        tuple: (是否成功, 错误信息)
    """
    pwd_result = validate_password_strength(new_password)
    if not pwd_result.get("is_valid", False):
        errors = pwd_result.get("errors", [])
        return False, f"密码强度不够：{', '.join(errors)}"

    hashed_password = hash_password(new_password)

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()
        if not user:
            return False, "用户不存在"

        user.password = hashed_password
        user.reset_attempt_count = 0
        user.reset_locked_until = None
        await session.commit()

    await log_password_recovery_event(username, "admin_reset", True, 0, admin_name)
    return True, "密码已重置"


async def get_password_recovery_logs(
    username: Optional[str] = None, limit: int = 10
) -> list:
    """
    获取密码找回日志

    Args:
        username: 用户名（可选，如果提供则只查询该用户的日志）
        limit: 返回的记录数限制

    Returns:
        日志记录列表
    """
    async with AsyncSessionLocal() as session:
        query = (
            select(PasswordRecoveryLog)
            .order_by(PasswordRecoveryLog.created_at.desc())
            .limit(limit)
        )
        if username:
            query = query.where(PasswordRecoveryLog.username == username)

        result = await session.execute(query)
        rows = result.scalars().all()

        logs = []
        for row in rows:
            logs.append(
                {
                    "username": row.username,
                    "ip_address": row.ip_address,
                    "event_type": row.event_type,
                    "success": bool(row.success),
                    "attempt_count": row.attempt_count,
                    "admin_name": row.admin_name,
                    "created_at": (
                        datetime.fromtimestamp(row.created_at).strftime(
                            "%Y-%m-%d %H:%M:%S"
                        )
                        if row.created_at is not None
                        else ""
                    ),
                }
            )
        return logs
