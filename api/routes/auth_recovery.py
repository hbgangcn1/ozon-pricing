import bcrypt
from inspect import isawaitable

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from db.users import find_by_username, get_user_by_id
from models.user import User
from password_recovery import (
    get_user_security_questions,
    log_password_recovery_event,
    reset_password,
    verify_security_answers,
)
from services.password_reset_service import (
    create_reset_token,
    purge_user_reset_tokens,
    validate_and_consume_reset_token,
)
from session_security import SessionSecurity

GENERIC_RECOVERY_MESSAGE = "如该账号存在且已设置安全问题，将引导您回答安全问题"
GENERIC_VERIFY_ERROR = "验证失败，请检查您的回答"
INVALID_RESET_TOKEN_ERROR = "令牌无效或已过期"
INVALID_PASSWORD_ERROR = "密码不符合要求"
PLACEHOLDER_QUESTIONS = ["（保密）", "（保密）"]
_DUMMY_HASH = (
    "$2b$12$2Qx.E30paHj2a2iZNpNoEub3PgFotifT0s.S8fCytaQB9D1yuJAmy"
)


def _run_dummy_bcrypt_checks() -> None:
    bcrypt.checkpw(b"dummy-answer", _DUMMY_HASH.encode("utf-8"))
    bcrypt.checkpw(b"dummy-answer", _DUMMY_HASH.encode("utf-8"))


async def start_password_recovery(username: str, client_ip: str) -> dict:
    user = await get_user_security_questions(username)
    questions = PLACEHOLDER_QUESTIONS
    success = False
    if user and user.get("has_questions"):
        questions = [user["security_q1"], user["security_q2"]]
        success = True
    else:
        _run_dummy_bcrypt_checks()
    await log_password_recovery_event(
        username=username,
        event_type="recover_start",
        success=success,
        ip_address=client_ip,
    )
    return {
        "message": GENERIC_RECOVERY_MESSAGE,
        "questions": questions,
    }


async def verify_password_recovery(
    session: AsyncSession,
    username: str,
    answer1: str,
    answer2: str,
    client_ip: str,
) -> str:
    user = await find_by_username(session, username)
    if isawaitable(user):
        user = await user
    if not isinstance(user, User) or not user.security_a1 or not user.security_a2:
        _run_dummy_bcrypt_checks()
        await log_password_recovery_event(
            username=username,
            event_type="recover_verify",
            success=False,
            ip_address=client_ip,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=GENERIC_VERIFY_ERROR,
        )

    verified, _ = await verify_security_answers(username, answer1, answer2)
    if not verified:
        await log_password_recovery_event(
            username=username,
            event_type="recover_verify",
            success=False,
            ip_address=client_ip,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=GENERIC_VERIFY_ERROR,
        )

    token = await create_reset_token(user.id)
    await log_password_recovery_event(
        username=username,
        event_type="recover_verify",
        success=True,
        ip_address=client_ip,
    )
    return token


async def reset_password_with_token(
    session: AsyncSession,
    reset_token: str,
    new_password: str,
    client_ip: str,
) -> str:
    valid, user_id, _ = await validate_and_consume_reset_token(reset_token)
    if not valid or user_id is None:
        await log_password_recovery_event(
            username="unknown",
            event_type="recover_reset",
            success=False,
            ip_address=client_ip,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=INVALID_RESET_TOKEN_ERROR,
        )

    user = await get_user_by_id(session, user_id)
    if not user or not user.username:
        await log_password_recovery_event(
            username="unknown",
            event_type="recover_reset",
            success=False,
            ip_address=client_ip,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=INVALID_RESET_TOKEN_ERROR,
        )

    success, message = await reset_password(user.username, new_password)
    if not success:
        await log_password_recovery_event(
            username=user.username,
            event_type="recover_reset",
            success=False,
            ip_address=client_ip,
        )
        detail = INVALID_PASSWORD_ERROR
        if "密码" not in message:
            detail = INVALID_RESET_TOKEN_ERROR
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

    await SessionSecurity.invalidate_user_sessions(user_id)
    await purge_user_reset_tokens(user_id)
    await log_password_recovery_event(
        username=user.username,
        event_type="recover_reset",
        success=True,
        ip_address=client_ip,
    )
    return "密码已重置，请重新登录"
