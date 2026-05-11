"""add statistics hot path indexes

Revision ID: a9d2c4f1b7e8
Revises: c8f3d6b9e2a1
Create Date: 2026-05-11 00:00:00.000000

"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "a9d2c4f1b7e8"
down_revision = "c8f3d6b9e2a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_user_login_log_created_at",
        "user_login_log",
        ["created_at"],
    )
    # Keep the existing composite index (user_id, login_time); it already
    # covers the JOIN side for user_id lookups in the hot path.
    op.create_index(
        "ix_admin_action_log_created_at",
        "admin_action_log",
        ["created_at"],
    )
    op.create_index(
        "ix_admin_action_log_admin_id",
        "admin_action_log",
        ["admin_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_admin_action_log_admin_id", table_name="admin_action_log")
    op.drop_index("ix_admin_action_log_created_at", table_name="admin_action_log")
    op.drop_index("ix_user_login_log_created_at", table_name="user_login_log")
