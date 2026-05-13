from sqlalchemy import Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from models import Base


class ApiIdempotencyKey(Base):
    __tablename__ = "api_idempotency_keys"
    __table_args__ = (
        UniqueConstraint("scope", "key", name="uq_api_idempotency_scope_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scope: Mapped[str] = mapped_column(String(64), nullable=False)
    key: Mapped[str] = mapped_column(String(255), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    response_body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("date_part('epoch'::text, now())"),
    )
    expires_at: Mapped[int] = mapped_column(Integer, nullable=False)
