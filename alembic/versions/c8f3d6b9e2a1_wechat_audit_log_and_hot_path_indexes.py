"""wechat audit log + hot path indexes

Revision ID: c8f3d6b9e2a1
Revises: b7e2f1a4c5d8
Create Date: 2026-05-11 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "c8f3d6b9e2a1"
down_revision = "b7e2f1a4c5d8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "wechat_notify_audit_logs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("out_trade_no", sa.String(64), nullable=True),
        sa.Column("transaction_id", sa.String(64), nullable=True),
        sa.Column("signature_verified", sa.Boolean, nullable=False),
        sa.Column("raw_body", sa.Text, nullable=False),
        sa.Column("response_code", sa.String(16), nullable=False),
        sa.Column("response_message", sa.String(256), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_wechat_notify_audit_logs_out_trade_no",
        "wechat_notify_audit_logs",
        ["out_trade_no"],
    )
    op.create_index(
        "ix_wechat_notify_audit_logs_transaction_id",
        "wechat_notify_audit_logs",
        ["transaction_id"],
    )

    op.create_index(
        "ix_payment_orders_user_id_created_at",
        "payment_orders",
        ["user_id", "created_at"],
    )
    op.create_index(
        "ix_logistics_user_fulfillment_dest",
        "logistics",
        ["user_id", "fulfillment_type", "destination"],
    )
    op.create_index(
        "ix_logistics_user_active_overflow",
        "logistics",
        ["user_id", "is_active", "disabled_by_overflow"],
    )
    op.create_index(
        "ix_products_user_id_name",
        "products",
        ["user_id", "name"],
    )
    op.create_index(
        "ix_user_login_log_user_time",
        "user_login_log",
        ["user_id", "login_time"],
    )
    op.create_index(
        "ix_active_sessions_user_id",
        "active_sessions",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_active_sessions_user_id", "active_sessions")
    op.drop_index("ix_user_login_log_user_time", "user_login_log")
    op.drop_index("ix_products_user_id_name", "products")
    op.drop_index("ix_logistics_user_active_overflow", "logistics")
    op.drop_index("ix_logistics_user_fulfillment_dest", "logistics")
    op.drop_index("ix_payment_orders_user_id_created_at", "payment_orders")
    op.drop_index(
        "ix_wechat_notify_audit_logs_transaction_id",
        "wechat_notify_audit_logs",
    )
    op.drop_index(
        "ix_wechat_notify_audit_logs_out_trade_no",
        "wechat_notify_audit_logs",
    )
    op.drop_table("wechat_notify_audit_logs")
