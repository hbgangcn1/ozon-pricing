from typing import Optional
from sqlalchemy import String, Integer, Float, text
from sqlalchemy.orm import Mapped, mapped_column
from models import Base


class PaymentOrder(Base):
    __tablename__ = "payment_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[str] = mapped_column(
        String,
        unique=True,
        nullable=False,
    )
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    duration: Mapped[Optional[str]] = mapped_column(String)
    status: Mapped[Optional[str]] = mapped_column(
        String,
        server_default=text("'PENDING'"),
    )
    wechat_transaction_id: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[Optional[int]] = mapped_column(Integer)
    order_type: Mapped[Optional[str]] = mapped_column(String)
    is_upgrade: Mapped[Optional[int]] = mapped_column(
        Integer,
        server_default=text("0"),
    )
    upgrade_from_plan: Mapped[Optional[str]] = mapped_column(String)
    upgrade_to_plan: Mapped[Optional[str]] = mapped_column(String)
    remaining_value: Mapped[Optional[float]] = mapped_column(
        Float,
        server_default=text("0"),
    )
