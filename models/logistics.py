from decimal import Decimal
from typing import Optional
from sqlalchemy import CheckConstraint, String, Integer, Float, Numeric, text
from sqlalchemy.orm import Mapped, mapped_column
from models import Base


class Logistics(Base):
    __tablename__ = "logistics"
    __table_args__ = (
        CheckConstraint(
            "volume_mode IN ('none', 'max_actual_vs_volume', 'longest_side', 'sum_of_sides')",
            name="logistics_volume_mode_check",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    name: Mapped[Optional[str]] = mapped_column(String)
    type: Mapped[Optional[str]] = mapped_column(String)
    min_days: Mapped[Optional[int]] = mapped_column(Integer)
    max_days: Mapped[Optional[int]] = mapped_column(Integer)
    price_limit: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4))
    price_limit_rub: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4))
    price_min: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 4),
        server_default=text("0"),
    )
    price_min_rub: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 4),
        server_default=text("0"),
    )
    price_limit_cny: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 4),
        server_default=text("0"),
    )
    price_min_cny: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 4),
        server_default=text("0"),
    )
    base_fee: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 4),
        server_default=text("0"),
    )
    min_weight: Mapped[Optional[int]] = mapped_column(Integer)
    max_weight: Mapped[Optional[int]] = mapped_column(Integer)
    max_sum_of_sides: Mapped[Optional[int]] = mapped_column(Integer)
    max_longest_side: Mapped[Optional[int]] = mapped_column(Integer)
    max_second_side: Mapped[Optional[int]] = mapped_column(
        Integer,
        server_default=text("0"),
    )
    max_third_side: Mapped[Optional[int]] = mapped_column(
        Integer,
        server_default=text("0"),
    )
    min_second_side: Mapped[Optional[int]] = mapped_column(
        Integer,
        server_default=text("0"),
    )
    min_length: Mapped[Optional[int]] = mapped_column(
        Integer,
        server_default=text("0"),
    )
    max_cylinder_sum: Mapped[Optional[int]] = mapped_column(
        Integer,
        server_default=text("0"),
    )
    min_cylinder_sum: Mapped[Optional[int]] = mapped_column(
        Integer,
        server_default=text("0"),
    )
    max_cylinder_length: Mapped[Optional[int]] = mapped_column(
        Integer,
        server_default=text("0"),
    )
    min_cylinder_length: Mapped[Optional[int]] = mapped_column(
        Integer,
        server_default=text("0"),
    )
    volume_mode: Mapped[Optional[str]] = mapped_column(
        String,
        server_default=text("'none'"),
    )
    longest_side_threshold: Mapped[Optional[int]] = mapped_column(
        Integer,
        server_default=text("0"),
    )
    sum_of_sides_threshold: Mapped[Optional[int]] = mapped_column(
        Integer,
        server_default=text("0"),
    )
    allow_battery: Mapped[Optional[int]] = mapped_column(Integer)
    allow_liquid: Mapped[Optional[int]] = mapped_column(Integer)
    battery_capacity_limit_wh: Mapped[Optional[float]] = mapped_column(
        Float,
        server_default=text("0"),
    )
    require_msds: Mapped[Optional[int]] = mapped_column(
        Integer,
        server_default=text("0"),
    )
    fee_mode: Mapped[Optional[str]] = mapped_column(
        String,
        server_default=text("'base_plus_continue'"),
    )
    first_fee: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 4),
        server_default=text("0"),
    )
    first_weight_g: Mapped[Optional[int]] = mapped_column(
        Integer,
        server_default=text("0"),
    )
    continue_fee: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 4),
        server_default=text("0"),
    )
    continue_unit: Mapped[Optional[str]] = mapped_column(
        String,
        server_default=text("'100'"),
    )
    volume_coefficient: Mapped[Optional[float]] = mapped_column(
        Float,
        server_default=text("5000"),
    )
    delivery_method: Mapped[Optional[str]] = mapped_column(
        String,
        server_default=text("'unknown'"),
    )
    priority_group: Mapped[Optional[str]] = mapped_column(
        String,
        server_default=text("'D'"),
    )
    price_limit_currency: Mapped[Optional[str]] = mapped_column(
        String,
        server_default=text("'RUB'"),
    )
    price_min_currency: Mapped[Optional[str]] = mapped_column(
        String,
        server_default=text("'RUB'"),
    )
    fulfillment_type: Mapped[Optional[str]] = mapped_column(
        String,
        server_default=text("'rfbs'"),
    )
    destination: Mapped[Optional[str]] = mapped_column(
        String,
        server_default=text("'RU'"),
    )
    fbp_service_level: Mapped[Optional[str]] = mapped_column(String)
    fbp_company: Mapped[Optional[str]] = mapped_column(String)
    is_smart: Mapped[Optional[int]] = mapped_column(
        Integer,
        server_default=text("0"),
    )
    scoring_group: Mapped[Optional[str]] = mapped_column(String)
    is_active: Mapped[Optional[int]] = mapped_column(
        Integer,
        server_default=text("1"),
    )
    disabled_by_overflow: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    last_used_at: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    updated_at: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("date_part('epoch'::text, now())"),
    )
