"""
数据库索引优化脚本
为关键查询添加索引以提升性能
"""

from typing import Dict, Any

try:
    from .db_utils import get_db_connection
    from .db_adapter import (
        get_db_connection as get_adapted_connection, DB_TYPE
    )
except ImportError:
    from db_utils import get_db_connection
    from db_adapter import (
        get_db_connection as get_adapted_connection, DB_TYPE
    )


class DatabaseIndexOptimizer:
    """数据库索引优化器"""

    def __init__(self):
        self.indexes_created = []
        self.performance_improvements = {}

    def optimize_sqlite_indexes(self):
        """优化SQLite索引"""
        if DB_TYPE != 'sqlite':
            print("当前数据库类型不是SQLite，跳过SQLite索引优化")
            return

        print("开始优化SQLite索引...")
        indexes = DatabaseIndexOptimizer._get_required_indexes_sqlite()

        with get_db_connection() as (conn, cursor):
            for index_name, sql in indexes.items():
                try:
                    cursor.execute(sql)
                    self.indexes_created.append(index_name)
                    print(f"✅ 创建索引: {index_name}")
                except Exception as e:
                    print(f"❌ 创建索引失败 {index_name}: {e}")

        print(f"SQLite索引优化完成，共创建 "
              f"{len(self.indexes_created)} 个索引")

    def optimize_postgresql_indexes(self):
        """优化PostgreSQL索引"""
        if DB_TYPE != 'postgresql':
            print("当前数据库类型不是PostgreSQL，跳过PostgreSQL索引优化")
            return

        print("开始优化PostgreSQL索引...")
        indexes = DatabaseIndexOptimizer._get_required_indexes_postgresql()

        with get_adapted_connection() as (conn, cursor):
            for index_name, sql in indexes.items():
                try:
                    cursor.execute(sql)
                    self.indexes_created.append(index_name)
                    print(f"✅ 创建索引: {index_name}")
                except Exception as e:
                    print(f"❌ 创建索引失败 {index_name}: {e}")

        print(f"PostgreSQL索引优化完成，共创建 "
              f"{len(self.indexes_created)} 个索引")

    @staticmethod
    def _get_required_indexes_sqlite() -> Dict[str, str]:
        """获取需要创建的索引（SQLite）"""
        return {
            # 用户相关索引
            'idx_users_username': (
                'CREATE INDEX IF NOT EXISTS idx_users_username '
                'ON users(username)'
            ),
            'idx_users_email': (
                'CREATE INDEX IF NOT EXISTS idx_users_email '
                'ON users(email)'
            ),
            'idx_users_subscription': (
                'CREATE INDEX IF NOT EXISTS idx_users_subscription '
                'ON users(subscription_type)'
            ),
            'idx_users_created_at': (
                'CREATE INDEX IF NOT EXISTS idx_users_created_at '
                'ON users(created_at)'
            ),

            # 产品相关索引
            'idx_products_user_id': (
                'CREATE INDEX IF NOT EXISTS idx_products_user_id '
                'ON products(user_id)'
            ),
            'idx_products_name': (
                'CREATE INDEX IF NOT EXISTS idx_products_name '
                'ON products(name)'
            ),
            'idx_products_created_at': (
                'CREATE INDEX IF NOT EXISTS idx_products_created_at '
                'ON products(created_at)'
            ),

            # 物流相关索引
            'idx_logistics_user_id': (
                'CREATE INDEX IF NOT EXISTS idx_logistics_user_id '
                'ON logistics(user_id)'
            ),
            'idx_logistics_type': (
                'CREATE INDEX IF NOT EXISTS idx_logistics_type '
                'ON logistics(type)'
            ),
            'idx_logistics_created_at': (
                'CREATE INDEX IF NOT EXISTS idx_logistics_created_at '
                'ON logistics(created_at)'
            ),

            # 支付订单相关索引
            'idx_payment_orders_user_id': (
                'CREATE INDEX IF NOT EXISTS idx_payment_orders_user_id '
                'ON payment_orders(user_id)'
            ),
            'idx_payment_orders_status': (
                'CREATE INDEX IF NOT EXISTS idx_payment_orders_status '
                'ON payment_orders(status)'
            ),
            'idx_payment_orders_created_at': (
                'CREATE INDEX IF NOT EXISTS idx_payment_orders_created_at '
                'ON payment_orders(created_at)'
            ),

            # 用户行为日志索引
            'idx_user_behavior_log_user_id': (
                'CREATE INDEX IF NOT EXISTS idx_user_behavior_log_user_id '
                'ON user_behavior_log(user_id)'
            ),
            'idx_user_behavior_log_action': (
                'CREATE INDEX IF NOT EXISTS idx_user_behavior_log_action '
                'ON user_behavior_log(action)'
            ),
            'idx_user_behavior_log_created_at': (
                'CREATE INDEX IF NOT EXISTS idx_user_behavior_log_created_at '
                'ON user_behavior_log(created_at)'
            ),

            # 管理员操作日志索引
            'idx_admin_action_log_admin_id': (
                'CREATE INDEX IF NOT EXISTS idx_admin_action_log_admin_id '
                'ON admin_action_log(admin_id)'
            ),
            'idx_admin_action_log_action': (
                'CREATE INDEX IF NOT EXISTS idx_admin_action_log_action '
                'ON admin_action_log(action)'
            ),
            'idx_admin_action_log_created_at': (
                'CREATE INDEX IF NOT EXISTS idx_admin_action_log_created_at '
                'ON admin_action_log(created_at)'
            )
        }

    @staticmethod
    def _get_required_indexes_postgresql() -> Dict[str, str]:
        """获取需要创建的索引（PostgreSQL）"""
        return {
            # 用户相关索引
            'idx_users_username': (
                'CREATE INDEX IF NOT EXISTS idx_users_username '
                'ON users(username)'
            ),
            'idx_users_email': (
                'CREATE INDEX IF NOT EXISTS idx_users_email '
                'ON users(email)'
            ),
            'idx_users_subscription': (
                'CREATE INDEX IF NOT EXISTS idx_users_subscription '
                'ON users(subscription_type)'
            ),
            'idx_users_created_at': (
                'CREATE INDEX IF NOT EXISTS idx_users_created_at '
                'ON users(created_at)'
            ),

            # 产品相关索引
            'idx_products_user_id': (
                'CREATE INDEX IF NOT EXISTS idx_products_user_id '
                'ON products(user_id)'
            ),
            'idx_products_name': (
                'CREATE INDEX IF NOT EXISTS idx_products_name '
                'ON products(name)'
            ),
            'idx_products_created_at': (
                'CREATE INDEX IF NOT EXISTS idx_products_created_at '
                'ON products(created_at)'
            ),

            # 物流相关索引
            'idx_logistics_user_id': (
                'CREATE INDEX IF NOT EXISTS idx_logistics_user_id '
                'ON logistics(user_id)'
            ),
            'idx_logistics_type': (
                'CREATE INDEX IF NOT EXISTS idx_logistics_type '
                'ON logistics(type)'
            ),
            'idx_logistics_created_at': (
                'CREATE INDEX IF NOT EXISTS idx_logistics_created_at '
                'ON logistics(created_at)'
            ),

            # 支付订单相关索引
            'idx_payment_orders_user_id': (
                'CREATE INDEX IF NOT EXISTS idx_payment_orders_user_id '
                'ON payment_orders(user_id)'
            ),
            'idx_payment_orders_status': (
                'CREATE INDEX IF NOT EXISTS idx_payment_orders_status '
                'ON payment_orders(status)'
            ),
            'idx_payment_orders_created_at': (
                'CREATE INDEX IF NOT EXISTS idx_payment_orders_created_at '
                'ON payment_orders(created_at)'
            ),

            # 用户行为日志索引
            'idx_user_behavior_log_user_id': (
                'CREATE INDEX IF NOT EXISTS idx_user_behavior_log_user_id '
                'ON user_behavior_log(user_id)'
            ),
            'idx_user_behavior_log_action': (
                'CREATE INDEX IF NOT EXISTS idx_user_behavior_log_action '
                'ON user_behavior_log(action)'
            ),
            'idx_user_behavior_log_created_at': (
                'CREATE INDEX IF NOT EXISTS idx_user_behavior_log_created_at '
                'ON user_behavior_log(created_at)'
            ),

            # 管理员操作日志索引
            'idx_admin_action_log_admin_id': (
                'CREATE INDEX IF NOT EXISTS idx_admin_action_log_admin_id '
                'ON admin_action_log(admin_id)'
            ),
            'idx_admin_action_log_action': (
                'CREATE INDEX IF NOT EXISTS idx_admin_action_log_action '
                'ON admin_action_log(action)'
            ),
            'idx_admin_action_log_created_at': (
                'CREATE INDEX IF NOT EXISTS idx_admin_action_log_created_at '
                'ON admin_action_log(created_at)'
            )
        }

    def get_performance_report(self) -> Dict[str, Any]:
        """获取性能优化报告"""
        return {
            'indexes_created': self.indexes_created,
            'total_indexes': len(self.indexes_created),
            'performance_improvements': self.performance_improvements
        }


def optimize_database_indexes():
    """优化数据库索引的主函数"""
    optimizer = DatabaseIndexOptimizer()

    if DB_TYPE == 'sqlite':
        optimizer.optimize_sqlite_indexes()
    elif DB_TYPE == 'postgresql':
        optimizer.optimize_postgresql_indexes()
    else:
        print(f"不支持的数据库类型: {DB_TYPE}")
        return

    # 输出性能报告
    report = optimizer.get_performance_report()
    print("\n📊 索引优化报告:")
    print(f"   创建索引数量: {report['total_indexes']}")
    print(f"   索引列表: {', '.join(report['indexes_created'])}")


if __name__ == "__main__":
    optimize_database_indexes()
