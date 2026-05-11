from typing import Optional
from datetime import datetime
from sqlalchemy import String, Integer, Float, DateTime, Boolean, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column
from models import Base


class UserLoginLog(Base):
    __tablename__ = "user_login_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    login_time: Mapped[int] = mapped_column(Integer, nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String)
    user_agent: Mapped[Optional[str]] = mapped_column(String)
    device_type: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[Optional[int]] = mapped_column(
        Integer,
        server_default=text("date_part('epoch'::text, now())"),
    )


class UserBehaviorLog(Base):
    __tablename__ = "user_behavior_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    behavior_type: Mapped[str] = mapped_column(String, nullable=False)
    behavior_detail: Mapped[Optional[str]] = mapped_column(String)
    calculation_mode: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[Optional[int]] = mapped_column(
        Integer,
        server_default=text("date_part('epoch'::text, now())"),
    )


class AdminActionLog(Base):
    __tablename__ = "admin_action_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    admin_id: Mapped[int] = mapped_column(Integer, nullable=False)
    action_type: Mapped[str] = mapped_column(String, nullable=False)
    action_detail: Mapped[Optional[str]] = mapped_column(String)
    target_user_id: Mapped[Optional[int]] = mapped_column(Integer)
    target_type: Mapped[Optional[str]] = mapped_column(String)
    ip_address: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[Optional[int]] = mapped_column(
        Integer,
        server_default=text("date_part('epoch'::text, now())"),
    )


class AlertRecord(Base):
    __tablename__ = "alert_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    alert_type: Mapped[str] = mapped_column(String, nullable=False)
    alert_level: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    threshold_value: Mapped[Optional[float]] = mapped_column(Float)
    actual_value: Mapped[Optional[float]] = mapped_column(Float)
    status: Mapped[Optional[str]] = mapped_column(
        String,
        server_default=text("'unhandled'"),
    )
    handled_by: Mapped[Optional[int]] = mapped_column(Integer)
    handled_at: Mapped[Optional[int]] = mapped_column(Integer)
    handle_note: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[Optional[int]] = mapped_column(
        Integer,
        server_default=text("date_part('epoch'::text, now())"),
    )


class AlertConfig(Base):
    __tablename__ = "alert_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    metric_name: Mapped[str] = mapped_column(String, nullable=False)
    threshold_value: Mapped[Optional[float]] = mapped_column(Float)
    comparison_type: Mapped[Optional[str]] = mapped_column(String)
    is_enabled: Mapped[Optional[int]] = mapped_column(
        Integer,
        server_default=text("1"),
    )
    notification_method: Mapped[Optional[str]] = mapped_column(
        String,
        server_default=text("'system'"),
    )
    created_at: Mapped[Optional[int]] = mapped_column(
        Integer,
        server_default=text("date_part('epoch'::text, now())"),
    )
    updated_at: Mapped[Optional[int]] = mapped_column(
        Integer,
        server_default=text("date_part('epoch'::text, now())"),
    )


class PasswordRecoveryLog(Base):
    __tablename__ = "password_recovery_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String, nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    success: Mapped[Optional[int]] = mapped_column(
        Integer,
        server_default=text("0"),
    )
    attempt_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        server_default=text("0"),
    )
    admin_name: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[Optional[int]] = mapped_column(
        Integer,
        server_default=text("date_part('epoch'::text, now())"),
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    admin_id: Mapped[int] = mapped_column(Integer, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String, nullable=False)
    details: Mapped[Optional[str]] = mapped_column(String)
    timestamp: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP"),
    )


class WechatNotifyAuditLog(Base):
    __tablename__ = "wechat_notify_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    out_trade_no: Mapped[Optional[str]] = mapped_column(
        String(64),
        index=True,
        nullable=True,
    )
    transaction_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        index=True,
        nullable=True,
    )
    signature_verified: Mapped[bool] = mapped_column(Boolean, nullable=False)
    raw_body: Mapped[str] = mapped_column(Text, nullable=False)
    response_code: Mapped[str] = mapped_column(String(16), nullable=False)
    response_message: Mapped[str] = mapped_column(String(256), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
