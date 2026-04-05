from typing import Optional
from sqlalchemy import String, Integer, text
from sqlalchemy.orm import Mapped, mapped_column
from models import Base


class StatisticsCache(Base):
    __tablename__ = "statistics_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cache_key: Mapped[str] = mapped_column(
        String,
        unique=True,
        nullable=False,
    )
    cache_data: Mapped[str] = mapped_column(String, nullable=False)
    expires_at: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[Optional[int]] = mapped_column(
        Integer,
        server_default=text("date_part('epoch'::text, now())"),
    )
    updated_at: Mapped[Optional[int]] = mapped_column(
        Integer,
        server_default=text("date_part('epoch'::text, now())"),
    )
