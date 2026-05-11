from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# 导入所有模型，确保 Base.metadata 包含全部表
from models.user import User, Plan, SubscriptionUpgradeHistory  # noqa: E402, F401
from models.product import Product  # noqa: E402, F401
from models.logistics import Logistics  # noqa: E402, F401
from models.commission_category import CommissionCategory  # noqa: E402, F401
from models.logistics_pool import LogisticsPool  # noqa: E402, F401
from models.order import PaymentOrder  # noqa: E402, F401
from models.config import SystemConfig, ExchangeRate  # noqa: E402, F401
from models.session import (  # noqa: E402, F401
    ActiveSession,
    LoginAttempt,
    UserLockout,
    TrustedDevice,
)
from models.log import (  # noqa: E402, F401
    UserLoginLog,
    UserBehaviorLog,
    AdminActionLog,
    AlertRecord,
    AlertConfig,
    PasswordRecoveryLog,
    AuditLog,
    WechatNotifyAuditLog,
)
from models.cache import StatisticsCache  # noqa: E402, F401
from models.password_reset_token import PasswordResetToken  # noqa: E402, F401
from models.trial_overflow_window import TrialOverflowWindow  # noqa: E402, F401

__all__ = [
    "Base",
    "User",
    "Plan",
    "SubscriptionUpgradeHistory",
    "Product",
    "Logistics",
    "CommissionCategory",
    "LogisticsPool",
    "PaymentOrder",
    "SystemConfig",
    "ExchangeRate",
    "ActiveSession",
    "LoginAttempt",
    "UserLockout",
    "TrustedDevice",
    "UserLoginLog",
    "UserBehaviorLog",
    "AdminActionLog",
    "AlertRecord",
    "AlertConfig",
    "PasswordRecoveryLog",
    "AuditLog",
    "WechatNotifyAuditLog",
    "StatisticsCache",
    "PasswordResetToken",
    "TrialOverflowWindow",
]
