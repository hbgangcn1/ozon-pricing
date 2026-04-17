from decimal import Decimal
from typing import Optional
from sqlalchemy import String, Integer, Numeric, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column
from models import Base


class CommissionCategory(Base):
    __tablename__ = "commission_category"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "name",
            name="uq_commission_category_user_name",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    name: Mapped[Optional[str]] = mapped_column(String)
    fbp_tier1_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 6))
    fbp_tier2_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 6))
    fbp_tier3_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 6))
    rfbs_tier1_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 6))
    rfbs_tier2_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 6))
    rfbs_tier3_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 6))
    is_active: Mapped[Optional[int]] = mapped_column(
        Integer,
        server_default=text("1"),
    )
