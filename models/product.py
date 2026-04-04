from typing import Optional
from sqlalchemy import String, Integer, Float, text
from sqlalchemy.orm import Mapped, mapped_column
from models import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String)
    russian_name: Mapped[Optional[str]] = mapped_column(String)
    category: Mapped[Optional[str]] = mapped_column(String)
    model: Mapped[Optional[str]] = mapped_column(String)
    unit_price: Mapped[Optional[float]] = mapped_column(Float)
    weight_g: Mapped[Optional[int]] = mapped_column(Integer)
    length_cm: Mapped[Optional[int]] = mapped_column(Integer)
    width_cm: Mapped[Optional[int]] = mapped_column(Integer)
    height_cm: Mapped[Optional[int]] = mapped_column(Integer)
    is_cylinder: Mapped[Optional[int]] = mapped_column(Integer)
    cylinder_diameter: Mapped[Optional[float]] = mapped_column(Float)
    cylinder_length: Mapped[Optional[float]] = mapped_column(Float)
    has_battery: Mapped[Optional[int]] = mapped_column(Integer)
    battery_capacity_wh: Mapped[Optional[float]] = mapped_column(Float)
    battery_capacity_mah: Mapped[Optional[int]] = mapped_column(Integer)
    battery_voltage: Mapped[Optional[float]] = mapped_column(Float)
    has_msds: Mapped[Optional[int]] = mapped_column(Integer)
    has_liquid: Mapped[Optional[int]] = mapped_column(Integer)
    shipping_fee: Mapped[Optional[float]] = mapped_column(Float)
    labeling_fee: Mapped[Optional[float]] = mapped_column(Float)
    promotion_discount: Mapped[Optional[float]] = mapped_column(
        Float,
        server_default=text("0.05"),
    )
    promotion_cost_rate: Mapped[Optional[float]] = mapped_column(
        Float,
        server_default=text("0.115"),
    )
    target_profit_margin: Mapped[Optional[float]] = mapped_column(
        Float,
        server_default=text("0.5"),
    )
    commission_rate: Mapped[Optional[float]] = mapped_column(
        Float,
        server_default=text("0.17"),
    )
    withdrawal_fee_rate: Mapped[Optional[float]] = mapped_column(
        Float,
        server_default=text("0.01"),
    )
    payment_processing_fee: Mapped[Optional[float]] = mapped_column(
        Float,
        server_default=text("0.01"),
    )
    return_rate: Mapped[Optional[float]] = mapped_column(
        Float,
        server_default=text("0"),
    )
    vat_rate: Mapped[Optional[float]] = mapped_column(
        Float,
        server_default=text("0"),
    )
    is_test_data: Mapped[Optional[int]] = mapped_column(
        Integer,
        server_default=text("0"),
    )
