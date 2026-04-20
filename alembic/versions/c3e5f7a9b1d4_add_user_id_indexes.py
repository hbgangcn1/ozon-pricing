"""add user_id indexes on logistics and products

Revision ID: c3e5f7a9b1d4
Revises: b4d7e9f1a2c3
Create Date: 2026-04-20 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

revision: str = "c3e5f7a9b1d4"
down_revision: Union[str, None] = "b4d7e9f1a2c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_logistics_user_id", "logistics", ["user_id"]
    )
    op.create_index(
        "ix_products_user_id", "products", ["user_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_products_user_id", table_name="products")
    op.drop_index("ix_logistics_user_id", table_name="logistics")
