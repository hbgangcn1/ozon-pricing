"""add session inactive reason

Revision ID: 87a840348f80
Revises: e4f6a8b0c1d2
Create Date: 2026-04-22 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "87a840348f80"
down_revision: Union[str, None] = "e4f6a8b0c1d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "active_sessions",
        sa.Column("inactive_reason", sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("active_sessions", "inactive_reason")
