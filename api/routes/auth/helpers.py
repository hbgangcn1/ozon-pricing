import os
import re
import sys
import time
from types import ModuleType

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_request_ip
from api.routes.auth_support import get_request_user_agent


def auth_module() -> ModuleType:
    package_name = __package__ or "api.routes.auth"
    return sys.modules[package_name]


def validate_password(password: str) -> bool:
    if len(password) < 13:
        return False
    if not re.search(r"[a-z]", password):
        return False
    if not re.search(r"[A-Z]", password):
        return False
    if not re.search(r"\d", password):
        return False
    if not re.search(r"[^a-zA-Z0-9]", password):
        return False
    return True


def get_username_check_client_ip(request: Request) -> str:
    return get_request_ip(request)


async def issue_auth_tokens(
    session: AsyncSession,
    request: Request,
    user_id: int,
    username: str,
    role: str,
) -> tuple[str, str]:
    auth = auth_module()
    sid = auth.secrets.token_urlsafe(32)
    now = time.time()
    await auth.insert_session(
        session,
        session_id=sid,
        user_id=user_id,
        ip_address=get_request_ip(request),
        user_agent=get_request_user_agent(request.headers.get("user-agent")),
        now=now,
    )
    # E2E 测试守护 gate：仅当显式同时设置两个 env 时跳过 kick-by-new-login。
    # 默认（含生产、开发、单元/集成测试）保持原有的 deactivate_all_sessions
    # 真实安全语义。Playwright 套件需要并行/跨 spec 共享同一个 admin
    # session，否则后续每次 apiLogin(admin) 都会踢掉 storageState 里的会话
    # 导致大面积 401 + SessionKickedDialog。详见 plan v5 R-W14-C0-line25-arch。
    if not _kick_by_new_login_disabled():
        await auth.deactivate_all_sessions(
            session,
            user_id,
            exclude_session_id=sid,
            reason="kicked_by_new_login",
        )
    access_token = auth.create_access_token(
        user_id=user_id,
        username=username,
        role=role,
        extra_claims={"sid": sid},
    )
    refresh_token = auth.create_refresh_token(user_id=user_id, sid=sid)
    return access_token, refresh_token


def _kick_by_new_login_disabled() -> bool:
    """
    返回 True 当且仅当 E2E 双 env 同时为 '1'。
    任一 env 缺失或非 '1' 都返回 False（保持生产/默认 kick 行为）。
    分两个 env 是为了"显式 opt-in"——单独 E2E_TEST=1 不足以禁用 kick，
    必须再叠加 E2E_DISABLE_NEW_LOGIN_SESSION_KICK=1。
    """
    return (
        os.environ.get("E2E_TEST") == "1"
        and os.environ.get("E2E_DISABLE_NEW_LOGIN_SESSION_KICK") == "1"
    )
