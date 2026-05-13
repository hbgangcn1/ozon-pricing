"""w13 perf hot path indexes

Wave E P0-02 mapping notes:
- logistics_records(created_at) -> logistics(user_id, id DESC): actual table has
  no created_at and list queries order by id DESC.
- orders(user_id,status,created_at) -> payment_orders(...): there is no orders
  table; payment_orders is the current order store.
- products(user_id, sku) skipped: products has no sku; existing
  ix_products_user_id_name covers current lookup shape.
- payment_orders(out_trade_no) skipped: order_id is the actual out_trade_no and
  already has a unique constraint from the model/migration history.
- sessions(expires_at) -> active_sessions(user_id,is_active,last_activity):
  actual active session table has no expires_at.

Revision ID: f4b8c9d0e1a2
Revises: 3129afc1b841
Create Date: 2026-05-13 18:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


revision: str = "f4b8c9d0e1a2"
down_revision: Union[str, None] = "3129afc1b841"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_logistics_user_id_id_desc "
        "ON logistics (user_id, id DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS "
        "ix_payment_orders_user_status_created_at_desc "
        "ON payment_orders (user_id, status, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_active_sessions_user_active_last_activity "
        "ON active_sessions (user_id, is_active, last_activity)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS "
        "ix_wechat_notify_audit_logs_bad_sig_created_at_desc "
        "ON wechat_notify_audit_logs (created_at DESC) "
        "WHERE signature_verified = false"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS "
        "ix_wechat_notify_audit_logs_created_at_transaction_id "
        "ON wechat_notify_audit_logs (created_at DESC, transaction_id)"
    )


def downgrade() -> None:
    op.execute(
        "DROP INDEX IF EXISTS "
        "ix_wechat_notify_audit_logs_created_at_transaction_id"
    )
    op.execute(
        "DROP INDEX IF EXISTS "
        "ix_wechat_notify_audit_logs_bad_sig_created_at_desc"
    )
    op.execute("DROP INDEX IF EXISTS ix_active_sessions_user_active_last_activity")
    op.execute(
        "DROP INDEX IF EXISTS "
        "ix_payment_orders_user_status_created_at_desc"
    )
    op.execute("DROP INDEX IF EXISTS ix_logistics_user_id_id_desc")
