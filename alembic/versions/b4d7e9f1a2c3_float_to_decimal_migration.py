"""float_to_decimal_migration

Revision ID: b4d7e9f1a2c3
Revises: a8c2d4e6f901
Create Date: 2026-04-17 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b4d7e9f1a2c3"
down_revision: Union[str, None] = "a8c2d4e6f901"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 价格/费用列 → Numeric(12, 4)
_PRODUCTS_PRICE_COLS = [
    "unit_price",
    "shipping_fee",
    "labeling_fee",
    "promotion_discount",
    "promotion_cost_rate",
    "target_profit_margin",
    "commission_rate",
    "withdrawal_fee_rate",
    "payment_processing_fee",
    "return_rate",
    "vat_rate",
]

_LOGISTICS_PRICE_COLS = [
    "price_limit",
    "price_limit_rub",
    "price_min",
    "price_min_rub",
    "price_limit_cny",
    "price_min_cny",
    "base_fee",
    "first_fee",
    "continue_fee",
]

# 费率列 → Numeric(12, 6)
_COMMISSION_RATE_COLS = [
    "fbp_tier1_rate",
    "fbp_tier2_rate",
    "fbp_tier3_rate",
    "rfbs_tier1_rate",
    "rfbs_tier2_rate",
    "rfbs_tier3_rate",
]


def _get_existing_tables() -> set:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return set(inspector.get_table_names())


def _get_existing_columns(table_name: str) -> set:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return {col["name"] for col in inspector.get_columns(table_name)}


def _alter_cols_to_numeric(
    table_name: str,
    columns: list,
    precision: int,
    scale: int,
    existing_tables: set,
) -> None:
    if table_name not in existing_tables:
        return
    existing_cols = _get_existing_columns(table_name)
    for col in columns:
        if col not in existing_cols:
            continue
        op.alter_column(
            table_name,
            col,
            type_=sa.Numeric(precision, scale),
            existing_type=sa.Float(),
            existing_nullable=True,
            postgresql_using=f"{col}::numeric({precision},{scale})",
        )


def _alter_cols_to_float(
    table_name: str,
    columns: list,
    precision: int,
    scale: int,
    existing_tables: set,
) -> None:
    if table_name not in existing_tables:
        return
    existing_cols = _get_existing_columns(table_name)
    for col in columns:
        if col not in existing_cols:
            continue
        op.alter_column(
            table_name,
            col,
            type_=sa.Float(),
            existing_type=sa.Numeric(precision, scale),
            existing_nullable=True,
        )


def upgrade() -> None:
    existing_tables = _get_existing_tables()

    # products: 价格/费用列 Float → Numeric(12, 4)
    _alter_cols_to_numeric(
        "products",
        _PRODUCTS_PRICE_COLS,
        12,
        4,
        existing_tables,
    )

    # logistics: 价格/费用列 Float → Numeric(12, 4)
    _alter_cols_to_numeric(
        "logistics",
        _LOGISTICS_PRICE_COLS,
        12,
        4,
        existing_tables,
    )

    # logistics_pool: 同 logistics 对应列
    _alter_cols_to_numeric(
        "logistics_pool",
        _LOGISTICS_PRICE_COLS,
        12,
        4,
        existing_tables,
    )

    # commission_category: 费率列 Float → Numeric(12, 6)
    _alter_cols_to_numeric(
        "commission_category",
        _COMMISSION_RATE_COLS,
        12,
        6,
        existing_tables,
    )

    # exchange_rates: 如果表不存在则创建，否则 ALTER rate 列
    if "exchange_rates" not in existing_tables:
        op.create_table(
            "exchange_rates",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column(
                "currency_pair",
                sa.String,
                unique=True,
                nullable=False,
            ),
            sa.Column("rate", sa.Numeric(12, 6), nullable=False),
            sa.Column("last_updated", sa.DateTime),
            sa.Column("source", sa.String),
        )
    else:
        existing_cols = _get_existing_columns("exchange_rates")
        if "rate" in existing_cols:
            op.alter_column(
                "exchange_rates",
                "rate",
                type_=sa.Numeric(12, 6),
                existing_type=sa.Float(),
                existing_nullable=False,
                postgresql_using="rate::numeric(12,6)",
            )


def downgrade() -> None:
    existing_tables = _get_existing_tables()

    # exchange_rates: 如果表是本次迁移创建的则删除，否则还原 rate 列
    if "exchange_rates" in existing_tables:
        existing_cols = _get_existing_columns("exchange_rates")
        if "rate" in existing_cols:
            op.alter_column(
                "exchange_rates",
                "rate",
                type_=sa.Float(),
                existing_type=sa.Numeric(12, 6),
                existing_nullable=False,
            )

    # commission_category: 费率列 Numeric(12, 6) → Float
    _alter_cols_to_float(
        "commission_category",
        _COMMISSION_RATE_COLS,
        12,
        6,
        existing_tables,
    )

    # logistics_pool: 价格/费用列 Numeric(12, 4) → Float
    _alter_cols_to_float(
        "logistics_pool",
        _LOGISTICS_PRICE_COLS,
        12,
        4,
        existing_tables,
    )

    # logistics: 价格/费用列 Numeric(12, 4) → Float
    _alter_cols_to_float(
        "logistics",
        _LOGISTICS_PRICE_COLS,
        12,
        4,
        existing_tables,
    )

    # products: 价格/费用列 Numeric(12, 4) → Float
    _alter_cols_to_float(
        "products",
        _PRODUCTS_PRICE_COLS,
        12,
        4,
        existing_tables,
    )
