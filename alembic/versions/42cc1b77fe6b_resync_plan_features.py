"""resync plan features

Revision ID: 42cc1b77fe6b
Revises: a9d2c4f1b7e8
Create Date: 2026-05-11 17:57:07.613045

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "42cc1b77fe6b"
down_revision = "a9d2c4f1b7e8"
branch_labels = None
depends_on = None


PLAN_FEATURES = {
    "free": "基础物流模板|每日10次计算|基础功能",
    "efficiency": "极速模式|3个物流模板|无限次计算|优先客服",
    "professional": "极速模式|10个物流模板|无限次计算|专属客服|数据导出",
    "enterprise": "极速模式|无限物流模板|无限次计算|API接口|定制开发|7x24服务",
}


DRIFTED_FEATURES = {
    "free": "仅限快速模式|1条物流规则|每日10次计算|基础功能",
    "efficiency": "仅限快速模式|3条物流规则|无限次计算",
    "professional": "极速模式|精准模式|无限物流规则|无限次计算|批量导入物流规则",
    "enterprise": "快速模式|精准模式|无限物流规则|无限次计算|批量导入物流|批量导入产品|API接口",
}


def _plans_table() -> sa.sql.expression.TableClause:
    return sa.table(
        "plans",
        sa.column("plan_code", sa.String),
        sa.column("features", sa.String),
    )


def _update_features(features_by_code: dict[str, str]) -> None:
    bind = op.get_bind()
    plans = _plans_table()
    for code, features in features_by_code.items():
        bind.execute(
            sa.update(plans)
            .where(plans.c.plan_code == code)
            .values(features=features)
        )


def upgrade() -> None:
    _update_features(PLAN_FEATURES)


def downgrade() -> None:
    _update_features(DRIFTED_FEATURES)
