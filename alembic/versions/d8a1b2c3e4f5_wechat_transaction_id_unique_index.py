"""partial unique index on wechat_transaction_id for idempotency defense-in-depth

Revision ID: d8a1b2c3e4f5
Revises: c3e5f7a9b1d4
Create Date: 2026-04-21 14:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

revision: str = "d8a1b2c3e4f5"
down_revision: Union[str, None] = "c3e5f7a9b1d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "uq_payment_orders_wechat_transaction_id",
        "payment_orders",
        ["wechat_transaction_id"],
        unique=True,
        postgresql_where="wechat_transaction_id IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_index(
        "uq_payment_orders_wechat_transaction_id",
        table_name="payment_orders",
    )
