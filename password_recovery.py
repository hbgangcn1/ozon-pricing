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

try:
    from .db_utils import get_db_connection, hash_password
    from .security_questions import validate_security_answers
except ImportError:
    from db_utils import get_db_connection, hash_password
    from security_questions import validate_security_answers

# 配置日志
logger = logging.getLogger(__name__)

# 密码找回配置
MAX_RESET_ATTEMPTS = 3  # 最大尝试次数
RESET_LOCK_DURATION = 1800  # 锁定时长（秒），30分钟


def log_password_recovery_event(
    username: str,
    event_type: str,
    success: bool = False,
    attempt_count: int = 0,
    admin_name: Optional[str] = None,
    ip_address: Optional[str] = None
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
    try:
        from .session_security import SessionSecurity
    except ImportError:
        from session_security import SessionSecurity

    if not ip_address:
        client_info = SessionSecurity.get_client_info()
        ip_address = client_info.get('ip_address', 'unknown')

    with get_db_connection() as (conn, c):
        c.execute("""
            INSERT INTO password_recovery_log
            (username, ip_address, event_type, success, attempt_count,
             admin_name, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            username, ip_address, event_type, 1 if success else 0,
            attempt_count, admin_name, int(time.time())
        ))
        conn.commit()

    # 同时写入应用日志
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


def get_user_security_questions(username: str) -> Optional[Dict[str, Any]]:
    """
    获取用户的安全问题

    Args:
        username: 用户名

    Returns:
        包含安全问题的字典，如果用户不存在或未设置安全问题则返回None
    """
    with get_db_connection() as (conn, c):
        c.execute("""
            SELECT security_q1, security_q2, reset_locked_until,
                   reset_attempt_count
            FROM users
            WHERE username = ?
        """, (username,))
        result = c.fetchone()

        if not result:
            return None

        security_q1, security_q2, reset_locked_until, reset_attempt_count = (
            result
        )

        # 检查是否设置了安全问题
        if not security_q1 or not security_q2:
            return {
                'has_questions': False,
                'reset_locked_until': reset_locked_until,
                'reset_attempt_count': reset_attempt_count or 0
            }

        # 检查是否被锁定
        current_time = time.time()
        is_locked = False
        if reset_locked_until:
            if current_time < reset_locked_until:
                is_locked = True
            else:
                # 锁定已过期，清除锁定状态
                c.execute("""
                    UPDATE users
                    SET reset_locked_until = NULL,
                        reset_attempt_count = 0
                    WHERE username = ?
                """, (username,))
                conn.commit()
                reset_locked_until = None
                reset_attempt_count = 0

        return {
            'has_questions': True,
            'security_q1': security_q1,
            'security_q2': security_q2,
            'is_locked': is_locked,
            'reset_locked_until': reset_locked_until,
            'reset_attempt_count': reset_attempt_count or 0,
            'locked_until': datetime.fromtimestamp(
                reset_locked_until
            ).strftime('%Y-%m-%d %H:%M:%S') if reset_locked_until else None
        }


def verify_security_answers(
    username: str,
    answer1: str,
    answer2: str
) -> tuple[bool, str]:
    """
    验证安全问题的答案

    Args:
        username: 用户名
        answer1: 答案1
        answer2: 答案2

    Returns:
        tuple: (是否验证成功, 错误信息)
    """
    # 验证答案格式
    is_valid, error_msg = validate_security_answers(answer1, answer2)
    if not is_valid:
        return False, error_msg

    with get_db_connection() as (conn, c):
        # 获取用户的安全答案哈希
        c.execute("""
            SELECT security_a1, security_a2, reset_locked_until,
                   reset_attempt_count
            FROM users
            WHERE username = ?
        """, (username,))
        result = c.fetchone()

        if not result:
            log_password_recovery_event(
                username, 'failure', False, 0
            )
            return False, "用户不存在"

        security_a1_hash, security_a2_hash, reset_locked_until, \
            attempt_count = result

        if not security_a1_hash or not security_a2_hash:
            return False, "用户未设置安全问题"

        # 检查是否被锁定
        current_time = time.time()
        if reset_locked_until and current_time < reset_locked_until:
            locked_until = datetime.fromtimestamp(
                reset_locked_until
            ).strftime('%Y-%m-%d %H:%M:%S')
            return False, (
                f"账号已被锁定，请于 {locked_until} 后重试。"
                "或联系管理员解锁。"
            )

        # 验证答案（不区分大小写）
        answer1_lower = answer1.strip().lower()
        answer2_lower = answer2.strip().lower()

        # 使用bcrypt验证答案
        try:
            a1_valid = bcrypt.checkpw(
                answer1_lower.encode('utf-8'),
                security_a1_hash.encode('utf-8')
            )
            a2_valid = bcrypt.checkpw(
                answer2_lower.encode('utf-8'),
                security_a2_hash.encode('utf-8')
            )
        except Exception as e:
            logger.error(f"验证答案时出错: {e}")
            return False, "验证过程出错，请重试"

        if a1_valid and a2_valid:
            # 验证成功，重置尝试次数
            c.execute("""
                UPDATE users
                SET reset_attempt_count = 0,
                    reset_locked_until = NULL,
                    reset_last_attempt = ?
                WHERE username = ?
            """, (current_time, username))
            conn.commit()

            log_password_recovery_event(
                username, 'success', True, attempt_count or 0
            )
            return True, "验证成功"
        else:
            # 验证失败，增加尝试次数
            new_attempt_count = (attempt_count or 0) + 1
            reset_locked_until = None

            # 如果达到最大尝试次数，锁定账号
            if new_attempt_count >= MAX_RESET_ATTEMPTS:
                reset_locked_until = current_time + RESET_LOCK_DURATION
                locked_until = datetime.fromtimestamp(
                    reset_locked_until
                ).strftime('%Y-%m-%d %H:%M:%S')
                error_msg = (
                    f"安全验证失败（{new_attempt_count}/{MAX_RESET_ATTEMPTS}次），"
                    f"账号已锁定至 {locked_until}。"
                    "请稍后重试或联系管理员解锁。"
                )
            else:
                error_msg = (
                    f"安全验证失败（{new_attempt_count}/{MAX_RESET_ATTEMPTS}次），"
                    "请重新输入。"
                )

            c.execute("""
                UPDATE users
                SET reset_attempt_count = ?,
                    reset_locked_until = ?,
                    reset_last_attempt = ?
                WHERE username = ?
            """, (
                new_attempt_count, reset_locked_until, current_time, username
            ))
            conn.commit()

            log_password_recovery_event(
                username, 'failure', False, new_attempt_count
            )
            return False, error_msg


def reset_password(
    username: str,
    new_password: str
) -> tuple[bool, str]:
    """
    重置用户密码

    Args:
        username: 用户名
        new_password: 新密码

    Returns:
        tuple: (是否成功, 错误信息)
    """
    # 验证密码强度
    try:
        from .password_utils import validate_password_strength
    except ImportError:
        from password_utils import validate_password_strength

    pwd_result = validate_password_strength(new_password)
    if not pwd_result.get('is_valid', False):
        errors = pwd_result.get('errors', [])
        return False, f"密码强度不够：{', '.join(errors)}"

    # 加密新密码
    hashed_password = hash_password(new_password)

    with get_db_connection() as (conn, c):
        # 检查用户是否存在
        c.execute("SELECT id FROM users WHERE username = ?", (username,))
        if not c.fetchone():
            return False, "用户不存在"

        # 更新密码
        c.execute("""
            UPDATE users
            SET password = ?,
                reset_attempt_count = 0,
                reset_locked_until = NULL
            WHERE username = ?
        """, (hashed_password, username))
        conn.commit()

    log_password_recovery_event(username, 'password_reset', True, 0)
    return True, "密码重置成功"


def unlock_user(username: str, admin_name: str) -> tuple[bool, str]:
    """
    管理员解锁用户

    Args:
        username: 用户名
        admin_name: 管理员名称

    Returns:
        tuple: (是否成功, 错误信息)
    """
    with get_db_connection() as (conn, c):
        # 检查用户是否存在
        c.execute("SELECT id FROM users WHERE username = ?", (username,))
        if not c.fetchone():
            return False, "用户不存在"

        # 解锁用户
        c.execute("""
            UPDATE users
            SET reset_locked_until = NULL,
                reset_attempt_count = 0
            WHERE username = ?
        """, (username,))
        conn.commit()

    log_password_recovery_event(
        username, 'admin_unlock', True, 0, admin_name
    )
    return True, "用户已解锁"


def admin_reset_password(
    username: str,
    new_password: str,
    admin_name: str
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
    # 验证密码强度
    try:
        from .password_utils import validate_password_strength
    except ImportError:
        from password_utils import validate_password_strength

    pwd_result = validate_password_strength(new_password)
    if not pwd_result.get('is_valid', False):
        errors = pwd_result.get('errors', [])
        return False, f"密码强度不够：{', '.join(errors)}"

    # 加密新密码
    hashed_password = hash_password(new_password)

    with get_db_connection() as (conn, c):
        # 检查用户是否存在
        c.execute("SELECT id FROM users WHERE username = ?", (username,))
        if not c.fetchone():
            return False, "用户不存在"

        # 更新密码并清除锁定状态
        c.execute("""
            UPDATE users
            SET password = ?,
                reset_attempt_count = 0,
                reset_locked_until = NULL
            WHERE username = ?
        """, (hashed_password, username))
        conn.commit()

    log_password_recovery_event(
        username, 'admin_reset', True, 0, admin_name
    )
    return True, "密码已重置"


def get_password_recovery_logs(
    username: Optional[str] = None,
    limit: int = 10
) -> list:
    """
    获取密码找回日志

    Args:
        username: 用户名（可选，如果提供则只查询该用户的日志）
        limit: 返回的记录数限制

    Returns:
        日志记录列表
    """
    with get_db_connection() as (conn, c):
        if username:
            c.execute("""
                SELECT username, ip_address, event_type, success,
                       attempt_count, admin_name, created_at
                FROM password_recovery_log
                WHERE username = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (username, limit))
        else:
            c.execute("""
                SELECT username, ip_address, event_type, success,
                       attempt_count, admin_name, created_at
                FROM password_recovery_log
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))

        results = c.fetchall()
        logs = []
        for row in results:
            logs.append({
                'username': row[0],
                'ip_address': row[1],
                'event_type': row[2],
                'success': bool(row[3]),
                'attempt_count': row[4],
                'admin_name': row[5],
                'created_at': datetime.fromtimestamp(row[6]).strftime(
                    '%Y-%m-%d %H:%M:%S'
                )
            })
        return logs
