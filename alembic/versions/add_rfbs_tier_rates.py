"""add rfbs tier rate columns

Revision ID: 7b3f9a2e1d04
Revises: eacc63642541
Create Date: 2026-04-06 18:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7b3f9a2e1d04"
down_revision: Union[str, None] = "eacc63642541"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "commission_category",
        sa.Column("rfbs_tier1_rate", sa.Float(), nullable=True),
    )
    op.add_column(
        "commission_category",
        sa.Column("rfbs_tier2_rate", sa.Float(), nullable=True),
    )
    op.add_column(
        "commission_category",
        sa.Column("rfbs_tier3_rate", sa.Float(), nullable=True),
    )

    op.execute(
        sa.text(
            """
            UPDATE commission_category
            SET
                rfbs_tier1_rate = COALESCE(fbp_tier1_rate, 0) + 0.01,
                rfbs_tier2_rate = COALESCE(fbp_tier2_rate, 0) + 0.01,
                rfbs_tier3_rate = COALESCE(fbp_tier3_rate, 0) + 0.01
            """
        )
    )


def downgrade() -> None:
    op.drop_column("commission_category", "rfbs_tier3_rate")
    op.drop_column("commission_category", "rfbs_tier2_rate")
    op.drop_column("commission_category", "rfbs_tier1_rate")
