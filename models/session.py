from typing import Optional
from sqlalchemy import (
    String,
    Integer,
    Float,
    Boolean,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from models import Base


class ActiveSession(Base):
    __tablename__ = "active_sessions"

    session_id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
    )
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[float] = mapped_column(Float, nullable=False)
    last_activity: Mapped[float] = mapped_column(Float, nullable=False)
    last_rotation: Mapped[Optional[float]] = mapped_column(
        Float,
        server_default=text("0"),
    )
    ip_address: Mapped[Optional[str]] = mapped_column(String)
    user_agent: Mapped[Optional[str]] = mapped_column(String)
    is_active: Mapped[Optional[bool]] = mapped_column(
        Boolean,
        server_default=text("true"),
    )
    inactive_reason: Mapped[Optional[str]] = mapped_column(String(32))
    device_fingerprint: Mapped[Optional[str]] = mapped_column(String)


class LoginAttempt(Base):
    __tablename__ = "login_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    identifier: Mapped[str] = mapped_column(String, nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String)
    timestamp: Mapped[float] = mapped_column(Float, nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    user_agent: Mapped[Optional[str]] = mapped_column(String)


class UserLockout(Base):
    __tablename__ = "user_lockouts"

    identifier: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        unique=True,
    )
    locked_until: Mapped[float] = mapped_column(Float, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False)


class TrustedDevice(Base):
    __tablename__ = "trusted_devices"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "device_fingerprint",
            name="trusted_devices_user_id_device_fingerprint_key",
        ),
        UniqueConstraint(
            "user_id",
            "device_fingerprint",
            name="trusted_devices_user_device_key",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    ip_address: Mapped[str] = mapped_column(String, nullable=False)
    device_fingerprint: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )
    user_agent: Mapped[Optional[str]] = mapped_column(String)
    trusted_at: Mapped[float] = mapped_column(Float, nullable=False)
    last_used: Mapped[float] = mapped_column(Float, nullable=False)
    is_active: Mapped[Optional[bool]] = mapped_column(
        Boolean,
        server_default=text("true"),
    )
