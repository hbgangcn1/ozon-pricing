"""unify_price_limits_to_cny

Revision ID: eacc63642541
Revises: 3acffacf41d4
Create Date: 2026-04-06 14:08:06.692670

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "eacc63642541"
down_revision: Union[str, None] = "3acffacf41d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

RUB_TO_CNY = 0.075
USD_TO_CNY = 7.2


def _convert_limit_expr(limit_col: str, rub_col: str, currency_col: str) -> str:
    return f"""
    CASE
        WHEN COALESCE({currency_col}, 'RUB') = 'USD' AND COALESCE({limit_col}, 0) > 0
            THEN COALESCE({limit_col}, 0) * {USD_TO_CNY}
        WHEN COALESCE({rub_col}, 0) > 0
            THEN COALESCE({rub_col}, 0) * {RUB_TO_CNY}
        WHEN COALESCE({limit_col}, 0) > 0
            THEN COALESCE({limit_col}, 0) * {RUB_TO_CNY}
        ELSE 0
    END
    """


def upgrade() -> None:
    op.add_column(
        "logistics",
        sa.Column("price_limit_cny", sa.Float(), server_default=sa.text("0"), nullable=True),
    )
    op.add_column(
        "logistics",
        sa.Column("price_min_cny", sa.Float(), server_default=sa.text("0"), nullable=True),
    )
    op.add_column(
        "logistics_pool",
        sa.Column("price_limit_cny", sa.Float(), server_default=sa.text("0"), nullable=True),
    )
    op.add_column(
        "logistics_pool",
        sa.Column("price_min_cny", sa.Float(), server_default=sa.text("0"), nullable=True),
    )

    op.execute(
        sa.text(
            f"""
            UPDATE logistics
            SET
                price_limit_cny = {_convert_limit_expr('price_limit', 'price_limit_rub', 'price_limit_currency')},
                price_min_cny = {_convert_limit_expr('price_min', 'price_min_rub', 'price_min_currency')}
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            UPDATE logistics_pool
            SET
                price_limit_cny = {_convert_limit_expr('price_limit', 'price_limit_rub', 'price_limit_currency')},
                price_min_cny = {_convert_limit_expr('price_min', 'price_min_rub', 'price_min_currency')}
            """
        )
    )


def downgrade() -> None:
    op.drop_column("logistics_pool", "price_min_cny")
    op.drop_column("logistics_pool", "price_limit_cny")
    op.drop_column("logistics", "price_min_cny")
    op.drop_column("logistics", "price_limit_cny")
