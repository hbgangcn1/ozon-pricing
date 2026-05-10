"""add user last calculations reset date

Revision ID: 4a1b2c3d5e6f
Revises: f9c1e2a3b4d5
Create Date: 2026-04-25 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "4a1b2c3d5e6f"
down_revision: Union[str, None] = "f9c1e2a3b4d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("last_calculations_reset_date", sa.String(length=10), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "last_calculations_reset_date")
