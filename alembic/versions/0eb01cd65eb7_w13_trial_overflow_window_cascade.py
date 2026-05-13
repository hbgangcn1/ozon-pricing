"""w13 trial_overflow_window cascade

Ensure trial_overflow_window rows are removed when their owning user is
deleted. The original FK was restrictive, leaving audit-window rows orphaned
after user deletion paths that rely on database-level cascading.

Revision ID: 0eb01cd65eb7
Revises: e749dfd9e7f8
Create Date: 2026-05-13 13:28:38.670961

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "0eb01cd65eb7"
down_revision: Union[str, None] = "e749dfd9e7f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_FK_NAME = "trial_overflow_window_user_id_fkey"


def upgrade() -> None:
    op.drop_constraint(_FK_NAME, "trial_overflow_window", type_="foreignkey")
    op.create_foreign_key(
        _FK_NAME,
        "trial_overflow_window",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(_FK_NAME, "trial_overflow_window", type_="foreignkey")
    op.create_foreign_key(
        _FK_NAME,
        "trial_overflow_window",
        "users",
        ["user_id"],
        ["id"],
    )
