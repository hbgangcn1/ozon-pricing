from decimal import Decimal
from typing import Optional
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Numeric, text
from sqlalchemy.orm import Mapped, mapped_column
from models import Base


class SystemConfig(Base):
    __tablename__ = "system_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    config_key: Mapped[str] = mapped_column(
        String,
        unique=True,
        nullable=False,
    )
    config_value: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String)
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP"),
    )


class ExchangeRate(Base):
    __tablename__ = "exchange_rates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    currency_pair: Mapped[str] = mapped_column(
        String,
        unique=True,
        nullable=False,
    )
    rate: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    last_updated: Mapped[Optional[datetime]] = mapped_column(DateTime)
    source: Mapped[Optional[str]] = mapped_column(String)
