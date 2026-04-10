"""add_max_third_side

Revision ID: a1b2c3d4e5f6
Revises: eacc63642541
Create Date: 2026-04-10 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "eacc63642541"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "logistics",
        sa.Column(
            "max_third_side",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=True,
        ),
    )
    op.add_column(
        "logistics_pool",
        sa.Column(
            "max_third_side",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("logistics_pool", "max_third_side")
    op.drop_column("logistics", "max_third_side")
