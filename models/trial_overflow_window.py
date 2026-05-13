from sqlalchemy import CheckConstraint, String, Integer, ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column
from models import Base


class TrialOverflowWindow(Base):
    """48-hour reselect window opened when a user's active logistics rules
    exceed their effective plan limit (trial expiry or downgrade).

    Lifecycle:
      - opened_at / expires_at = opened_at + 48h
      - closed_at = 0 means OPEN; partial unique index enforces 1 open per user
      - close_reason in ('expired', 'upgraded', 'reselected') once closed
    """

    __tablename__ = "trial_overflow_window"
    __table_args__ = (
        CheckConstraint(
            "close_reason IN ('', 'expired', 'upgraded', 'reselected')",
            name="ck_trial_overflow_window_close_reason",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    opened_at: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_at: Mapped[int] = mapped_column(Integer, nullable=False)
    closed_at: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    close_reason: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default=text("''"),
    )
