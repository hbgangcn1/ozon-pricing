"""add pro trial overflow

Revision ID: b7e2f1a4c5d8
Revises: 4a1b2c3d5e6f
Create Date: 2026-05-07 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b7e2f1a4c5d8"
down_revision: Union[str, None] = "4a1b2c3d5e6f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "trial_used",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "trial_started_at",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "trial_expires_at",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "trial_plan_at_start",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("''"),
        ),
    )

    op.add_column(
        "logistics",
        sa.Column(
            "disabled_by_overflow",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "logistics",
        sa.Column(
            "last_used_at",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )

    op.create_table(
        "trial_overflow_window",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("opened_at", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.Integer(), nullable=False),
        sa.Column(
            "closed_at",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "close_reason",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("''"),
        ),
        sa.CheckConstraint(
            "close_reason IN ('', 'expired', 'upgraded', 'reselected')",
            name="ck_trial_overflow_window_close_reason",
        ),
    )
    op.create_index(
        "ix_trial_overflow_window_user_id",
        "trial_overflow_window",
        ["user_id"],
    )
    op.create_index(
        "uq_trial_overflow_window_open_per_user",
        "trial_overflow_window",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("closed_at = 0"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_trial_overflow_window_open_per_user",
        table_name="trial_overflow_window",
    )
    op.drop_index(
        "ix_trial_overflow_window_user_id",
        table_name="trial_overflow_window",
    )
    op.drop_table("trial_overflow_window")
    op.drop_column("logistics", "last_used_at")
    op.drop_column("logistics", "disabled_by_overflow")
    op.drop_column("users", "trial_plan_at_start")
    op.drop_column("users", "trial_expires_at")
    op.drop_column("users", "trial_started_at")
    op.drop_column("users", "trial_used")
