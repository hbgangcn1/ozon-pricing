"""w13 api idempotency keys

Persist 24h idempotency-key response snapshots for selected POST endpoints.

Revision ID: 3129afc1b841
Revises: a8ef9b55453a
Create Date: 2026-05-13 13:37:47.131092

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "3129afc1b841"
down_revision: Union[str, None] = "a8ef9b55453a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "api_idempotency_keys",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scope", sa.String(length=64), nullable=False),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("response_body", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("date_part('epoch'::text, now())"),
        ),
        sa.Column("expires_at", sa.Integer(), nullable=False),
        sa.UniqueConstraint("scope", "key", name="uq_api_idempotency_scope_key"),
    )


def downgrade() -> None:
    op.drop_table("api_idempotency_keys")
