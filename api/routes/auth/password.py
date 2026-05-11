from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from api.dependencies import get_current_user_id
from api.models.schemas import (
    ChangePassword,
    MessageResponse,
    PasswordRecoveryResetRequest,
    PasswordRecoveryStartRequest,
    PasswordRecoveryStartResponse,
    PasswordRecoveryVerifyRequest,
    PasswordRecoveryVerifyResponse,
)
from api.middleware.username_check_limiter import UsernameCheckRateLimiter
from api.routes.auth_recovery import (
    reset_password_with_token,
    start_password_recovery,
    verify_password_recovery,
)
from logger_config import logger

from ._router import router
from .helpers import (
    get_request_ip,
    get_username_check_client_ip,
    auth_module,
    validate_password,
)


recover_start_limiter = UsernameCheckRateLimiter(max_requests=5, window_seconds=60)
recover_verify_limiter = UsernameCheckRateLimiter(max_requests=5, window_seconds=60)


@router.post("/recover/start", response_model=PasswordRecoveryStartResponse)
async def recover_start(
    payload: PasswordRecoveryStartRequest,
    request: Request,
):
    client_ip = get_username_check_client_ip(request)
    recover_start_limiter.check(client_ip)
    return await start_password_recovery(payload.username, client_ip)


@router.post("/recover/verify", response_model=PasswordRecoveryVerifyResponse)
async def recover_verify(
    payload: PasswordRecoveryVerifyRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
):
    client_ip = get_username_check_client_ip(request)
    recover_verify_limiter.check(client_ip)
    reset_token = await verify_password_recovery(
        session=session,
        username=payload.username,
        answer=payload.answer,
        client_ip=client_ip,
    )
    return {"reset_token": reset_token}


@router.post("/recover/reset", response_model=MessageResponse)
async def recover_reset(
    payload: PasswordRecoveryResetRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
):
    message = await reset_password_with_token(
        session=session,
        reset_token=payload.reset_token,
        new_password=payload.new_password,
        client_ip=get_request_ip(request),
    )
    return MessageResponse(message=message)


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    data: ChangePassword,
    request: Request,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    if not validate_password(data.new_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="密码必须至少13位，包含大小写字母、数字和特殊字符",
        )

    auth = auth_module()
    existing_user = await auth.get_user_by_id(session, user_id)
    if not existing_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="认证已失效",
        )

    success = await auth.update_user_password(
        session,
        user_id,
        data.current_password,
        data.new_password,
    )
    client_ip = get_request_ip(request)
    if not success:
        logger.warning(
            "auth.change_password.failed user_id=%s ip=%s",
            user_id,
            client_ip,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="当前密码错误",
        )

    logger.info(
        "auth.change_password.success user_id=%s ip=%s",
        user_id,
        client_ip,
    )
    return MessageResponse(message="密码修改成功")
