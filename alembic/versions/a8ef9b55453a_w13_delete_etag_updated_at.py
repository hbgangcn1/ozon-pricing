"""w13 delete etag updated_at

Add lightweight integer version columns used to emit weak ETags for single
resource GET responses and to guard DELETE endpoints with If-Match.

Revision ID: a8ef9b55453a
Revises: 0eb01cd65eb7
Create Date: 2026-05-13 13:34:46.344363

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a8ef9b55453a"
down_revision: Union[str, None] = "0eb01cd65eb7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for table in ("products", "logistics", "users"):
        op.add_column(
            table,
            sa.Column(
                "updated_at",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("date_part('epoch'::text, now())"),
            ),
        )


def downgrade() -> None:
    for table in ("users", "logistics", "products"):
        op.drop_column(table, "updated_at")
