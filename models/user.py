from typing import Optional
from sqlalchemy import String, Integer, Float, text, Index, func
from sqlalchemy.orm import Mapped, mapped_column
from models import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[Optional[str]] = mapped_column(
        String,
        unique=True,
    )
    password: Mapped[Optional[str]] = mapped_column(String)
    role: Mapped[Optional[str]] = mapped_column(String)
    email: Mapped[Optional[str]] = mapped_column(String, unique=True)
    preferred_mode: Mapped[Optional[str]] = mapped_column(
        String,
        server_default=text("'fast'"),
    )
    user_type: Mapped[Optional[str]] = mapped_column(
        String,
        server_default=text("'permanent'"),
    )
    expiry_date: Mapped[Optional[str]] = mapped_column(String)
    remaining_calculations: Mapped[Optional[int]] = mapped_column(
        Integer,
        server_default=text("'-1'"),
    )
    last_calculations_reset_date: Mapped[Optional[str]] = mapped_column(
        String,
        server_default=text("''"),
    )
    first_login_date: Mapped[Optional[str]] = mapped_column(String)
    test_days_remaining: Mapped[Optional[int]] = mapped_column(
        Integer,
        server_default=text("0"),
    )
    subscription_type: Mapped[Optional[str]] = mapped_column(
        String,
        server_default=text("'free'"),
    )
    subscription_expires: Mapped[Optional[int]] = mapped_column(Integer)
    efficiency_promo_used: Mapped[Optional[int]] = mapped_column(
        Integer,
        server_default=text("0"),
    )
    created_at: Mapped[Optional[str]] = mapped_column(
        String,
        server_default=text("''"),
    )
    last_login: Mapped[Optional[str]] = mapped_column(String)
    is_test_user: Mapped[Optional[int]] = mapped_column(
        Integer,
        server_default=text("0"),
    )
    billing_cycle: Mapped[Optional[str]] = mapped_column(
        String,
        server_default=text("'month'"),
    )
    last_paid_amount: Mapped[Optional[float]] = mapped_column(
        Float,
        server_default=text("0"),
    )
    subscription_start: Mapped[Optional[int]] = mapped_column(Integer)
    security_q1: Mapped[Optional[str]] = mapped_column(String)
    security_a1: Mapped[Optional[str]] = mapped_column(String)
    security_q2: Mapped[Optional[str]] = mapped_column(String)
    security_a2: Mapped[Optional[str]] = mapped_column(String)
    reset_locked_until: Mapped[Optional[float]] = mapped_column(Float)
    reset_attempt_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        server_default=text("0"),
    )
    reset_last_attempt: Mapped[Optional[float]] = mapped_column(Float)
    logistics_templates_limit: Mapped[Optional[int]] = mapped_column(
        Integer,
        server_default=text("'-1'"),
    )
    is_auto_renew: Mapped[Optional[int]] = mapped_column(
        Integer,
        server_default=text("0"),
    )
    is_frozen: Mapped[Optional[int]] = mapped_column(
        Integer,
        server_default=text("0"),
    )
    trial_used: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    trial_started_at: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    trial_expires_at: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    trial_plan_at_start: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default=text("''"),
    )

    __table_args__ = (
        Index(
            "ux_users_username_lower",
            func.lower(username),
            unique=True,
        ),
        Index(
            "ux_users_email_lower",
            func.lower(email),
            unique=True,
            postgresql_where=email.isnot(None),
        ),
    )


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_code: Mapped[str] = mapped_column(
        String,
        unique=True,
        nullable=False,
    )
    plan_name: Mapped[str] = mapped_column(String, nullable=False)
    display_price_month: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    display_price_year: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    actual_price_month: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    actual_price_year: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    test_price_month: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        server_default=text("0"),
    )
    test_price_year: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        server_default=text("0"),
    )
    calc_limit: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("'-1'"),
    )
    logistics_limit: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("1"),
    )
    description: Mapped[Optional[str]] = mapped_column(String)
    features: Mapped[Optional[str]] = mapped_column(String)
    is_active: Mapped[Optional[int]] = mapped_column(
        Integer,
        server_default=text("1"),
    )
    sort_order: Mapped[Optional[int]] = mapped_column(
        Integer,
        server_default=text("0"),
    )
    created_at: Mapped[Optional[int]] = mapped_column(
        Integer,
        server_default=text("date_part('epoch'::text, now())"),
    )
    updated_at: Mapped[Optional[int]] = mapped_column(
        Integer,
        server_default=text("date_part('epoch'::text, now())"),
    )


class SubscriptionUpgradeHistory(Base):
    __tablename__ = "subscription_upgrade_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    from_plan: Mapped[str] = mapped_column(String, nullable=False)
    to_plan: Mapped[str] = mapped_column(String, nullable=False)
    from_cycle: Mapped[Optional[str]] = mapped_column(String)
    to_cycle: Mapped[Optional[str]] = mapped_column(String)
    upgrade_time: Mapped[int] = mapped_column(Integer, nullable=False)
    remaining_value: Mapped[Optional[float]] = mapped_column(
        Float,
        server_default=text("0"),
    )
    difference_paid: Mapped[Optional[float]] = mapped_column(
        Float,
        server_default=text("0"),
    )
    target_price: Mapped[float] = mapped_column(Float, nullable=False)
    payment_order_id: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[Optional[int]] = mapped_column(
        Integer,
        server_default=text("date_part('epoch'::text, now())"),
    )
