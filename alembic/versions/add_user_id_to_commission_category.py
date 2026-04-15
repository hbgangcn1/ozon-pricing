"""add user_id to commission_category

Revision ID: a8c2d4e6f901
Revises: d609b028236c
Create Date: 2026-04-15 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a8c2d4e6f901"
down_revision: Union[str, None] = "d609b028236c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "commission_category", sa.Column("user_id", sa.Integer(), nullable=True)
    )
    op.execute(
        sa.text("UPDATE commission_category SET user_id = 1 WHERE user_id IS NULL")
    )
    op.drop_constraint(
        "commission_category_name_key",
        "commission_category",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_commission_category_user_name",
        "commission_category",
        ["user_id", "name"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_commission_category_user_name",
        "commission_category",
        type_="unique",
    )
    op.create_unique_constraint(
        "commission_category_name_key",
        "commission_category",
        ["name"],
    )
    op.drop_column("commission_category", "user_id")
