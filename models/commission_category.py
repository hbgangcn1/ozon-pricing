from typing import Optional
from sqlalchemy import String, Integer, Float, text
from sqlalchemy.orm import Mapped, mapped_column
from models import Base


class CommissionCategory(Base):
    __tablename__ = "commission_category"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[Optional[str]] = mapped_column(String, unique=True)
    fbp_tier1_rate: Mapped[Optional[float]] = mapped_column(Float)
    fbp_tier2_rate: Mapped[Optional[float]] = mapped_column(Float)
    fbp_tier3_rate: Mapped[Optional[float]] = mapped_column(Float)
    rfbs_tier1_rate: Mapped[Optional[float]] = mapped_column(Float)
    rfbs_tier2_rate: Mapped[Optional[float]] = mapped_column(Float)
    rfbs_tier3_rate: Mapped[Optional[float]] = mapped_column(Float)
    is_active: Mapped[Optional[int]] = mapped_column(
        Integer,
        server_default=text("1"),
    )
