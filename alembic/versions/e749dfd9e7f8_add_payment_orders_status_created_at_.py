"""add_payment_orders_status_created_at_index

Revision ID: e749dfd9e7f8
Revises: 42cc1b77fe6b
Create Date: 2026-05-11 18:59:37.826488

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e749dfd9e7f8'
down_revision: Union[str, None] = '42cc1b77fe6b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_payment_orders_status_created_at",
        "payment_orders",
        ["status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_payment_orders_status_created_at", table_name="payment_orders")
