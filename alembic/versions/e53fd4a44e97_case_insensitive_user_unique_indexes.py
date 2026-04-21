"""case insensitive user unique indexes

Revision ID: e53fd4a44e97
Revises: 87a840348f80
Create Date: 2026-04-22 03:45:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e53fd4a44e97"
down_revision: Union[str, None] = "87a840348f80"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Case-insensitive uniqueness is enforced in db/users.py via func.lower(...)
    # pre-checks, but two concurrent transactions can both pass the check and
    # both INSERT, yielding duplicate rows that later make verify_user raise
    # MultipleResultsFound. A partial/functional unique index pushes the
    # guarantee down to PostgreSQL so the race collapses to a single winner.
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_users_username_lower "
        "ON users (lower(username))"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_users_email_lower "
        "ON users (lower(email)) WHERE email IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ux_users_email_lower")
    op.execute("DROP INDEX IF EXISTS ux_users_username_lower")
