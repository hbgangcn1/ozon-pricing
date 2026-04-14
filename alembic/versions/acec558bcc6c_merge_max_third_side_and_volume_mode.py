"""merge_max_third_side_and_volume_mode

Revision ID: acec558bcc6c
Revises: a1b2c3d4e5f6, d2e9f3b4c5a6
Create Date: 2026-04-10 20:29:01.890564

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "acec558bcc6c"
down_revision: Union[str, Sequence[str], None] = ("a1b2c3d4e5f6", "d2e9f3b4c5a6")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
