"""Authentication route package.

The re-exported names below preserve the historic `api.routes.auth` patch/import
surface used by tests and external callers while endpoint implementations live
in focused submodules.
"""

from importlib import import_module
import secrets

from ._router import router
from .helpers import validate_password
from .password import recover_start_limiter, recover_verify_limiter
from db.config import is_registration_open
from db.sessions_crud import (
    deactivate_all_sessions,
    deactivate_session,
    insert_session,
)
from db.subscriptions import reset_user_daily_calculations
from db.users import (
    create_user,
    find_by_username,
    get_user_by_id,
    update_user_password,
    verify_user,
)
from security.tokens import (
    TokenExpiredError,
    TokenInvalidError,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
)
from logger_config import logger

import_module(f"{__name__}.login")
import_module(f"{__name__}.me")
import_module(f"{__name__}.password")
import_module(f"{__name__}.refresh")


__all__ = [
    "TokenExpiredError",
    "TokenInvalidError",
    "create_access_token",
    "create_refresh_token",
    "create_user",
    "deactivate_all_sessions",
    "deactivate_session",
    "decode_refresh_token",
    "find_by_username",
    "get_user_by_id",
    "insert_session",
    "is_registration_open",
    "logger",
    "recover_start_limiter",
    "recover_verify_limiter",
    "reset_user_daily_calculations",
    "router",
    "secrets",
    "update_user_password",
    "validate_password",
    "verify_user",
]
