"""ORM-declared hot-path indexes mirrored by Wave E Alembic migration."""

from sqlalchemy import Index, text

from models.logistics import Logistics
from models.log import WechatNotifyAuditLog
from models.order import PaymentOrder
from models.session import ActiveSession

Index("ix_logistics_user_id_id_desc", Logistics.user_id, Logistics.id.desc())
Index(
    "ix_payment_orders_user_status_created_at_desc",
    PaymentOrder.user_id,
    PaymentOrder.status,
    PaymentOrder.created_at.desc(),
)
Index(
    "ix_active_sessions_user_active_last_activity",
    ActiveSession.user_id,
    ActiveSession.is_active,
    ActiveSession.last_activity,
)
Index(
    "ix_wechat_notify_audit_logs_bad_sig_created_at_desc",
    WechatNotifyAuditLog.created_at.desc(),
    postgresql_where=text("signature_verified = false"),
)
Index(
    "ix_wechat_notify_audit_logs_created_at_transaction_id",
    WechatNotifyAuditLog.created_at.desc(),
    WechatNotifyAuditLog.transaction_id,
)
