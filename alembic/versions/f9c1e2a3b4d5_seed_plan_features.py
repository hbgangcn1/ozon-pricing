"""seed plan features text

Revision ID: f9c1e2a3b4d5
Revises: e53fd4a44e97
Create Date: 2026-04-24

Refresh the pipe-delimited features text on the four canonical plan rows
(free / efficiency / professional / enterprise) so the SubscriptionPage
renders the strings the Playwright suite asserts on (e.g. '极速模式',
'基础物流模板'). Idempotent: only updates rows that already exist.
"""
from alembic import op
import sqlalchemy as sa


revision = "f9c1e2a3b4d5"
down_revision = "e53fd4a44e97"
branch_labels = None
depends_on = None


PLAN_FEATURES = {
    "free": "基础物流模板|每日10次计算|基础功能",
    "efficiency": "极速模式|3个物流模板|无限次计算|优先客服",
    "professional": "极速模式|10个物流模板|无限次计算|专属客服|数据导出",
    "enterprise": "极速模式|无限物流模板|无限次计算|API接口|定制开发|7x24服务",
}


PREVIOUS_FEATURES = {
    "free": "每日10次计算|1个物流模板|基础功能",
    "efficiency": "无限次计算|3个物流模板|优先客服",
    "professional": "无限次计算|10个物流模板|专属客服|数据导出",
    "enterprise": "无限次计算|无限物流模板|API接口|定制开发|7x24服务",
}


def upgrade() -> None:
    bind = op.get_bind()
    plans = sa.table(
        "plans",
        sa.column("plan_code", sa.String),
        sa.column("features", sa.Text),
    )
    for code, features in PLAN_FEATURES.items():
        bind.execute(
            sa.update(plans)
            .where(plans.c.plan_code == code)
            .values(features=features)
        )


def downgrade() -> None:
    bind = op.get_bind()
    plans = sa.table(
        "plans",
        sa.column("plan_code", sa.String),
        sa.column("features", sa.Text),
    )
    for code, features in PREVIOUS_FEATURES.items():
        bind.execute(
            sa.update(plans)
            .where(plans.c.plan_code == code)
            .values(features=features)
        )
