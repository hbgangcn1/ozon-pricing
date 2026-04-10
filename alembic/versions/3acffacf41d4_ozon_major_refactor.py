"""ozon-major-refactor

Revision ID: 3acffacf41d4
Revises: d0388d2a0262
Create Date: 2026-04-06 00:44:33.623612

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "3acffacf41d4"
down_revision: Union[str, None] = "d0388d2a0262"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 创建 commission_category 表
    op.create_table(
        "commission_category",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("fbp_tier1_rate", sa.Float(), nullable=True),
        sa.Column("fbp_tier2_rate", sa.Float(), nullable=True),
        sa.Column("fbp_tier3_rate", sa.Float(), nullable=True),
        sa.Column(
            "is_active", sa.Integer(), server_default=sa.text("1"), nullable=True
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    # 创建 logistics_pool 表
    op.create_table(
        "logistics_pool",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("type", sa.String(), nullable=True),
        sa.Column("min_days", sa.Integer(), nullable=True),
        sa.Column("max_days", sa.Integer(), nullable=True),
        sa.Column("price_limit", sa.Float(), nullable=True),
        sa.Column("price_limit_rub", sa.Float(), nullable=True),
        sa.Column("price_min", sa.Float(), server_default=sa.text("0"), nullable=True),
        sa.Column(
            "price_min_rub", sa.Float(), server_default=sa.text("0"), nullable=True
        ),
        sa.Column("base_fee", sa.Float(), server_default=sa.text("0"), nullable=True),
        sa.Column("min_weight", sa.Integer(), nullable=True),
        sa.Column("max_weight", sa.Integer(), nullable=True),
        sa.Column("max_sum_of_sides", sa.Integer(), nullable=True),
        sa.Column("max_longest_side", sa.Integer(), nullable=True),
        sa.Column(
            "max_second_side", sa.Integer(), server_default=sa.text("0"), nullable=True
        ),
        sa.Column(
            "min_second_side", sa.Integer(), server_default=sa.text("0"), nullable=True
        ),
        sa.Column(
            "min_length", sa.Integer(), server_default=sa.text("0"), nullable=True
        ),
        sa.Column(
            "max_cylinder_sum", sa.Integer(), server_default=sa.text("0"), nullable=True
        ),
        sa.Column(
            "min_cylinder_sum", sa.Integer(), server_default=sa.text("0"), nullable=True
        ),
        sa.Column(
            "max_cylinder_length",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=True,
        ),
        sa.Column(
            "min_cylinder_length",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=True,
        ),
        sa.Column(
            "volume_mode", sa.String(), server_default=sa.text("'none'"), nullable=True
        ),
        sa.Column(
            "longest_side_threshold",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=True,
        ),
        sa.Column("allow_battery", sa.Integer(), nullable=True),
        sa.Column("allow_liquid", sa.Integer(), nullable=True),
        sa.Column(
            "battery_capacity_limit_wh",
            sa.Float(),
            server_default=sa.text("0"),
            nullable=True,
        ),
        sa.Column(
            "require_msds", sa.Integer(), server_default=sa.text("0"), nullable=True
        ),
        sa.Column(
            "fee_mode",
            sa.String(),
            server_default=sa.text("'base_plus_continue'"),
            nullable=True,
        ),
        sa.Column("first_fee", sa.Float(), server_default=sa.text("0"), nullable=True),
        sa.Column(
            "first_weight_g", sa.Integer(), server_default=sa.text("0"), nullable=True
        ),
        sa.Column(
            "continue_fee", sa.Float(), server_default=sa.text("0"), nullable=True
        ),
        sa.Column(
            "continue_unit", sa.String(), server_default=sa.text("'100'"), nullable=True
        ),
        sa.Column(
            "volume_coefficient",
            sa.Float(),
            server_default=sa.text("5000"),
            nullable=True,
        ),
        sa.Column(
            "delivery_method",
            sa.String(),
            server_default=sa.text("'unknown'"),
            nullable=True,
        ),
        sa.Column(
            "priority_group", sa.String(), server_default=sa.text("'D'"), nullable=True
        ),
        sa.Column(
            "price_limit_currency",
            sa.String(),
            server_default=sa.text("'RUB'"),
            nullable=True,
        ),
        sa.Column(
            "price_min_currency",
            sa.String(),
            server_default=sa.text("'RUB'"),
            nullable=True,
        ),
        sa.Column(
            "fulfillment_type",
            sa.String(),
            server_default=sa.text("'rfbs'"),
            nullable=True,
        ),
        sa.Column(
            "destination", sa.String(), server_default=sa.text("'RU'"), nullable=True
        ),
        sa.Column("fbp_service_level", sa.String(), nullable=True),
        sa.Column("fbp_company", sa.String(), nullable=True),
        sa.Column("is_smart", sa.Integer(), server_default=sa.text("0"), nullable=True),
        sa.Column("source_file", sa.String(), nullable=True),
        sa.Column("imported_at", sa.Integer(), nullable=True),
        sa.Column(
            "is_active", sa.Integer(), server_default=sa.text("1"), nullable=True
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # 为 logistics 表新增5个字段
    op.add_column(
        "logistics",
        sa.Column(
            "fulfillment_type",
            sa.String(),
            server_default=sa.text("'rfbs'"),
            nullable=True,
        ),
    )
    op.add_column(
        "logistics",
        sa.Column(
            "destination", sa.String(), server_default=sa.text("'RU'"), nullable=True
        ),
    )
    op.add_column(
        "logistics",
        sa.Column("fbp_service_level", sa.String(), nullable=True),
    )
    op.add_column(
        "logistics",
        sa.Column("fbp_company", sa.String(), nullable=True),
    )
    op.add_column(
        "logistics",
        sa.Column("is_smart", sa.Integer(), server_default=sa.text("0"), nullable=True),
    )

    # 为 products 表新增 commission_category_id
    op.add_column(
        "products",
        sa.Column(
            "commission_category_id",
            sa.Integer(),
            server_default=sa.text("NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("products", "commission_category_id")
    op.drop_column("logistics", "is_smart")
    op.drop_column("logistics", "fbp_company")
    op.drop_column("logistics", "fbp_service_level")
    op.drop_column("logistics", "destination")
    op.drop_column("logistics", "fulfillment_type")
    op.drop_table("logistics_pool")
    op.drop_table("commission_category")
