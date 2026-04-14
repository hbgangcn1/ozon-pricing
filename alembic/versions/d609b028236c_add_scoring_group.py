"""add_scoring_group

Revision ID: d609b028236c
Revises: acec558bcc6c
Create Date: 2026-04-14 20:25:56.970015

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d609b028236c"
down_revision: Union[str, None] = "acec558bcc6c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_SCORING_KEYWORDS = [
    "Premium Big",
    "Premium Small",
    "Extra Small",
    "Budget",
    "Small",
    "Big",
    "Other",
]


def _extract_scoring_group(name: str) -> str:
    for kw in _SCORING_KEYWORDS:
        if kw in name:
            return kw
    return "Other"


def upgrade() -> None:
    op.add_column(
        "logistics",
        sa.Column("scoring_group", sa.String(), nullable=True),
    )
    op.add_column(
        "logistics_pool",
        sa.Column("scoring_group", sa.String(), nullable=True),
    )

    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT id, name FROM logistics WHERE fulfillment_type = 'fbp'")
    ).fetchall()
    for row in rows:
        sg = _extract_scoring_group(row[1] or "")
        conn.execute(
            sa.text("UPDATE logistics SET scoring_group = :sg WHERE id = :id"),
            {"sg": sg, "id": row[0]},
        )

    pool_rows = conn.execute(
        sa.text("SELECT id, name FROM logistics_pool WHERE fulfillment_type = 'fbp'")
    ).fetchall()
    for row in pool_rows:
        sg = _extract_scoring_group(row[1] or "")
        conn.execute(
            sa.text("UPDATE logistics_pool SET scoring_group = :sg WHERE id = :id"),
            {"sg": sg, "id": row[0]},
        )


def downgrade() -> None:
    op.drop_column("logistics_pool", "scoring_group")
    op.drop_column("logistics", "scoring_group")
