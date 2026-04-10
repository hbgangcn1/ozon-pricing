"""add sum_of_sides_threshold to logistics tables

Revision ID: c1f8e7a9b2d3
Revises: 7b3f9a2e1d04
Create Date: 2026-04-10 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c1f8e7a9b2d3"
down_revision: Union[str, None] = "7b3f9a2e1d04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "logistics",
        sa.Column(
            "sum_of_sides_threshold",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=True,
        ),
    )
    op.add_column(
        "logistics_pool",
        sa.Column(
            "sum_of_sides_threshold",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=True,
        ),
    )

    op.execute(
        sa.text(
            """
            UPDATE logistics
            SET volume_mode='longest_side'
            WHERE volume_mode='threshold'
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE logistics_pool
            SET volume_mode='longest_side'
            WHERE volume_mode='threshold'
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE logistics_pool
            SET volume_mode='threshold'
            WHERE volume_mode='longest_side'
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE logistics
            SET volume_mode='threshold'
            WHERE volume_mode='longest_side'
            """
        )
    )

    op.drop_column("logistics_pool", "sum_of_sides_threshold")
    op.drop_column("logistics", "sum_of_sides_threshold")
