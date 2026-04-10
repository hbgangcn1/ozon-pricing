"""update logistics volume_mode check constraint to include sum_of_sides

Revision ID: d2e9f3b4c5a6
Revises: c1f8e7a9b2d3
Create Date: 2026-04-10 00:00:01.000000

"""

from typing import Sequence, Union

from alembic import op


revision: str = "d2e9f3b4c5a6"
down_revision: Union[str, None] = "c1f8e7a9b2d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("logistics_volume_mode_check", "logistics", type_="check")
    op.create_check_constraint(
        "logistics_volume_mode_check",
        "logistics",
        "volume_mode IN ('none', 'max_actual_vs_volume', 'longest_side', 'sum_of_sides')",
    )


def downgrade() -> None:
    op.drop_constraint("logistics_volume_mode_check", "logistics", type_="check")
    op.create_check_constraint(
        "logistics_volume_mode_check",
        "logistics",
        "volume_mode IN ('none', 'max_actual_vs_volume', 'longest_side')",
    )
